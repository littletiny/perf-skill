# Risk 消息展示自定义设计文档

> 设计目标：极简 Risk 消息展示，支持从 init 配置导入文案模板
> 
> 版本: 1.3
> 创建时间: 2026-03-02

---

## 核心原则

**极简至上**
- 纯文本，无图标
- 无缩进，无层级
- 扁平结构，一行或两行
- 级别用大写标签

**配置驱动**
- 文案模板在 init 时注入
- 支持从配置文件加载
- 运行时零代码修改

**统一输出**
- 分析工具（analysis）和追踪工具（trace）共享同一套格式
- 配置一处定义，全局生效

---

## 展示格式

### 标准格式（推荐）

```
[CRITICAL] 锁竞争占比 79.84%，系统严重瓶颈
→ find-callers --target 'pthread_mutex_lock'
```

```
[WARNING] 发现 2 个高内核态进程未分析 [MULTI_HIGH_KERNEL]
→ cluster-symbols --comm containerd-shim
```

```
[INFO] 数据质量良好，分析结果可信
```

### 简洁格式

```
[CRITICAL] 锁竞争占比 79.84%，系统严重瓶颈
```

### 单行格式

```
[WARNING] 发现 2 个高内核态进程未分析 → cluster-symbols --comm containerd-shim
```

### Trace 专用格式

Trace 输出使用相同的格式系统，但针对 issue 列表有特殊布局：

**Issue 列表（standard）**:
```
[OPEN] 2 issues pending

[ISS-001] [WARNING] netstat 高内核态 94.7%
→ cluster-symbols --comm netstat

[ISS-002] [CRITICAL] 锁竞争占比 79.84%
→ find-callers --target 'pthread_mutex_lock'
```

**Issue 列表（compact）**:
```
[OPEN] ISS-001 [WARNING] netstat 高内核态 94.7%
[OPEN] ISS-002 [CRITICAL] 锁竞争占比 79.84%
```

**Timeline 格式**:
```
[1] 10:05:00 get-comm-top
[WARNING] 发现 2 个高内核态进程未分析
→ cluster-symbols --comm netstat

[2] 10:10:00 cluster-symbols
[INFO] 分析完成，无新风险
```

---

## 配置文件

```yaml
# ~/.config/spear/risk.yaml 或 .spear/risk.yaml

risk:
  # 格式: standard | compact | oneline
  format: standard
  
  # 颜色（ANSI 码，空字符串表示无色）
  colors:
    critical: "\033[91m"   # 红
    warning: "\033[93m"    # 黄
    info: "\033[94m"       # 蓝
    reset: "\033[0m"
  
  # 文案模板
  templates:
    # 基础 risk 模板
    message: "[{level}] {message}{pattern_suffix}"
    pattern_suffix: " [{patterns}]"
    hint: "→ {hint}"
    oneline: "[{level}] {message} → {hint}"
    
    # trace 专用模板
    issue_id: "[{id}]"
    issue_open: "[OPEN] {id} [{level}] {desc}"
    issue_resolved: "[RESOLVED] {id} [{level}] {desc}"
    timeline_header: "[{seq}] {time} {command}"
  
  # 字段显示开关
  show:
    message: true
    hint: true
    patterns: false
    pending_targets: false
    action_required: false

# 模式覆盖
modes:
  ci:
    colors:
      critical: ""
      warning: ""
      info: ""
      reset: ""
  
  compact:
    format: compact
    templates:
      message: "[{level}] {message}"
```

---

## 代码实现

### 配置类

