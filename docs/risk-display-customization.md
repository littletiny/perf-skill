# Risk 消息展示自定义设计文档

> 设计目标：极简 Risk 消息展示，支持从 init 配置导入文案模板
>
> 版本: 1.6
> 创建时间: 2026-03-02

---

## 设计概览

### 数据流

```
[Analysis 工具]
    ↓ 输出 Risk
    ↓ 自动捕获 (_auto_record_risk_from_output)
[Trace 存储] ← 原始数据 (level/message/hint) → .spear.json
    ↓ 展示 (spear trace issues/timeline)
[终端输出] ← 使用 RiskDisplayConfig 格式化
```

### 配置来源（优先级从高到低）

1. 命令行参数 `--risk-config PATH`
2. 环境变量 `SPEAR_RISK_CONFIG`
3. 当前目录 `.spear/risk.json`
4. 用户目录 `~/.config/spear/risk.json`
5. **内置默认配置**（代码中硬编码）

---

## 配置文件

### 文件格式（JSON）

```json
{
  "risk": {
    "colors": {
      "critical": "\u001b[91m",
      "warning": "\u001b[93m",
      "info": "\u001b[94m",
      "reset": "\u001b[0m"
    },
    "templates": {
      "issue_open": "[OPEN] [{id}] [{level}] {desc}",
      "issue_resolved": "[RESOLVED] [{id}] [{level}] {desc}",
      "hint": "→ {hint}",
      "result": "→ {result}",
      "list_header_open": "[OPEN] {count} issues pending",
      "list_header_resolved": "[RESOLVED] {count} issues",
      "list_header_all": "[ALL] {open_count} open, {resolved_count} resolved",
      "timeline_command": "[{seq}] {time} {command}",
      "timeline_finding_created": "[{level}] {issue_id}: {desc}",
      "timeline_finding_resolved": "[RESOLVED] {issue_id}: {result}"
    },
    "show": {
      "hint": true,
      "result": true
    }
  },
  "modes": {
    "ci": {
      "colors": {
        "critical": "",
        "warning": "",
        "info": "",
        "reset": ""
      }
    },
    "compact": {
      "templates": {
        "issue_open": "[OPEN] {id} [{level}] {desc}",
        "issue_resolved": "[RESOLVED] {id} [{level}] {desc}"
      },
      "show": {
        "hint": false,
        "result": false
      }
    }
  }
}
```

### 默认配置文件位置

项目内置默认配置：
```
config/risk-default.json
```

安装时复制到用户目录：
```
~/.config/spear/risk.json
```

### 加载优先级

```python
def load_config():
    # 1. 内置默认
    config = load_builtin_default()

    # 2. 用户默认（如果存在）
    if exists("~/.config/spear/risk.json"):
        merge(config, load("~/.config/spear/risk.json"))

    # 3. 项目本地（如果存在）
    if exists(".spear/risk.json"):
        merge(config, load(".spear/risk.json"))

    # 4. 环境变量指定
    if env_path := getenv("SPEAR_RISK_CONFIG"):
        merge(config, load(env_path))

    return config
```

---

## 代码实现

### 1. 默认配置文件 (config/risk-default.json)

```json
{
  "_comment": "Default risk display configuration for SPEAR",
  "risk": {
    "colors": {
      "critical": "\u001b[91m",
      "warning": "\u001b[93m",
      "info": "\u001b[94m",
      "reset": "\u001b[0m"
    },
    "templates": {
      "issue_open": "[OPEN] [{id}] [{level}] {desc}",
      "issue_resolved": "[RESOLVED] [{id}] [{level}] {desc}",
      "hint": "→ {hint}",
      "result": "→ {result}",
      "list_header_open": "[OPEN] {count} issues pending",
      "list_header_resolved": "[RESOLVED] {count} issues",
      "list_header_all": "[ALL] {open_count} open, {resolved_count} resolved",
      "timeline_command": "[{seq}] {time} {command}",
      "timeline_finding_created": "[{level}] {issue_id}: {desc}",
      "timeline_finding_resolved": "[RESOLVED] {issue_id}: {result}",
      "timeline_info": "[INFO] {message}"
    },
    "show": {
      "hint": true,
      "result": true
    }
  },
  "modes": {
    "ci": {
      "colors": {
        "critical": "",
        "warning": "",
        "info": "",
        "reset": ""
      }
    },
    "compact": {
      "templates": {
        "issue_open": "[OPEN] {id} [{level}] {desc}",
        "issue_resolved": "[RESOLVED] {id} [{level}] {desc}"
      },
      "show": {
        "hint": false,
        "result": false
      }
    }
  }
}
```

