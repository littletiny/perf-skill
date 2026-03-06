"""
Attention Tags 格式化工具

提供简洁的接口函数用于添加优先级标签。
标签使用 X 前缀避免与日常单词冲突：
- X0: 阻塞级 (Critical/Blocker)
- X1: 重要级 (High/Major)  
- X2: 提示级 (Medium/Minor)
- XA: 操作建议 (Action)

常量定义统一从 config.defaults 导入。
"""

import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from config.defaults import AttentionFlag


def x0(text: str) -> str:
    """添加 X0 标签（阻塞级）- Critical/Blocker"""
    return f"{AttentionFlag.X0} {text}"


def x1(text: str) -> str:
    """添加 X1 标签（重要级）- High/Major"""
    return f"{AttentionFlag.X1} {text}"


def x2(text: str) -> str:
    """添加 X2 标签（提示级）- Medium/Minor"""
    return f"{AttentionFlag.X2} {text}"


def xa(text: str, cmd: str = "") -> str:
    """添加 XA 标签（操作建议）- Action
    
    Args:
        text: 提示描述
        cmd: 建议执行的命令（可选）
    """
    if cmd:
        return f"{AttentionFlag.XA} {text}: {cmd}"
    return f"{AttentionFlag.XA} {text}"


def flag(level: str, text: str) -> str:
    """通用标签函数
    
    Args:
        level: X0, X1, X2, 或 XA
        text: 标签内容
    """
    return f"<{level}> {text}"


# 条件标签函数
def x0_if(condition: bool, text: str, fallback: str = "") -> str:
    """条件添加 X0 标签"""
    if condition:
        return x0(text)
    return fallback or text


def x1_if(condition: bool, text: str, fallback: str = "") -> str:
    """条件添加 X1 标签"""
    if condition:
        return x1(text)
    return fallback or text


def xa_if(condition: bool, text: str, cmd: str = "", fallback: str = "") -> str:
    """条件添加 XA 标签"""
    if condition:
        return xa(text, cmd)
    return fallback or text


# 快捷场景函数（使用 X 标签）
def alert_lock(lock_func: str) -> str:
    """Lock contention alert"""
    return x0(f"Lock Contention: {lock_func} hotspot")


def alert_saturation(cpu_id: int, util: float, monopoly: float) -> str:
    """Single-core saturation alert"""
    return x0(f"Single-Core Saturation: CPU{cpu_id} util {util:.1f}%, Monopoly {monopoly:.2f}")


def alert_high_kernel(ratio: float) -> str:
    """High kernel ratio alert"""
    return x0(f"High Kernel Ratio: {ratio:.1f}%")

def hint_find_callers(target: str) -> str:
    """建议执行 find-callers"""
    return xa("Trace Analysis", f"find-callers --target {target}")


def hint_bottleneck_trace(comm: str) -> str:
    """建议执行 bottleneck-trace"""
    return xa("Deep Tracing", f"bottleneck-trace --comm {comm}")


# 解析提取（简单实现）
def extract_tag(text: str) -> tuple[str | None, str]:
    """从文本中提取标签和内容
    
    Returns:
        (tag, content) 元组，如果没有标签则 tag 为 None
    """
    text = text.strip()
    if text.startswith("<") and ">" in text:
        end = text.index(">")
        tag = text[1:end]
        content = text[end+1:].strip()
        return tag, content
    return None, text


def has_tag(text: str, tag: str) -> bool:
    """检查文本是否包含指定标签"""
    return text.strip().startswith(f"<{tag}>")


def strip_tag(text: str) -> str:
    """移除标签，只保留内容"""
    _, content = extract_tag(text)
    return content
