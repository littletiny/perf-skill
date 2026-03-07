# CLI 层重构设计文档（3 人协作版）

> 创建时间: 2026-03-03  
> 预计工期: 5 天（并行 3 天 + 联调 2 天）  
> 关联文档: `design-three-tier-architecture.md`

---

## 1. 项目概览

### 1.1 重构目标

将散落在 **10 个文件**中的 CLI 逻辑集中化，建立清晰的四层架构：

```
┌─────────────────────────────────────────────────────────────┐
│  Layer 4: CLI (命令层)      ← 本次重构重点                   │
│  ├─ 统一入口 shecr.py                                      │
│  ├─ 参数解析与路由 cli/main.py                             │
│  ├─ 基础设施 cli/{decorators,builders}.py                  │
│  ├─ 分析命令 cli/commands/analysis/*.py  (6个)             │
│  ├─ 组合命令 cli/commands/composite/*.py (2个)             │
│  ├─ Trace命令 cli/commands/trace/*.py    (9个)             │
│  └─ 环境管理 cli/env.py                                    │
├─────────────────────────────────────────────────────────────┤
│  Layer 3: Analysis (分析层)  ← 清理 @command 装饰器          │
│  ├─ analysis/facade.py                                     │
│  ├─ analysis/{comm_top,hotspots,trace,anomalies,...}.py    │
│  └─ composite/{sys_audit,bottleneck_analyze}.py            │
├─────────────────────────────────────────────────────────────┤
│  Layer 2: Core (核心层)      ← 清理 CLI 代码                 │
│  ├─ core/engine.py                                         │
│  ├─ core/trace.py          (只保留 Trace 模型)             │
│  └─ core/output_models.py                                  │
├─────────────────────────────────────────────────────────────┤
│  Layer 1: Data (数据层)                                     │
└─────────────────────────────────────────────────────────────┘
```

### 1.2 团队分工

| 角色 | 负责人 | 交付物 | 依赖 |
|------|--------|--------|------|
| **A - 基础设施** | 待定 | `cli/` 包框架、`decorators.py`、`builders.py` | 无（Day 1 完成） |
| **B - 分析命令** | 待定 | 6 个分析命令迁移、`cli/commands/analysis/` | 依赖 A Day 1 |
| **C - Trace & 环境** | 待定 | 9 个 Trace 命令、`cli/env.py`、清理 `trace.py` | 依赖 A Day 1 |

---

## 2. 分工详情

### 2.1 人员 A：CLI 基础设施负责人

**职责**: 搭建 CLI 层骨架，提供基础设施供 B/C 使用

#### Day 1: 创建包结构

```
scripts/perf_toolkit/cli/
├── __init__.py              # 暴露主要接口
├── decorators.py            # @command 装饰器（从 core 迁移）
├── builders.py              # OutputBuilder（从 core 迁移）
├── main.py                  # 参数解析框架（预留接口）
├── env.py                   # 环境管理框架（预留接口）
└── commands/
    ├── __init__.py
    ├── analysis/
    │   └── __init__.py
    ├── composite/
    │   └── __init__.py
    └── trace/
        └── __init__.py
```

**具体任务清单**:

- [ ] **Task A1**: 创建目录结构
  - 参考下方「文件迁移清单」创建所有目录
  - 添加 `__init__.py` 文件

- [ ] **Task A2**: 迁移 `@command` 装饰器
  - 源文件: `core/command_decorator.py` (68行)
  - 目标: `cli/decorators.py`
  - 修改 import: `from .output_builder import OutputBuilder`
  - **验证**: 能成功 import

- [ ] **Task A3**: 迁移 `OutputBuilder`
  - 源文件: `core/output_builder.py` (350+行)
  - 目标: `cli/builders.py`
  - 修改 import 路径: `from ..core.trace import Trace` 等
  - **验证**: 能成功 import

- [ ] **Task A4**: 创建 `cli/main.py` 框架
  - 提供 `create_parser()` 函数（空壳，参数后续 B/C 填充）
  - 提供 `route_command()` 函数（空壳）
  - 提供 `main()` 入口函数
  - **关键接口约定**:
    ```python
    def route_command(command_name: str, engine, args):
        """
        命令路由 - B/C 需要在此注册自己的命令
        
        Args:
            command_name: 命令名称，如 'get-hotspots'
            engine: PerfExpertEngine 实例
            args: argparse.Namespace
        """
        # B 负责填充 analysis 命令
        # C 负责填充 trace/env 命令
        pass
    ```

