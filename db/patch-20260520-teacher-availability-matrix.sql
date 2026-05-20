-- 2026-05-20: 教师固定周可用性矩阵
-- 5 行 × 7 列，matrix[period-1][weekday-1]
-- -1 = 明确不可用，0 = 随意分配，1 = 明确可用

ALTER TABLE teacher_profile
    ADD COLUMN availability_matrix_json TEXT NULL COMMENT '教师固定周可用性矩阵 JSON，5x7，matrix[period-1][weekday-1]，-1不可用/0随意/1明确可用'
    AFTER unavailable_time_text;

ALTER TABLE teacher_profile
    ADD COLUMN profile_note TEXT NULL COMMENT '教师其他排课说明，自然语言，由 LLM 解析为软约束'
    AFTER availability_matrix_json;

ALTER TABLE teacher_profile
    ADD COLUMN profile_preference_json TEXT NULL COMMENT '教师其他排课说明的 LLM 结构化解析结果 JSON'
    AFTER profile_note;
