输入为 JSON，包含：
- teaching_tasks：本次排课涉及的教学任务上下文
- teacher_profiles：Qdrant 检索到的教师画像 payload，可能包含 availableTimeText、unavailableTimeText、workloadRequirement、specialNote、vectorText 等字段

请阅读教学任务上下文与教师画像全文，输出结构化教师画像惩罚参数。
输出格式必须为：
{
  "teacher_penalties": {
    "teacher_id": {
      "unavailable_slots": [[day, period]],
      "max_weekly_hours": 8,
      "penalty_weight": 0.05,
      "reason": "简短说明"
    }
  }
}

动态输入 JSON：
{payload_json}
