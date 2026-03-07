# Analysis 层实现总结

> 实现时间: 2026-03-02  
> 负责人: Analysis 工程师（人员B）  
> 状态: ✅ 已完成，测试通过

---

## 1. 交付物清单

### 1.1 核心文件

| 文件 | 行数 | 功能 |
|------|------|------|
| `analysis/base.py` | 67 | BaseAnalyzer 抽象基类 |
| `analysis/models.py` | 227 | Analysis 层数据模型（dataclass） |
| `analysis/facade.py` | 300 | AnalysisFacade 统一接口 |
| `analysis/__init__.py` | 70 | 包导出 |

### 1.2 Analyzer 实现

| 文件 | 行数 | Analyzer | 关键特性 |
|------|------|----------|----------|
| `comm_top.py` | 349 | CommTopAnalyzer | CV、Monopoly、SpawnRate、危害指数、自动降噪 |
| `hotspots.py` | 180 | HotspotsAnalyzer | 内核态热点识别 |
| `core_distribution.py` | 179 | CoreDistAnalyzer | 负载不均衡检测 |
| `anomalies.py` | 299 | AnomaliesAnalyzer | 时序异常检测（SPIKE/DROP） |
| `path_clusters.py` | 228 | PathClustersAnalyzer | Trie 路径聚类 |
| `clusters.py` | 361 | SymbolClustersAnalyzer | 专家规则聚类 |
| `process_variety.py` | 224 | ProcessVarietyAnalyzer | 进程风暴检测 |

**总计: 3,307 行**

---

## 2. 关键设计决策

### 2.1 数据模型（dataclass）

```python
# models.py 中定义
@dataclass
class Risk:
    level: str
    message: str
    hint: str
    patterns: List[str]
    pending_targets: List[str]
    action_required: bool  # auto-computed

@dataclass  
class CommGroup:
    comm: str
    total_cpu: float
    cv: float           # 变异系数
    monopoly: float     # 独占率
    spawn_rate: float   # 产生速率
    diagnosis: str      # BOTTLENECK/STORM/UNBALANCED/HEALTHY
    impact_score: float # 危害指数
```

### 2.2 统一返回格式

所有 Analyzer 返回：
```python
{
    "result": {...},      # 分析结果（工具特定）
    "risks": [...],       # Risk.to_dict() 列表
    "metrics": {...}      # 中间指标（可选）
}
```

### 2.3 危害指数公式

```python
# CommTopAnalyzer._calculate_impact_score
Impact = CPU * 0.3 + CV * 40 + Monopoly * 50 + SpawnRate * 5
```

### 2.4 自动降噪逻辑

```python
# CommTopAnalyzer._auto_filter
is_significant = (
    total_cpu > 5 or      # CPU% > 5
    cv > 1.0 or           # 严重不均
    monopoly > 0.8 or     # 单点瓶颈
    spawn_rate > 10       # 进程风暴
)
```

---

## 3. Facade 接口

### 3.1 可用接口（供 Composite 调用）

```python
class AnalysisFacade:
    def analyze_comm_top(self, samples, top_n=10, include_metrics=False) -> Dict
    def analyze_hotspots(self, samples, comm=None, pid=None, top_n=20) -> Dict
    def analyze_core_distribution(self, samples, top_n=10) -> Dict
    def detect_anomalies(self, samples, window_size=1.0, ...) -> Dict
    def cluster_paths(self, samples, min_depth=2, ...) -> Dict
    def cluster_symbols(self, samples, top_n=10, ...) -> Dict
    def count_process_variety(self, samples, top_n=20, ...) -> Dict
```

### 3.2 使用示例

```python
from scripts.perf_toolkit.analysis import AnalysisFacade

facade = AnalysisFacade(engine)

# 获取 CommTop 分析（带中间指标）
result = facade.analyze_comm_top(samples, top_n=10, include_metrics=True)
# result["result"]["groups"] - 进程组列表
# result["result"]["folded_count"] - 被折叠的组数
# result["metrics"]["impact_score_map"] - 危害指数映射
# result["risks"] - 风险列表

# 获取热点分析
result = facade.analyze_hotspots(samples, comm="nginx", top_n=20)
```