- [ ] **Task A5**: 更新 `shecr.py`
  - 原文件备份为 `shecr.py.bak`
  - 重写为简单入口:
    ```python
    #!/usr/bin/env python3
    from perf_toolkit.cli.main import main
    if __name__ == "__main__":
        main()
    ```

**交付标准**:
- `python3 -c "from perf_toolkit.cli import decorators, builders; print('OK')"` 不报错
- `python3 scripts/shecr.py --help` 能运行（可能只有 help）

---

### 2.2 人员 B：分析命令迁移负责人

**职责**: 迁移 6 个分析命令到 `cli/commands/analysis/`

**依赖**: A 完成 Day 1 后才能开始

#### Day 2-3: 命令迁移

**具体任务清单**:

- [ ] **Task B1**: 创建命令注册接口（与 A 协作）
  - 在 `cli/main.py` 中添加 `register_analysis_commands(subparsers)`
  - 在 `cli/main.py` 的 `route_command()` 中添加分析命令路由

- [ ] **Task B2**: 迁移 `get-hotspots`
  - 源: `analysis/hotspots.py` 中的 `cmd_get_hotspots` 函数
  - 目标: `cli/commands/analysis/hotspots.py`
  - 步骤:
    1. 复制函数到新文件
    2. 更新 import: `from perf_toolkit.analysis.hotspots import HotspotsAnalyzer`
    3. 从原文件删除 `cmd_get_hotspots` 和 `@command` 装饰器
    4. 在 `main.py` 注册参数:
       ```python
       p = subparsers.add_parser('get-hotspots', ...)
       p.add_argument("--sort-by", ...)
       # ... 其他参数从 shecr.py 迁移
       ```
  - **验证**: `shecr get-hotspots --data xxx.data` 正常工作

- [ ] **Task B3**: 迁移 `find-callers`
  - 源: `analysis/trace.py` 中的 `cmd_trace_attribution`
  - 目标: `cli/commands/analysis/trace.py`
  - 注意: 文件名冲突，新文件命名为 `callers.py`
  - 从原文件删除 CLI 代码

- [ ] **Task B4**: 迁移 `detect-anomalies`
  - 源: `analysis/anomalies.py`
  - 目标: `cli/commands/analysis/anomalies.py`

- [ ] **Task B5**: 迁移 `cluster-paths`
  - 源: `analysis/path_clusters.py`
  - 目标: `cli/commands/analysis/path_clusters.py`

- [ ] **Task B6**: 迁移 `analyze-core-distribution`
  - 源: `analysis/core_distribution.py`
  - 目标: `cli/commands/analysis/core_dist.py`

- [ ] **Task B7**: 迁移 `get-comm-top`
  - 源: `analysis/comm_top.py`
  - 目标: `cli/commands/analysis/comm_top.py`

- [ ] **Task B8**: 清理 Analysis 层
  - 确保 6 个 `analysis/*.py` 文件只保留 `Analyzer` 类
  - 删除所有 `@command` 装饰器
  - 删除所有 `cmd_*` 函数
  - **验证**: `from perf_toolkit.analysis.hotspots import HotspotsAnalyzer` 仍可用

**交付标准**:
- 6 个分析命令全部可用: `shecr get-hotspots/find-callers/detect-anomalies/cluster-paths/analyze-core-distribution/get-comm-top`
- `analysis/*.py` 不再包含 CLI 代码

---

### 2.3 人员 C：Trace & 环境命令负责人

**职责**: 迁移 9 个 Trace 命令 + `shecr_wrap.py` 功能

**依赖**: A 完成 Day 1 后才能开始

#### Day 2: Trace 命令迁移

**具体任务清单**:

- [ ] **Task C1**: 创建命令注册接口（与 A 协作）
  - 在 `cli/main.py` 中添加 `register_trace_commands(subparsers)`
  - 在 `cli/main.py` 的 `route_command()` 中添加 trace 命令路由