### 2. 配置加载器 (core/risk_config.py)

```python
#!/usr/bin/env python3
"""Risk 展示配置 - JSON 格式，支持内置默认"""

import json
import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, Optional


# 内置默认配置（硬编码，确保无配置文件也能运行）
DEFAULT_CONFIG = {
    "colors": {
        "critical": "\033[91m",
        "warning": "\033[93m",
        "info": "\033[94m",
        "reset": "\033[0m"
    },
    "templates": {
        "issue_open": "[OPEN] [{id}] [{level}] {desc}",
        "issue_resolved": "[RESOLVED] [{id}] [{level}] {desc}",
        "hint": "→ {hint}",
        "result": "→ {result}",
        "list_header_open": "[OPEN] {count} issues pending",
        "list_header_resolved": "[RESOLVED] {count} issues",
        "list_header_all": "[ALL] {open_count} open, {resolved_count} resolved",
        "timeline_command": "[{seq}] {time} {command}",
        "timeline_finding_created": "[{level}] {issue_id}: {desc}",
        "timeline_finding_resolved": "[RESOLVED] {issue_id}: {result}",
        "timeline_info": "[INFO] {message}"
    },
    "show": {
        "hint": True,
        "result": True
    }
}


@dataclass
class RiskDisplayConfig:
    """Risk 展示配置"""
    colors: Dict[str, str] = field(default_factory=lambda: DEFAULT_CONFIG["colors"].copy())
    templates: Dict[str, str] = field(default_factory=lambda: DEFAULT_CONFIG["templates"].copy())
    show: Dict[str, bool] = field(default_factory=lambda: DEFAULT_CONFIG["show"].copy())

    @classmethod
    def load(cls, explicit_path: Optional[str] = None) -> 'RiskDisplayConfig':
        """
        加载配置

        优先级（从低到高）：
        1. 内置默认
        2. ~/.config/spear/risk.json
        3. .spear/risk.json
        4. SPEAR_RISK_CONFIG 环境变量
        5. 显式指定路径
        """
        config = cls()

        # 搜索路径（按优先级排序）
        search_paths = [
            Path.home() / '.config' / 'spear' / 'risk.json',
            Path('.spear/risk.json'),
        ]

        # 按顺序合并（后覆盖前）
        for path in search_paths:
            if path.exists():
                config._merge_from_file(path)

        # 环境变量指定
        if env_path := os.getenv('SPEAR_RISK_CONFIG'):
            if Path(env_path).exists():
                config._merge_from_file(Path(env_path))

        # 显式指定（最高优先级）
        if explicit_path and Path(explicit_path).exists():
            config._merge_from_file(Path(explicit_path))

        return config

    def _merge_from_file(self, path: Path):
        """从 JSON 文件合并配置"""
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            if not isinstance(data, dict) or 'risk' not in data:
                return

            risk_data = data['risk']

            if 'colors' in risk_data:
                self.colors.update(risk_data['colors'])
            if 'templates' in risk_data:
                self.templates.update(risk_data['templates'])
            if 'show' in risk_data:
                self.show.update(risk_data['show'])

        except (json.JSONDecodeError, IOError, KeyError):
            pass

    def apply_mode(self, mode: str):
        """应用模式覆盖（从配置文件中查找 modes 部分）"""
        # 从已加载的配置文件中查找 modes
        for path in [Path('.spear/risk.json'), Path.home() / '.config' / 'spear' / 'risk.json']:
            if not path.exists():
                continue
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                if not isinstance(data, dict) or 'modes' not in data:
                    continue

                if mode in data['modes']:
                    mode_data = data['modes'][mode]
                    if 'colors' in mode_data:
                        self.colors.update(mode_data['colors'])
                    if 'templates' in mode_data:
                        self.templates.update(mode_data['templates'])
                    if 'show' in mode_data:
                        self.show.update(mode_data['show'])
                    break

            except (json.JSONDecodeError, IOError):
                continue


# 全局配置缓存
_config_cache = None

def get_risk_config(explicit_path: str = None, mode: str = None) -> RiskDisplayConfig:
    """获取全局 Risk 配置"""
    global _config_cache
    if _config_cache is None:
        _config_cache = RiskDisplayConfig.load(explicit_path)
    if mode:
        _config_cache.apply_mode(mode)
    return _config_cache


def clear_risk_config_cache():
    """清除配置缓存"""
    global _config_cache
    _config_cache = None
```

