MEMORY_EXTRACT_SYSTEM = """从以下对话中提取值得长期记住的关键信息。
只提取有长期参考价值的信息，日常寒暄不需要记录。

提取标准：
- 重要的人际关系变化
- 重要的情绪事件或转折
- 新发现的个人偏好或特征
- 多次重复出现的主题（说明该话题对学生重要）

【对话记录】
{conversation}

输出JSON格式：
{{
  "memories": [
    {{
      "content": "记忆内容描述",
      "topic_tags": ["tag1", "tag2"],
      "importance": "high/medium"
    }}
  ]
}}

如果没有值得记住的信息，返回 {{"memories": []}}"""

MEMORY_EXTRACT_USER = "请从对话中提取值得长期记住的关键信息。"