- [ ] **Task C2**: 从 `core/trace.py` 提取命令
  - 源文件: `core/trace.py` (1000+行，包含 `Trace` 类 + 9 个 `cmd_doc_*`)
  - 提取以下函数到 `cli/commands/trace/`:
    | 函数 | 新文件 |
    |------|--------|
    | `cmd_doc_init` | `init.py` |
    | `cmd_doc_add` | `add.py` |
    | `cmd_doc_timeline` | `timeline.py` |
    | `cmd_doc_issues` | `issues.py` |
    | `cmd_doc_complete` | `complete.py` |
    | `cmd_doc_reopen` | `reopen.py` |
    | `cmd_doc_finalize` | `finalize.py` |
    | `cmd_doc_export` | `export.py` |
    | `cmd_doc_audit` | `audit.py` |

- [ ] **Task C3**: 精简 `core/trace.py`
  - 删除所有 `cmd_doc_*` 函数
  - 只保留 `Trace` 类（约 750 行）
  - **验证**: `from perf_toolkit.core import Trace` 仍可用

- [ ] **Task C4**: 注册 trace 子命令
  - 在 `main.py` 创建 `trace` 子命令组:
    ```python
    trace_parser = subparsers.add_parser('trace', help='Tracing commands')
    trace_sub = trace_parser.add_subparsers(dest='trace_cmd')
    # 注册 init/add/timeline/issues/complete/reopen/finalize/export/audit
    ```

#### Day 3: 环境管理迁移

- [ ] **Task C5**: 迁移 `shecr_wrap.py` 功能
  - 源文件: `shecr_wrap.py` (350+行)
  - 目标: `cli/env.py`
  - 迁移以下命令:
    - `cmd_init` → `cli/commands/env/init.py`
    - `cmd_use` → `cli/commands/env/use.py`
    - `cmd_list` → `cli/commands/env/list.py`
    - `cmd_status` → `cli/commands/env/status.py`
    - `cmd_exec` → 删除（不再需要，因为主入口统一了）

- [ ] **Task C6**: 在 `main.py` 注册环境命令
  - `shecr init --data-path xxx`
  - `shecr use xxx`
  - `shecr list`
  - `shecr status`

- [ ] **Task C7**: 删除 `shecr_wrap.py`
  - 确认所有功能已迁移
  - 删除文件
  - 更新文档（如果有提到 shecr_wrap 的地方）

**交付标准**:
- 9 个 trace 子命令可用: `shecr trace init/add/timeline/issues/complete/reopen/finalize/export/audit`
- 4 个环境命令可用: `shecr init/use/list/status`
- `core/trace.py` 只保留 `Trace` 类
- `shecr_wrap.py` 已删除

---

## 3. 协作接口约定

### 3.1 A → B/C 的交付物（Day 1 结束）

A 需要确保以下接口可用：

```python
# cli/decorators.py
from functools import wraps

def command(name: str, filters: list = None):
    """
    命令装饰器 - 统一处理样板代码
    
    Args:
        name: 命令名称（如 'get-hotspots'）
        filters: 过滤参数列表，None 表示使用全部 6 个
    
    Usage:
        @command("get-hotspots")
        def cmd_get_hotspots(builder, engine, args, samples):
            ...
    """
    ...

# cli/builders.py  
from perf_toolkit.core.engine import PerfExpertEngine

class OutputBuilder:
    """
    输出构建器 - 基于统一数据模型
    
    Args:
        engine: PerfExpertEngine 实例
        args: argparse namespace
        compact: 是否使用紧凑模式
        text_mode: 是否使用文本格式（默认 True）
    """
    def __init__(self, engine: PerfExpertEngine, args, compact: bool = False, text_mode: bool = True):
        ...
    
    def begin_command(self, command_name: str):
        """命令开始时调用"""
        ...
    
    def check_empty_samples(self, samples, filters: dict = None) -> bool:
        """检查空样本，如为空则自动输出并返回 True"""
        ...
    
    def assess_quality(self, samples):
        """评估数据质量"""
        ...
    
    def record_risk(self, level: str, desc: str, hint: str = "") -> str:
        """记录风险，返回 issue_id"""
        ...
    
    def print_output(self, output):
        """输出结果（自动选择 JSON 或文本格式）"""
        ...

# cli/main.py（框架）
import argparse
from perf_toolkit.core import PerfExpertEngine

def create_parser() -> argparse.ArgumentParser:
    """创建参数解析器 - A 提供框架，B/C 填充子命令"""
    parser = argparse.ArgumentParser(description="SHECR Diagnostic Toolkit")
    subparsers = parser.add_subparsers(dest="command")
    
    # B 和 C 将在此注册自己的命令
    # register_analysis_commands(subparsers)  # B 负责
    # register_trace_commands(subparsers)     # C 负责
    # register_env_commands(subparsers)       # C 负责
    
    return parser

def route_command(command_name: str, engine: PerfExpertEngine, args):
    """
    命令路由 - B/C 填充具体路由逻辑
    
    Args:
        command_name: 命令名称
        engine: PerfExpertEngine 实例
        args: argparse.Namespace
    """
    # B 负责填充 analysis 命令路由
    # C 负责填充 trace/env 命令路由
    pass

def main():
    """主入口"""
    parser = create_parser()
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    # 环境命令不需要 engine（C 负责处理）
    if args.command in ['init', 'use', 'list', 'status']:
        handle_env_command(args)
        return
    
    # Trace 子命令（C 负责处理）
    if args.command == 'trace':
        handle_trace_command(args)
        return
    
    # 分析命令需要 engine（B 负责处理）
    engine = PerfExpertEngine(args.data, freq=getattr(args, 'freq', 19))
    route_command(args.command, engine, args)
```