### 3. Trace 类集成 (core/trace.py)

```python
# core/trace.py

from .risk_config import RiskDisplayConfig, get_risk_config


class Trace:
    """Trace v2.0 - 支持 RiskDisplayConfig 格式化输出"""

    def __init__(self, path: Optional[str] = None, config: RiskDisplayConfig = None):
        self.path = path or self._find_doc()
        self.data = self._load()
        self._current_seq = None
        self.config = config

    def _get_config(self, cfg: RiskDisplayConfig = None) -> RiskDisplayConfig:
        """获取有效配置（回退机制）"""
        return cfg or self.config or get_risk_config()

    # =====================================================================
    # 格式化方法
    # =====================================================================

    def format_issue(self, issue: Dict, cfg: RiskDisplayConfig = None) -> str:
        """格式化单个 issue"""
        cfg = self._get_config(cfg)

        issue_id = issue.get('id', '')
        level = issue.get('level', 'warning')
        desc = issue.get('desc', '')
        status = issue.get('status', 'open')
        hint = issue.get('hint', '')
        result = issue.get('result', '')

        # 应用颜色
        color = cfg.colors.get(level, '')
        reset = cfg.colors.get('reset', '')

        # Issue 行
        if status == 'resolved':
            tpl = cfg.templates.get('issue_resolved', '[RESOLVED] [{id}] [{level}] {desc}')
        else:
            tpl = cfg.templates.get('issue_open', '[OPEN] [{id}] [{level}] {desc}')

        line = tpl.format(id=issue_id, level=level.upper(), desc=desc)
        if color:
            line = f"{color}{line}{reset}"

        lines = [line]

        # Hint / Result
        if status != 'resolved' and hint and cfg.show.get('hint', True):
            tpl = cfg.templates.get('hint', '→ {hint}')
            lines.append(tpl.format(hint=hint))
        elif status == 'resolved' and result and cfg.show.get('result', True):
            tpl = cfg.templates.get('result', '→ {result}')
            lines.append(tpl.format(result=result))

        return '\n'.join(lines)

    def format_issue_list(self, issues: List[Dict], status_filter: str = 'all',
                          cfg: RiskDisplayConfig = None) -> str:
        """格式化 issue 列表"""
        cfg = self._get_config(cfg)

        if not issues:
            return "(No issues)"

        lines = []

        # 标题
        if status_filter == 'open':
            tpl = cfg.templates.get('list_header_open', '[OPEN] {count} issues pending')
            lines.append(tpl.format(count=len(issues)))
        elif status_filter == 'resolved':
            tpl = cfg.templates.get('list_header_resolved', '[RESOLVED] {count} issues')
            lines.append(tpl.format(count=len(issues)))
        else:
            open_count = len([i for i in issues if i.get('status') == 'open'])
            resolved_count = len([i for i in issues if i.get('status') == 'resolved'])
            tpl = cfg.templates.get('list_header_all', '[ALL] {open_count} open, {resolved_count} resolved')
            lines.append(tpl.format(open_count=open_count, resolved_count=resolved_count))

        lines.append('')

        # Issue 列表
        for issue in issues:
            lines.append(self.format_issue(issue, cfg))
            lines.append('')

        return '\n'.join(lines)

    def format_timeline(self, cfg: RiskDisplayConfig = None) -> str:
        """格式化 timeline"""
        cfg = self._get_config(cfg)
        timeline = self.get_timeline()

        if not timeline:
            return "(No timeline records)"

        lines = []

        for record in timeline:
            seq = record.get('seq', 0)
            ts = record.get('timestamp', '')
            cmd = record.get('command', '')

            # 简化时间显示
            time_str = ts.split('T')[1].split('.')[0] if 'T' in ts else ts[:8]

            # Command 行
            tpl = cfg.templates.get('timeline_command', '[{seq}] {time} {command}')
            lines.append(tpl.format(seq=seq, time=time_str, command=cmd))

            # Findings
            for finding in record.get('findings', []):
                ftype = finding.get('type', '')

                if ftype == 'risk_created':
                    level = finding.get('level', 'warning')
                    color = cfg.colors.get(level, '')
                    reset = cfg.colors.get('reset', '')
                    issue_id = finding.get('issue_id', '')
                    desc = finding.get('desc', '')

                    tpl = cfg.templates.get('timeline_finding_created', '[{level}] {issue_id}: {desc}')
                    line = tpl.format(level=level.upper(), issue_id=issue_id, desc=desc)
                    if color:
                        line = f"{color}{line}{reset}"
                    lines.append(line)

                elif ftype == 'issue_resolved':
                    issue_id = finding.get('issue_id', '')
                    result = finding.get('result', '')
                    tpl = cfg.templates.get('timeline_finding_resolved', '[RESOLVED] {issue_id}: {result}')
                    lines.append(tpl.format(issue_id=issue_id, result=result))

                elif ftype == 'info':
                    msg = finding.get('message', '')
                    tpl = cfg.templates.get('timeline_info', '[INFO] {message}')
                    lines.append(tpl.format(message=msg))

            lines.append('')

        # 摘要
        summary = self.get_summary()
        lines.append(f"Commands: {summary['total_commands']}, Open: {summary['open_issues']}, Resolved: {summary['resolved_issues']}")

        return '\n'.join(lines)
```