```python
# core/risk_config.py

import os
import yaml
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, Any, Optional


@dataclass
class RiskConfig:
    """Risk/Trace 展示配置"""
    format: str = "standard"
    colors: Dict[str, str] = field(default_factory=lambda: {
        "critical": "\033[91m",
        "warning": "\033[93m",
        "info": "\033[94m",
        "reset": "\033[0m"
    })
    templates: Dict[str, str] = field(default_factory=lambda: {
        # 基础模板
        "message": "[{level}] {message}{pattern_suffix}",
        "pattern_suffix": " [{patterns}]",
        "hint": "→ {hint}",
        "oneline": "[{level}] {message} → {hint}",
        # Trace 专用
        "issue_id": "[{id}]",
        "issue_open": "[OPEN] {id} [{level}] {desc}",
        "issue_resolved": "[RESOLVED] {id} [{level}] {desc}",
        "timeline_header": "[{seq}] {time} {command}",
    })
    show: Dict[str, bool] = field(default_factory=lambda: {
        "message": True,
        "hint": True,
        "patterns": False,
        "pending_targets": False,
        "action_required": False,
    })
    
    @classmethod
    def load(cls, explicit_path: Optional[str] = None) -> 'RiskConfig':
        """加载配置，按优先级合并"""
        config = cls()
        
        # 搜索路径（按优先级）
        paths = [
            Path.home() / '.config' / 'spear' / 'risk.yaml',
            Path('.spear/risk.yaml'),
        ]
        
        # 加载所有存在的配置（先加载的会被后加载的覆盖）
        for path in reversed(paths):  # 反转，让用户目录优先级更低
            if path.exists():
                if loaded := cls._from_file(path):
                    config._merge(loaded)
        
        # 环境变量指定的配置（最高优先级）
        if env_path := os.getenv('SPEAR_RISK_CONFIG'):
            if Path(env_path).exists():
                if loaded := cls._from_file(Path(env_path)):
                    config._merge(loaded)
        
        # 显式指定的配置
        if explicit_path and Path(explicit_path).exists():
            if loaded := cls._from_file(Path(explicit_path)):
                config._merge(loaded)
        
        return config
    
    @classmethod
    def _from_file(cls, path: Path) -> Optional['RiskConfig']:
        """从文件加载"""
        try:
            with open(path) as f:
                data = yaml.safe_load(f)
            if not data or 'risk' not in data:
                return None
            return cls._from_dict(data['risk'])
        except Exception:
            return None
    
    @classmethod
    def _from_dict(cls, data: Dict) -> 'RiskConfig':
        return cls(
            format=data.get('format', 'standard'),
            colors={**cls().colors, **data.get('colors', {})},
            templates={**cls().templates, **data.get('templates', {})},
            show={**cls().show, **data.get('show', {})},
        )
    
    def _merge(self, other: 'RiskConfig'):
        """合并配置"""
        if other.format:
            self.format = other.format
        self.colors.update(other.colors)
        self.templates.update(other.templates)
        self.show.update(other.show)
    
    def apply_mode(self, mode: str):
        """应用模式覆盖"""
        # 从配置文件中查找 modes 部分
        for path in [Path('.spear/risk.yaml'), Path.home() / '.config' / 'spear' / 'risk.yaml']:
            if not path.exists():
                continue
            try:
                with open(path) as f:
                    data = yaml.safe_load(f)
                if 'modes' in data and mode in data['modes']:
                    mode_cfg = self._from_dict(data['modes'][mode])
                    self._merge(mode_cfg)
                    break
            except Exception:
                continue


# 全局配置实例（延迟加载）
_risk_config = None

def get_risk_config(explicit_path: str = None, mode: str = None) -> RiskConfig:
    """获取全局 Risk 配置"""
    global _risk_config
    if _risk_config is None:
        _risk_config = RiskConfig.load(explicit_path)
    if mode:
        _risk_config.apply_mode(mode)
    return _risk_config
```

### Risk 渲染引擎（分析工具使用）

```python
# core/risk_renderer.py

from typing import List, Dict, Any
from .risk_config import RiskConfig


class RiskRenderer:
    """Risk 消息渲染器"""
    
    def __init__(self, config: RiskConfig = None):
        self.cfg = config or RiskConfig()
    
    def render(self, risk: Dict[str, Any]) -> List[str]:
        """渲染 Risk 信息"""
        level = risk.get('level', 'none')
        if level == 'none':
            return []
        
        fmt = self.cfg.format
        if fmt == 'compact':
            return self._render_compact(risk, level)
        elif fmt == 'oneline':
            return self._render_oneline(risk, level)
        else:  # standard
            return self._render_standard(risk, level)
    
    def _render_standard(self, risk: Dict, level: str) -> List[str]:
        """标准格式: 两行"""
        lines = []
        level_upper = level.upper()
        color = self.cfg.colors.get(level, '')
        reset = self.cfg.colors.get('reset', '')
        
        # 第1行: [LEVEL] message [patterns]
        message = risk.get('message', '')
        pattern_suffix = ''
        
        if self.cfg.show.get('patterns'):
            patterns = risk.get('patterns', [])
            if patterns:
                tpl = self.cfg.templates.get('pattern_suffix', ' [{patterns}]')
                pattern_suffix = tpl.format(patterns=','.join(patterns))
        
        tpl = self.cfg.templates.get('message', '[{level}] {message}{pattern_suffix}')
        line = tpl.format(level=level_upper, message=message, pattern_suffix=pattern_suffix)
        
        if color:
            line = f"{color}{line}{reset}"
        lines.append(line)
        
        # 第2行: hint
        if self.cfg.show.get('hint'):
            hint = risk.get('hint', '')
            if hint:
                tpl = self.cfg.templates.get('hint', '→ {hint}')
                lines.append(tpl.format(hint=hint))
        
        return lines
    
    def _render_compact(self, risk: Dict, level: str) -> List[str]:
        """简洁格式: 仅一行"""
        level_upper = level.upper()
        color = self.cfg.colors.get(level, '')
        reset = self.cfg.colors.get('reset', '')
        message = risk.get('message', '')
        
        line = f"[{level_upper}] {message}"
        if color:
            line = f"{color}{line}{reset}"
        return [line]
    
    def _render_oneline(self, risk: Dict, level: str) -> List[str]:
        """单行格式"""
        level_upper = level.upper()
        color = self.cfg.colors.get(level, '')
        reset = self.cfg.colors.get('reset', '')
        message = risk.get('message', '')
        hint = risk.get('hint', '')
        
        tpl = self.cfg.templates.get('oneline', '[{level}] {message} → {hint}')
        line = tpl.format(level=level_upper, message=message, hint=hint)
        
        if color:
            line = f"{color}{line}{reset}"
        return [line]
    
    def render_to_string(self, risk: Dict[str, Any]) -> str:
        return '\n'.join(self.render(risk))
```