### 3.2 B/C 向 A 提供的接口（Day 2 开始填充）

B 需要提供：
```python
# cli/commands/analysis/__init__.py
COMMANDS = {
    'get-hotspots': 'cli.commands.analysis.hotspots.cmd_get_hotspots',
    'find-callers': 'cli.commands.analysis.callers.cmd_trace_attribution',
    'detect-anomalies': 'cli.commands.analysis.anomalies.cmd_detect_anomalies',
    'cluster-paths': 'cli.commands.analysis.path_clusters.cmd_cluster_paths',
    'analyze-core-distribution': 'cli.commands.analysis.core_dist.cmd_analyze_core_distribution',
    'get-comm-top': 'cli.commands.analysis.comm_top.cmd_get_comm_top',
}

def register_commands(subparsers):
    """注册分析命令参数"""
    # p = subparsers.add_parser('get-hotspots', ...)
    # p.add_argument(...)
    ...
```

C 需要提供：
```python
# cli/commands/trace/__init__.py
COMMANDS = {
    'trace init': 'cli.commands.trace.init.cmd_doc_init',
    'trace add': 'cli.commands.trace.add.cmd_doc_add',
    # ... 其他 7 个
}

# cli/commands/env/__init__.py  
COMMANDS = {
    'init': 'cli.commands.env.init.cmd_init',
    'use': 'cli.commands.env.use.cmd_use',
    'list': 'cli.commands.env.list.cmd_list',
    'status': 'cli.commands.env.status.cmd_status',
}
```

### 3.3 Git 协作策略

为了避免冲突，建议按以下分支策略：

```
main
├── feature/cli-base        (A 负责，Day 1)
│   └── 创建 cli/ 目录，迁移 decorators/builders
├── feature/cli-analysis    (B 负责，依赖 A Day 1)
│   └── 迁移 6 个分析命令
├── feature/cli-trace       (C 负责，依赖 A Day 1)
│   └── 迁移 9 个 trace 命令 + 环境命令
└── feature/cli-integration (A/B/C 共同，Day 4-5)
    └── 合并所有分支，联调测试
```

**关键时间点**:
- **Day 1 结束**: A 完成 `feature/cli-base`，合并到 main
- **Day 2 开始**: B/C 从 main 拉取最新代码，分别创建自己的分支
- **Day 3 结束**: B/C 完成各自任务，提交 PR
- **Day 4-5**: 联合联调，处理冲突

---

## 4. 联调检查清单（Day 4-5）

三人一起完成以下验证：

### 4.1 基础功能验证