### 4. CLI 函数 (core/trace.py)

```python
# core/trace.py - CLI 函数

def _load_config_from_args(args) -> RiskDisplayConfig:
    """从 args 加载配置"""
    cfg = get_risk_config(explicit_path=getattr(args, 'risk_config', None))

    if style := getattr(args, 'risk_style', None):
        cfg.apply_mode(style)

    # CI 环境禁用颜色
    if os.getenv('NO_COLOR') or os.getenv('SPEAR_NO_COLOR'):
        cfg.colors = {k: '' for k in cfg.colors}

    return cfg


def cmd_doc_issues(args):
    """查看 issues"""
    cfg = _load_config_from_args(args)
    doc = Trace(config=cfg)

    status_filter = getattr(args, 'status', 'all')

    if status_filter == 'open':
        issues = doc.get_open_issues()
    elif status_filter == 'resolved':
        issues = doc.get_resolved_issues()
    else:
        issues = doc.get_open_issues() + doc.get_resolved_issues()

    print(doc.format_issue_list(issues, status_filter, cfg))

    if status_filter in ['all', 'open'] and doc.get_open_issues():
        print(f"Usage: spear trace complete --id ISS-001 --result '分析结果'")


def cmd_doc_timeline(args):
    """查看 timeline"""
    cfg = _load_config_from_args(args)
    doc = Trace(config=cfg)
    print(doc.format_timeline(cfg))
```

### 5. CLI 参数 (spear.py)

```python
# 为 trace 子命令添加 Risk 参数
def add_trace_risk_args(parser):
    parser.add_argument('--risk-config', metavar='PATH',
                        help='Risk display config file (JSON)')
    parser.add_argument('--risk-style', choices=['default', 'ci', 'compact'],
                        help='Risk style preset')

# 应用到相关命令
add_trace_risk_args(doc_issues)
add_trace_risk_args(doc_timeline)
add_trace_risk_args(doc_finalize)
```

---

## 文件结构

```
config/
└── risk-default.json       # 内置默认配置（项目安装时复制到用户目录）

scripts/perf_toolkit/core/
├── risk_config.py          # 配置加载器（JSON 格式）
└── trace.py                # Trace 类（使用配置格式化）

scripts/spear.py            # CLI 参数
```

---

## 使用示例

### 默认输出（无配置文件）

```bash
spear trace issues
```

```
[OPEN] 2 issues pending

[OPEN] [ISS-001] [WARNING] netstat 高内核态 94.7%
→ cluster-symbols --comm netstat

[OPEN] [ISS-002] [CRITICAL] 锁竞争占比 79.84%
→ find-callers --target 'pthread_mutex_lock'
```

### CI 模式

```bash
spear trace issues --risk-style ci
```

```
[OPEN] 2 issues pending

[OPEN] [ISS-001] [WARNING] netstat 高内核态 94.7%
-> cluster-symbols --comm netstat
```

### 简洁模式

```bash
spear trace issues --risk-style compact
```

```
[OPEN] 2 issues pending

[OPEN] ISS-001 [WARNING] netstat 高内核态 94.7%
[OPEN] ISS-002 [CRITICAL] 锁竞争占比 79.84%
```

---

## 环境变量

| 变量 | 说明 |
|------|------|
| `SPEAR_RISK_CONFIG` | 配置文件路径（JSON） |
| `SPEAR_RISK_STYLE` | 默认样式模式（ci/compact） |
| `NO_COLOR` / `SPEAR_NO_COLOR` | 禁用颜色输出 |