### Trace 渲染引擎（追踪工具使用）

```python
# core/trace_renderer.py

from typing import List, Dict, Any
from .risk_config import RiskConfig


class TraceRenderer:
    """Trace 输出渲染器 - 使用 RiskConfig 配置"""
    
    def __init__(self, config: RiskConfig = None):
        self.cfg = config or RiskConfig()
    
    # =====================================================================
    # Issue 渲染
    # =====================================================================
    
    def render_issue(self, issue: Dict[str, Any], compact: bool = False) -> List[str]:
        """渲染单个 issue"""
        if compact or self.cfg.format == 'compact':
            return self._render_issue_compact(issue)
        return self._render_issue_standard(issue)
    
    def _render_issue_standard(self, issue: Dict) -> List[str]:
        """标准格式渲染 issue"""
        lines = []
        issue_id = issue.get('id', 'ISS-???')
        level = issue.get('level', 'warning')
        desc = issue.get('desc', '')
        status = issue.get('status', 'open')
        
        color = self.cfg.colors.get(level, '')
        reset = self.cfg.colors.get('reset', '')
        
        # Issue 标题行
        if status == 'resolved':
            tpl = self.cfg.templates.get('issue_resolved', '[RESOLVED] {id} [{level}] {desc}')
        else:
            tpl = self.cfg.templates.get('issue_open', '[OPEN] {id} [{level}] {desc}')
        
        line = tpl.format(id=issue_id, level=level.upper(), desc=desc)
        if color:
            line = f"{color}{line}{reset}"
        lines.append(line)
        
        # Hint（如果有且未解决）
        if status != 'resolved':
            hint = issue.get('hint', '')
            if hint:
                tpl = self.cfg.templates.get('hint', '→ {hint}')
                lines.append(tpl.format(hint=hint))
        else:
            # 显示结果
            result = issue.get('result', '')
            if result:
                lines.append(f"→ {result}")
        
        return lines
    
    def _render_issue_compact(self, issue: Dict) -> List[str]:
        """简洁格式渲染 issue"""
        issue_id = issue.get('id', 'ISS-???')
        level = issue.get('level', 'warning')
        desc = issue.get('desc', '')
        status = issue.get('status', 'open')
        
        color = self.cfg.colors.get(level, '')
        reset = self.cfg.colors.get('reset', '')
        
        status_tag = "[RESOLVED]" if status == 'resolved' else "[OPEN]"
        line = f"{status_tag} {issue_id} [{level.upper()}] {desc}"
        
        if color:
            line = f"{color}{line}{reset}"
        return [line]
    
    def render_issue_list(self, issues: List[Dict], title: str = None) -> List[str]:
        """渲染 issue 列表"""
        lines = []
        
        # 标题
        if title:
            lines.append(title)
        
        if not issues:
            lines.append("(No issues)")
            return lines
        
        # 按格式渲染
        compact = self.cfg.format == 'compact'
        for issue in issues:
            lines.extend(self.render_issue(issue, compact))
            if not compact:
                lines.append("")  # 标准格式：issue 之间空行
        
        return lines
    
    # =====================================================================
    # Timeline 渲染
    # =====================================================================
    
    def render_timeline_record(self, record: Dict) -> List[str]:
        """渲染 timeline 单条记录"""
        lines = []
        seq = record.get('seq', 0)
        ts = record.get('timestamp', '')
        cmd = record.get('command', '')
        
        # 简化时间显示
        time_str = ts.split('T')[1].split('.')[0] if 'T' in ts else ts[:8]
        
        # Header
        tpl = self.cfg.templates.get('timeline_header', '[{seq}] {time} {command}')
        lines.append(tpl.format(seq=seq, time=time_str, command=cmd))
        
        # Findings
        for finding in record.get('findings', []):
            ftype = finding.get('type', '')
            if ftype == 'risk_created':
                level = finding.get('level', 'warning')
                color = self.cfg.colors.get(level, '')
                reset = self.cfg.colors.get('reset', '')
                issue_id = finding.get('issue_id', '')
                desc = finding.get('desc', '')
                line = f"[{level.upper()}] {issue_id}: {desc}"
                if color:
                    line = f"{color}{line}{reset}"
                lines.append(line)
            elif ftype == 'issue_resolved':
                issue_id = finding.get('issue_id', '')
                result = finding.get('result', '')
                lines.append(f"[RESOLVED] {issue_id}: {result}")
            elif ftype == 'info':
                msg = finding.get('message', '')
                lines.append(f"[INFO] {msg}")
        
        return lines
    
    def render_timeline(self, timeline: List[Dict]) -> List[str]:
        """渲染完整 timeline"""
        lines = []
        for record in timeline:
            lines.extend(self.render_timeline_record(record))
            lines.append("")  # 记录之间空行
        return lines
    
    # =====================================================================
    # Summary 渲染
    # =====================================================================
    
    def render_summary(self, summary: Dict) -> List[str]:
        """渲染摘要"""
        return [
            f"Commands: {summary.get('total_commands', 0)}",
            f"Open: {summary.get('open_issues', 0)}",
            f"Resolved: {summary.get('resolved_issues', 0)}",
        ]
```

