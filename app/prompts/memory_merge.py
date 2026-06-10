MEMORY_MERGE_SYSTEM = """根据以下信息，更新学生档案摘要。

【现有档案】
{existing_profile}

【本次会话新提取的信息】
{new_extractions}

要求：
- 将新信息融入现有档案，保持自然连贯
- 如果新信息与现有信息矛盾，以新信息为准
- 删除不再相关的过时信息
- 输出更新后的完整档案摘要，纯文本格式"""

MEMORY_MERGE_USER = "请更新学生档案摘要。"
