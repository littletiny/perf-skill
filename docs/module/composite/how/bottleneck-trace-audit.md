# bottleneck-trace 与 sys-audit Risk 集成设计

> 版本: 1.0  
> 日期: 2026-03-04  
> 状态: 设计阶段

---

## 背景与问题

### 当前行为

```bash
# 1. 执行 sys-audit 发现 4 个关键瓶颈
shecr sys-audit --data perf.data
# 输出: [X0] 发现 4 个关键性能瓶颈: netstat, python3, containerd-shim, kubelet
#       自动创建 ISS-001

# 2. 执行 bottleneck-trace（自动识别模式）
shecr bottleneck-trace --data perf.data
# 问题: 重新自动识别，只分析 netstat（危害指数最高）
# 忽略了 ISS-001 中记录的另外 3 个瓶颈
```

### 问题分析

| 问题 | 说明 |
|------|------|
| 信息孤岛 | sys-audit 发现的多个瓶颈，bottleneck-trace 不知道 |
| 重复识别 | bottleneck-trace 重新计算，可能得到不同结果 |
| 遗漏分析 | 用户可能忘记分析其他瓶颈进程 |
| 违背延迟收敛 | 没有引导用户完成所有 pending issues |

---

## 设计目标

1. **无缝继承**: bottleneck-trace 默认继承 sys-audit 发现的待处理 issues
2. **优先级引导**: 按危害指数排序，引导用户逐个分析
3. **显式选择**: 支持用户指定分析特定进程
4. **向后兼容**: 无 Trace 文档时，回退到自动识别模式

---

## 数据流设计

```
┌─────────────────────────────────────────────────────────────────┐
│  Phase 1: sys-audit 发现问题                                     │
└─────────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│  Trace (/.shecr.json)                                           │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  issues: {                                              │   │
│  │    "ISS-001": {                                         │   │
│  │      "desc": "发现 4 个关键性能瓶颈",                    │   │
│  │      "level": "critical",                               │   │
│  │      "status": "open",                                  │   │
│  │      "pending_targets": ["netstat", "python3",          │   │
│  │                          "containerd-shim", "kubelet"], │   │
│  │      "metrics": {                                       │   │
│  │        "netstat": {"cpu": 243.9, "score": 431.0},       │   │
│  │        "python3": {"cpu": 207.2, "score": 282.2},       │   │
│  │        ...                                              │   │
│  │      }                                                  │   │
│  │    }                                                    │   │
│  │  }                                                     │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│  Phase 2: bottleneck-trace 继承问题                              │
└─────────────────────────────────────────────────────────────────┘
                            │
            ┌───────────────┼───────────────┐
            │               │               │
            ▼               ▼               ▼
    ┌───────────┐   ┌───────────┐   ┌───────────┐
    │ 有 open   │   │ 有 open   │   │ 无 open   │
    │ issues    │   │ issues    │   │ issues    │
    │ + 无      │   │ + 有      │   │           │
    │ --comm    │   │ --comm    │   │           │
    └─────┬─────┘   └─────┬─────┘   └─────┬─────┘
          │               │               │
          ▼               ▼               ▼
    按优先级选择      分析指定进程      自动识别
    第一个 pending    无论是否在        瓶颈
    target            issues 中
```

---

## CLI 行为变更

### 场景 1: 无参数执行（默认继承）

```bash
shecr bottleneck-trace --data perf.data
```

**新行为**:

```
═══════════════════════════════════════════════════════════════════
BOTTLENECK-TRACE: 继承 sys-audit 发现的问题
═══════════════════════════════════════════════════════════════════

从 ISS-001 发现 4 个待分析瓶颈（按危害指数排序）:

  [1] netstat          Score: 431.0  CPU: 243.9%  ⚠️  高内核态 95%
  [2] python3          Score: 282.2  CPU: 207.2%  
  [3] containerd-shim  Score: 225.2  CPU: 96.0%   ⚠️  高内核态 90%
  [4] kubelet          Score: 205.5  CPU: 114.9%  

当前分析: netstat (危害指数最高)
═══════════════════════════════════════════════════════════════════

[分析结果...]

下一步建议:
  • 标记完成: shecr trace complete --id ISS-001 --result "netstat: ..."
  • 分析下一个: shecr bottleneck-trace --data perf.data --next
  • 分析指定: shecr bottleneck-trace --comm python3
```

### 场景 2: 显式指定进程

```bash
shecr bottleneck-trace --data perf.data --comm python3
```

**行为不变**: 直接分析指定进程，不受 issues 影响。