### Trace 类集成

```python
# core/trace.py (修改部分)

from .risk_config import RiskConfig, get_risk_config
from .trace_renderer import TraceRenderer


class Trace:
    """Trace v2.0 - 诊断过程追踪"""
    
    def __init__(self, path: Optional[str] = None, config: RiskConfig = None):
        self.path = path or self._find_doc()
        self.data = self._load()
        self._current_seq = None
        
        # 渲染配置
        self.config = config or get_risk_config()
        self.renderer = TraceRenderer(self.config)
    
    def set_config(self, config: RiskConfig):
        """设置配置（用于动态切换）"""
        self.config = config
        self.renderer = TraceRenderer(config)
    
    # =====================================================================
    # CLI 输出方法（使用 renderer）
    # =====================================================================
    
    def format_issues(self, status: str = 'all') -> str:
        """格式化 issue 列表（用于 CLI 输出）"""
        lines = []
        
        if status in ['all', 'open']:
            open_issues = self.get_open_issues()
            if open_issues:
                title = f"[OPEN] {len(open_issues)} issues pending"
                lines.extend(self.renderer.render_issue_list(open_issues, title))
        
        if status in ['all', 'resolved']:
            resolved_issues = self.get_resolved_issues()
            if resolved_issues:
                title = f"[RESOLVED] {len(resolved_issues)} issues"
                lines.extend(self.renderer.render_issue_list(resolved_issues, title))
        
        return '\n'.join(lines)
    
    def format_timeline(self) -> str:
        """格式化 timeline（用于 CLI 输出）"""
        timeline = self.get_timeline()
        if not timeline:
            return "(No timeline records)"
        return '\n'.join(self.renderer.render_timeline(timeline))
```

### CLI 命令更新

```python
# core/trace.py - CLI 函数

def cmd_doc_issues(args):
    """查看 issues 状态 - 使用 RiskConfig 格式"""
    # 加载配置
    config = get_risk_config(
        explicit_path=getattr(args, 'risk_config', None),
        mode=getattr(args, 'risk_style', None)
    )
    
    doc = Trace(config=config)
    status_filter = getattr(args, 'status', 'all')
    
    # 使用统一格式输出
    output = doc.format_issues(status_filter)
    if output:
        print(output)
    else:
        print("(No issues)")
    
    # 提示用法
    summary = doc.get_summary()
    if summary['open_issues'] > 0:
        print(f"\nUsage: spear trace complete --id ISS-001 --result '分析结果'")


def cmd_doc_timeline(args):
    """查看时间线 - 使用 RiskConfig 格式"""
    config = get_risk_config(
        explicit_path=getattr(args, 'risk_config', None),
        mode=getattr(args, 'risk_style', None)
    )
    
    doc = Trace(config=config)
    print(doc.format_timeline())
    
    # 摘要
    summary = doc.get_summary()
    print(f"ISSUES: {summary['resolved_issues']} resolved, {summary['open_issues']} open")
```

