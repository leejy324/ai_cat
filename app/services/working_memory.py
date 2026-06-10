"""工作记忆：内存dict，key=session_id，value=消息列表"""

_working_memory: dict[str, list[dict]] = {}

WORKING_MEMORY_LIMIT = 10


def get_working_memory(session_id: str) -> list[dict]:
    """获取指定会话的工作记忆"""
    return _working_memory.get(session_id, [])


def add_to_working_memory(session_id: str, role: str, content: str):
    """向工作记忆添加消息，超出限制时丢弃旧消息"""
    if session_id not in _working_memory:
        _working_memory[session_id] = []
    _working_memory[session_id].append({"role": role, "content": content})
    if len(_working_memory[session_id]) > WORKING_MEMORY_LIMIT:
        _working_memory[session_id] = _working_memory[session_id][-WORKING_MEMORY_LIMIT:]


def clear_working_memory(session_id: str):
    """清除会话的工作记忆"""
    _working_memory.pop(session_id, None)