### 场景 3: 分析下一个

```bash
shecr bottleneck-trace --data perf.data --next
```

**新参数**: `--next` 自动选择 issues 中下一个未分析的 pending target。

### 场景 4: 无 Trace 文档（向后兼容）

```bash
# 无 .shecr.json 或 issues 都已解决
shecr bottleneck-trace --data perf.data
```

**回退行为**: 按原有逻辑自动识别瓶颈。

---

## 数据结构扩展

### Issue 结构扩展

```python
@dataclass
class Issue:
    id: str
    desc: str
    level: str
    status: str  # open | resolved
    created_at: str
    created_by_seq: int
    
    # 新增字段
    pending_targets: List[str] = field(default_factory=list)  # 待分析目标列表
    analyzed_targets: List[str] = field(default_factory=list)  # 已分析目标列表
    metrics: Dict[str, Dict] = field(default_factory=dict)    # 每个目标的详细指标
    
    resolved_at: Optional[str] = None
    resolved_by_seq: Optional[int] = None
    result: Optional[str] = None
    hint: str = ""
```

### 示例 Issue

```json
{
  "ISS-001": {
    "id": "ISS-001",
    "desc": "发现 4 个关键性能瓶颈",
    "level": "critical",
    "status": "open",
    "created_at": "2026-03-04T10:30:00Z",
    "created_by_seq": 1,
    "pending_targets": ["python3", "containerd-shim", "kubelet"],
    "analyzed_targets": ["netstat"],
    "metrics": {
      "netstat": {
        "cpu": 243.9,
        "sys_cpu": 230.9,
        "kernel_ratio": 95.0,
        "pids": 2623,
        "score": 431.0,
        "monopoly": 0.85,
        "diagnosis": "BOTTLENECK"
      },
      "python3": {
        "cpu": 207.2,
        "sys_cpu": 72.9,
        "kernel_ratio": 35.0,
        "pids": 826,
        "score": 282.2,
        "monopoly": 0.72,
        "diagnosis": "BOTTLENECK"
      }
    },
    "hint": "执行 bottleneck-trace 逐个分析"
  }
}
```

---

## 核心逻辑实现

### 1. Trace 类扩展

```python
class Trace:
    """扩展 Trace 类以支持 pending_targets 管理"""
    
    def get_open_issues_with_pending_targets(self) -> List[Issue]:
        """获取有 pending_targets 的 open issues"""
        return [
            issue for issue in self.data.issues.values()
            if issue.status == "open" and issue.pending_targets
        ]
    
    def mark_target_analyzed(self, issue_id: str, target: str):
        """标记某个 target 已分析"""
        issue = self.data.issues.get(issue_id)
        if issue and target in issue.pending_targets:
            issue.pending_targets.remove(target)
            issue.analyzed_targets.append(target)
            self.save()
    
    def get_next_pending_target(self, issue_id: Optional[str] = None) -> Optional[Tuple[str, Issue]]:
        """获取下一个待分析的 target
        
        Returns:
            Tuple[str, Issue]: (target_comm, issue) 或 None
        """
        if issue_id:
            issue = self.data.issues.get(issue_id)
            if issue and issue.pending_targets:
                return (issue.pending_targets[0], issue)
            return None
        
        # 查找所有 issues 中优先级最高的 pending target
        for issue in self.get_open_issues_with_pending_targets():
            if issue.pending_targets:
                return (issue.pending_targets[0], issue)
        return None
```

### 2. bottleneck-trace 命令修改