### OutputBuilder 集成

```python
# core/output_builder.py

from .risk_config import get_risk_config
from .risk_renderer import RiskRenderer


class OutputBuilder:
    def __init__(self, engine, args, compact: bool = False, text_mode: bool = True):
        self.engine = engine
        self.args = args
        self.text_mode = text_mode
        
        # 加载 Risk 配置（init 时完成，全局共享）
        self.risk_config = get_risk_config(
            explicit_path=getattr(args, 'risk_config', None)
        )
        
        # 应用命令行覆盖
        if fmt := getattr(args, 'risk_format', None):
            self.risk_config.format = fmt
        if style := getattr(args, 'risk_style', None):
            self.risk_config.apply_mode(style)
        
        # 禁用颜色（CI 环境）
        if os.getenv('NO_COLOR') or os.getenv('SPEAR_NO_COLOR'):
            self.risk_config.colors = {k: '' for k in self.risk_config.colors}
        
        self.risk_renderer = RiskRenderer(self.risk_config)
        
        # Trace 共享同一配置
        self._trace = None
```

---

## CLI 参数

```python
def add_risk_args(parser):
    """共享的 Risk 格式参数"""
    parser.add_argument(
        '--risk-config',
        metavar='PATH',
        help='Risk 配置文件路径'
    )
    
    parser.add_argument(
        '--risk-format',
        choices=['standard', 'compact', 'oneline'],
        help='Risk 展示格式'
    )
    
    parser.add_argument(
        '--risk-style',
        choices=['default', 'ci'],
        help='Risk 样式预设 (ci: 无颜色)'
    )
```

**应用到所有命令**:
```python
# 分析工具
spear get-comm-top --data perf.data --risk-format compact
spear cluster-symbols --comm nginx --risk-style ci

# Trace 工具（共享相同参数）
spear trace issues --risk-format compact
spear trace timeline --risk-style ci
```

---

## 使用示例

### 1. 全局配置

```yaml
# .spear/risk.yaml
risk:
  format: standard
  colors:
    critical: "\033[91m"
    warning: "\033[93m"
    info: "\033[94m"
    reset: "\033[0m"
```

**分析工具输出**:
```
[WARNING] 发现 2 个高内核态进程未分析
→ cluster-symbols --comm containerd-shim
```

**Trace 输出**:
```
[OPEN] 2 issues pending

[OPEN] [ISS-001] [WARNING] netstat 高内核态 94.7%
→ cluster-symbols --comm netstat

[OPEN] [ISS-002] [CRITICAL] 锁竞争占比 79.84%
→ find-callers --target 'pthread_mutex_lock'
```

### 2. CI 环境配置

```yaml
# .spear/risk.yaml
modes:
  ci:
    colors:
      critical: ""
      warning: ""
      info: ""
      reset: ""
```

```bash
export SPEAR_RISK_STYLE=ci
spear get-comm-top --data perf.data
spear trace issues
```

**输出**:
```
[WARNING] 发现 2 个高内核态进程未分析
-> cluster-symbols --comm containerd-shim
```

### 3. 简洁模式

```bash
spear trace issues --risk-format compact
```

**输出**:
```
[OPEN] ISS-001 [WARNING] netstat 高内核态 94.7%
[OPEN] ISS-002 [CRITICAL] 锁竞争占比 79.84%
```

---

## 文件结构

```
scripts/perf_toolkit/core/
├── risk_config.py       # 配置加载器（分析 + Trace 共享）
├── risk_renderer.py     # 分析工具渲染器
├── trace_renderer.py    # Trace 专用渲染器
├── trace.py             # Trace 类（集成配置）
└── output_builder.py    # 分析工具（集成配置）
```

---

## 实施步骤

1. **创建 `risk_config.py`** - 统一配置加载
2. **创建 `risk_renderer.py`** - 分析工具渲染
3. **创建 `trace_renderer.py`** - Trace 专用渲染
4. **修改 `trace.py`** - 集成配置和渲染器
5. **修改 `output_builder.py`** - 共享配置系统
6. **添加全局 CLI 参数** - `--risk-config`, `--risk-format`, `--risk-style`
