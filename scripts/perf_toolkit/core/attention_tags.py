"""
Attention Tags 格式化工具

提供简洁的接口函数用于添加优先级标签。
标签使用 X 前缀避免与日常单词冲突：
- X0: 阻塞级 (Critical/Blocker)
- X1: 重要级 (High/Major)  
- X2: 提示级 (Medium/Minor)
- XA: 操作建议 (Action)
"""


def x0(text: str) -> str:
    """添加 X0 标签（阻塞级）- Critical/Blocker"""
    return f"<X0> {text}"


def x1(text: str) -> str:
    """添加 X1 标签（重要级）- High/Major"""
    return f"<X1> {text}"


def x2(text: str) -> str:
    """添加 X2 标签（提示级）- Medium/Minor"""
    return f"<X2> {text}"


def xa(text: str, cmd: str = "") -> str:
    """添加 XA 标签（操作建议）- Action
    
    Args:
        text: 提示描述
        cmd: 建议执行的命令（可选）
    """
    if cmd:
        return f"<XA> {text}: {cmd}"
    return f"<XA> {text}"


# 兼容旧名称的别名（推荐使用新的 x0/x1/x2/xa）
p0 = x0
p1 = x1
p2 = x2
hint = xa

# 条件标签函数的兼容别名
p0_if = x0_if
p1_if = x1_if
hint_if = xa_if


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
    """锁竞争警报"""
    return x0(f"锁竞争: {lock_func} 热点")


def alert_saturation(cpu_id: int, util: float, monopoly: float) -> str:
    """单核饱和警报"""
    return x0(f"单核饱和: CPU{cpu_id} 利用率 {util:.1f}%, Monopoly {monopoly:.2f}")


def alert_high_kernel(ratio: float) -> str:
    """高内核态警报"""
    return x0(f"高内核态: 内核占比 {ratio:.1f}%")


def alert_process_storm(spawn_rate: float) -> str:
    """进程风暴警报"""
    return x1(f"进程风暴: Spawn Rate {spawn_rate:.1f}/s")


def hint_find_callers(target: str) -> str:
    """建议执行 find-callers"""
    return xa("溯源分析", f"find-callers --target {target}")


def hint_bottleneck_trace(comm: str) -> str:
    """建议执行 bottleneck-trace"""
    return xa("深度追踪", f"bottleneck-trace --comm {comm}")


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