```python
@command("bottleneck-trace")
def cmd_bottleneck_trace(
    builder: 'OutputBuilder',
    engine: 'PerfExpertEngine',
    args: 'Namespace',
    samples: List[Dict[str, Any]]
) -> BottleneckTraceResult:
    """
    [Composite] 瓶颈追踪命令 - 支持从 sys-audit 继承 issues
    
    Args:
        --comm: 指定目标进程（可选，优先级最高）
        --next: 分析 issues 中的下一个 pending target
    """
    target_comm = getattr(args, 'comm', None)
    next_mode = getattr(args, 'next', False)
    top_n = getattr(args, 'top_n', 10)
    
    facade = AnalysisFacade(engine)
    
    # ========== Phase 1: 确定目标进程 ==========
    
    selected_issue = None
    
    if target_comm:
        # 显式指定，直接使用
        pass
    elif next_mode:
        # 从 Trace 获取下一个 pending target
        next_target_info = builder.trace.get_next_pending_target()
        if next_target_info:
            target_comm, selected_issue = next_target_info
            builder.print_info(f"从 {selected_issue.id} 选择下一个分析目标: {target_comm}")
    else:
        # 默认: 检查是否有 open issues
        open_issues = builder.trace.get_open_issues_with_pending_targets()
        if open_issues:
            # 有 issues，选择第一个 pending target
            selected_issue = open_issues[0]
            target_comm = selected_issue.pending_targets[0]
            builder.print_info(f"继承 {selected_issue.id} 的分析目标: {target_comm}")
            
            # 打印所有待分析目标（仅在首次分析时）
            if len(selected_issue.analyzed_targets) == 0:
                _print_pending_targets_summary(builder, selected_issue)
        else:
            # 无 issues，自动识别
            target_comm = _find_bottleneck_comm(facade, samples)
    
    if not target_comm:
        return _create_no_bottleneck_result(samples)
    
    # ========== Phase 2-5: 原有分析流程 ==========
    
    bottleneck_analysis = _analyze_bottleneck(facade, samples, target_comm)
    hotspots_result = facade.analyze_hotspots(samples, comm=target_comm, top_n=top_n)
    hotspots_report = _convert_hotspots_result(hotspots_result)
    
    # ... 后续原有逻辑 ...
    
    # ========== Phase 6: 更新 Issue 状态 ==========
    
    if selected_issue and target_comm in selected_issue.pending_targets:
        builder.trace.mark_target_analyzed(selected_issue.id, target_comm)
        builder.print_info(f"已标记 {target_comm} 分析完成")
        
        # 如果还有 pending targets，提示用户
        if selected_issue.pending_targets:
            next_target = selected_issue.pending_targets[0]
            builder.print_info(f"下一步: shecr bottleneck-trace --comm {next_target}")
    
    return result


def _print_pending_targets_summary(builder: 'OutputBuilder', issue: Issue):
    """打印待分析目标摘要"""
    lines = [
        "═══════════════════════════════════════════════════════════════════",
        f"BOTTLENECK-TRACE: 从 {issue.id} 继承 {len(issue.pending_targets)} 个待分析瓶颈",
        "═══════════════════════════════════════════════════════════════════",
        "",
        "按危害指数排序:",
    ]
    
    # 按 score 排序显示
    sorted_targets = sorted(
        issue.pending_targets,
        key=lambda t: issue.metrics.get(t, {}).get('score', 0),
        reverse=True
    )
    
    for i, target in enumerate(sorted_targets, 1):
        m = issue.metrics.get(target, {})
        cpu = m.get('cpu', 0)
        score = m.get('score', 0)
        kernel = m.get('kernel_ratio', 0)
        flag = "⚠️  高内核态" if kernel > 50 else ""
        lines.append(f"  [{i}] {target:20s} Score: {score:6.1f}  CPU: {cpu:6.1f}%  {flag}")
    
    lines.extend([
        "",
        f"当前分析: {sorted_targets[0]} (危害指数最高)",
        "═══════════════════════════════════════════════════════════════════",
    ])
    
    builder.print_info("\n".join(lines))
```

### 3. sys-audit 输出扩展

sys-audit 创建 issue 时，需要填充 `pending_targets` 和 `metrics`：

```python
def _create_bottleneck_issue(builder, diagnosis: DiagnosisReport) -> str:
    """创建瓶颈 issue，包含所有 pending targets"""
    
    # 收集所有 bottleneck 进程
    all_bottlenecks = []
    if diagnosis.primary_suspect:
        all_bottlenecks.append(diagnosis.primary_suspect)
    all_bottlenecks.extend(diagnosis.secondary_loads)
    
    # 按 impact_score 排序
    all_bottlenecks.sort(key=lambda g: g.impact_score, reverse=True)
    
    # 构建 pending_targets 和 metrics
    pending_targets = [g.comm for g in all_bottlenecks]
    metrics = {
        g.comm: {
            "cpu": g.total_cpu,
            "sys_cpu": g.kernel_cpu,
            "kernel_ratio": g.kernel_ratio,
            "pids": g.pid_count,
            "score": g.impact_score,
            "monopoly": g.monopoly,
            "diagnosis": g.diagnosis
        }
        for g in all_bottlenecks
    }
    
    # 创建 issue
    issue_id = builder.trace.add(
        desc=f"发现 {len(all_bottlenecks)} 个关键性能瓶颈",
        level="critical",
        hint="执行 bottleneck-trace 逐个分析",
        pending_targets=pending_targets,
        metrics=metrics
    )
    
    return issue_id
```