```bash
# 1. 帮助信息
python3 scripts/shecr.py --help

# 2. 分析命令（B 负责验证）
shecr get-hotspots --data tests/perfdata/new_format/case_test.data
shecr find-callers --data tests/perfdata/new_format/case_test.data --target pthread_mutex_lock
shecr detect-anomalies --data tests/perfdata/new_format/case_test.data
shecr cluster-paths --data tests/perfdata/new_format/case_test.data
shecr analyze-core-distribution --data tests/perfdata/new_format/case_test.data
shecr get-comm-top --data tests/perfdata/new_format/case_test.data

# 3. Trace 命令（C 负责验证）
shecr trace init --data tests/perfdata/new_format/case_test.data
shecr trace add --desc "测试 issue"
shecr trace timeline
shecr trace issues

# 4. 环境命令（C 负责验证）
shecr init --data-path tests/perfdata/new_format/case_test.data
shecr status
shecr list

# 5. 运行自动化测试（A 负责）
python3 tests/run_tests.py
```

### 4.2 清理验证

- [ ] `core/command_decorator.py` 已删除（A 验证）
- [ ] `core/output_builder.py` 已删除（A 验证）
- [ ] `core/trace.py` 只保留 `Trace` 类，无 CLI 函数（C 验证）
- [ ] `analysis/*.py` 无 `@command` 和 `cmd_*`（B 验证）
- [ ] `shecr_wrap.py` 已删除（C 验证）

### 4.3 文档更新

- [ ] 更新 `AGENTS.md` 目录结构（A 负责）
- [ ] 更新 `SKILL.md`（如有需要，A 负责）
- [ ] 更新 `CHANGELOG.md`（A 负责）

---

## 5. 风险预案

| 风险 | 影响 | 预案 |
|------|------|------|
| A Day 1 延期 | B/C 无法开始 | A 优先完成 `decorators.py` 和 `builders.py`，`main.py` 可简化 |
| import 循环依赖 | 运行时错误 | B/C 只从 `cli/` 导入 `decorators/builders`，不反向导入 |
| 参数冲突 | 两个命令参数同名但含义不同 | B/C 及时沟通，使用前缀如 `--trace-format` vs `--output-format` |
| 测试失败 | 功能回归 | Day 4 预留时间修复，如无法修复则回滚该命令 |

---

## 6. 附录

### 6.1 文件变更总表

| 原路径 | 新路径 | 负责人 | 操作 |
|--------|--------|--------|------|
| `core/command_decorator.py` | `cli/decorators.py` | A | 移动 |
| `core/output_builder.py` | `cli/builders.py` | A | 移动 |
| `core/trace.py` (CLI 部分) | `cli/commands/trace/*.py` | C | 拆分 |
| `analysis/hotspots.py` (CLI) | `cli/commands/analysis/hotspots.py` | B | 移动 |
| `analysis/trace.py` (CLI) | `cli/commands/analysis/callers.py` | B | 移动 |
| `analysis/anomalies.py` (CLI) | `cli/commands/analysis/anomalies.py` | B | 移动 |
| `analysis/path_clusters.py` (CLI) | `cli/commands/analysis/path_clusters.py` | B | 移动 |
| `analysis/core_distribution.py` (CLI) | `cli/commands/analysis/core_dist.py` | B | 移动 |
| `analysis/comm_top.py` (CLI) | `cli/commands/analysis/comm_top.py` | B | 移动 |
| `composite/sys_audit.py` (CLI) | `cli/commands/composite/sys_audit.py` | B | 移动 |
| `composite/bottleneck_analyze.py` (CLI) | `cli/commands/composite/bottleneck_analyze.py` | B | 移动 |
| `shecr_wrap.py` | `cli/commands/env/*.py` | C | 拆分后删除 |
| `shecr.py` | `shecr.py` | A | 重写为简单入口 |

### 6.2 每日站会检查点

**Day 1 站会** (A 汇报):
- [ ] 目录结构创建完成
- [ ] `decorators.py` 迁移完成
- [ ] `builders.py` 迁移完成

**Day 2 站会** (B/C 汇报):
- [ ] B: 前 3 个分析命令迁移完成
- [ ] C: 前 5 个 trace 命令迁移完成

**Day 3 站会** (B/C 汇报):
- [ ] B: 所有分析命令迁移完成
- [ ] C: 所有 trace + 环境命令迁移完成

**Day 4 站会** (共同):
- [ ] 分支合并冲突解决
- [ ] 基础功能验证通过

**Day 5 站会** (共同):
- [ ] 所有自动化测试通过
- [ ] 文档更新完成
- [ ] 代码审查完成