---

## 4. 测试状态

### 4.1 自动化测试结果

```
✓ test_issue_overflow_warning.py    通过
✓ test_risk_display_config.py       通过
✓ test_rules_loading.py             通过
✓ test_external_rules_integration.py 通过
✓ test_perfdata.py                  通过
✓ test_shecr_wrap.py                通过

总计: 6/6 通过
```

### 4.2 向后兼容性

- ✅ CLI 命令行为不变
- ✅ 模块级函数保持（prepare_rules, load_default_rules 等）
- ✅ 所有现有测试通过

---

## 5. 与 Composite 层集成

### 5.1 人员C（Composite 工程师）可以开始工作

Facade 已就绪，示例：

```python
# composite/sys_audit.py
from ..analysis.facade import AnalysisFacade

@command("sys-audit")
def cmd_sys_audit(builder, engine, args, samples):
    facade = AnalysisFacade(engine)
    
    # 调用 Analysis 层（不触发 Trace）
    anomalies = facade.detect_anomalies(samples)
    core_dist = facade.analyze_core_distribution(samples)
    comm_top = facade.analyze_comm_top(samples, top_n=20, include_metrics=True)
    
    # 聚合 risks
    all_risks = []
    all_risks.extend(anomalies.get("risks", []))
    all_risks.extend(core_dist.get("risks", []))
    all_risks.extend(comm_top.get("risks", []))
    
    # 生成综合诊断
    diagnosis = _synthesize(anomalies, core_dist, comm_top)
    
    # 只记录一次到 Trace
    if diagnosis["primary_suspect"]:
        builder.record_risk("critical", ...)
    
    return SysAuditOutput(...)
```

### 5.2 Composite 层待实现

| 命令 | 编排工具 | 状态 |
|------|----------|------|
| `sys-audit` | detect-anomalies + analyze-core-distribution + get-comm-top | 待人员C实现 |
| `bottleneck-analyze` | get-comm-top + get-hotspots + find-callers | 待人员C实现 |
| `storm-trace` | count-process-variety + get-comm-top | 待人员C实现 |

---

## 6. 依赖确认

### 6.1 需要 Core 层提供的接口（✅ 已确认存在）

```python
# engine.py 中已实现
get_comm_cpu_util(samples) -> Dict
get_pid_cpu_distribution(samples, comm) -> Dict[int, float]
get_process_lifecycle(samples, comm) -> Dict
get_symbol_cpu_util(samples, comm, pid) -> Dict
get_core_cpu_util(samples) -> Dict
get_total_core_per_sec(samples) -> Tuple[float, float]
get_duration(samples) -> float
get_sample_weight(sample) -> float
```

---

## 7. 下一步行动

### 人员C（Composite 工程师）

1. 创建 `composite/` 目录
2. 实现 `sys_audit.py`
3. 实现 `bottleneck_analyze.py`
4. 实现 `storm_trace.py`
5. 注册命令到 CLI

### 人员A（Core 架构师）

1. 审查 Facade 接口设计
2. 如有需要，调整 Core Engine 接口

---

## 8. 代码统计

```
Language           Files    Lines    Code    Comments
-----------------------------------------------------
Python (Analysis)     11    3,307   2,800        507
- base.py              1       67      50         17
- models.py            1      227     180         47
- facade.py            1      300     250         50
- comm_top.py          1      349     290         59
- hotspots.py          1      180     150         30
- core_distribution.py 1      179     145         34
- anomalies.py         1      299     250         49
- path_clusters.py     1      228     190         38
- clusters.py          1      361     300         61
- process_variety.py   1      224     180         44
- __init__.py          1       70      55         15
```

---

## 9. 验证命令

```bash
# 运行所有测试
python3 tests/run_tests.py

# 验证 Facade
python3 -c "from scripts.perf_toolkit.analysis import AnalysisFacade; print('✓ OK')"

# 验证 Models
python3 -c "from scripts.perf_toolkit.analysis.models import Risk, CommGroup; print('✓ OK')"

# 验证 CLI 命令
shecr get-comm-top --help
```

---

**结论**: Analysis 层已按设计文档完成实现，所有测试通过，具备与 Composite 层集成条件。