---

## CLI 参数扩展

```python
# cli/commands/composite/bottleneck_trace.py

def register_commands(subparsers):
    p = subparsers.add_parser(
        'bottleneck-trace',
        help='瓶颈深度追踪（支持从 sys-audit 继承问题）'
    )
    
    # 原有参数
    p.add_argument('--data', required=True, help='数据文件路径')
    p.add_argument('--comm', help='指定目标进程（可选）')
    p.add_argument('--top-n', type=int, default=10, help='热点分析数量')
    
    # 新增参数
    p.add_argument(
        '--next',
        action='store_true',
        help='分析 issues 中的下一个 pending target'
    )
    p.add_argument(
        '--issue-id',
        help='指定要继承的 issue ID（默认选择优先级最高的）'
    )
    p.add_argument(
        '--auto',
        action='store_true',
        help='强制使用自动识别模式（忽略 issues）'
    )
```

---

## 使用流程示例

### 完整诊断流程

```bash
# 1. 系统全景扫描
shecr sys-audit --data case_huge_samples.data
# 输出: [X0] 发现 4 个关键性能瓶颈
#       自动创建 ISS-001

# 2. 分析第一个瓶颈（自动继承 netstat）
shecr bottleneck-trace --data case_huge_samples.data
# 输出: 
#   ═══════════════════════════════════════════════════════════════════
#   BOTTLENECK-TRACE: 从 ISS-001 继承 4 个待分析瓶颈
#   ═══════════════════════════════════════════════════════════════════
#   按危害指数排序:
#     [1] netstat          Score: 431.0  CPU: 243.9%  ⚠️  高内核态 95%
#     [2] python3          Score: 282.2  CPU: 207.2%
#     [3] containerd-shim  Score: 225.2  CPU: 96.0%   ⚠️  高内核态 90%
#     [4] kubelet          Score: 205.5  CPU: 114.9%
#   
#   当前分析: netstat (危害指数最高)
#   ═══════════════════════════════════════════════════════════════════
#   [分析结果...]
#   
#   下一步: shecr bottleneck-trace --comm python3

# 3. 标记完成或继续分析
shecr trace complete --id ISS-001 --result "netstat: spinlock竞争..."
# 或
shecr bottleneck-trace --data case_huge_samples.data --next
# 或
shecr bottleneck-trace --data case_huge_samples.data --comm python3

# 4. 分析完所有 4 个瓶颈后
shecr trace issues
# 输出: [OPEN] 0 issues remaining

shecr trace finalize
# 输出: [READY] All issues resolved
```

---

## 兼容性考虑

| 场景 | 处理方式 |
|------|----------|
| 无 .shecr.json | 回退到自动识别模式 |
| issues 都已解决 | 回退到自动识别模式 |
| 同时指定 --comm 和 --next | --comm 优先级更高 |
| --auto 强制自动识别 | 忽略 issues |
| 旧版本 Trace 文档 | 忽略新字段，回退到自动识别 |

---

## 实现任务清单

- [ ] **Phase 1**: Trace 模型扩展
  - [ ] Issue dataclass 添加 `pending_targets`, `analyzed_targets`, `metrics` 字段
  - [ ] Trace 类添加 `get_next_pending_target()`, `mark_target_analyzed()` 方法
  
- [ ] **Phase 2**: sys-audit 修改
  - [ ] 创建 issue 时填充 pending_targets 和 metrics
  
- [ ] **Phase 3**: bottleneck-trace 修改
  - [ ] 添加 `--next`, `--issue-id`, `--auto` 参数
  - [ ] 实现继承逻辑（优先检查 issues）
  - [ ] 添加目标选择提示输出
  - [ ] 实现分析完成后自动更新 issue 状态
  
- [ ] **Phase 4**: 测试
  - [ ] 无 issues 时回退到自动识别
  - [ ] 有 issues 时正确继承
  - [ ] --next 参数正确选择下一个
  - [ ] --comm 参数优先级最高
  
- [ ] **Phase 5**: 文档更新
  - [ ] 更新 SKILL.md 中的使用示例
  - [ ] 更新 references/tools.md 中的命令说明

---

## 相关文档

- [Trace 机制设计](design-trace.md) - Trace 数据结构基础
- [Composite 层接口](interface-composite.md) - BottleneckTracer 类定义
- [CLI 层接口](interface-cli.md) - 命令注册规范
- [工具: bottleneck-trace](../report/tool-bottleneck-trace.md) - 工具详细说明
