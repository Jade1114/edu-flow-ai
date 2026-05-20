-- 2026-05-20: 清理教师画像旧字段
-- 教师 profile 收口为：availability_matrix_json + profile_note + profile_preference_json

ALTER TABLE teacher_profile
    DROP COLUMN available_time_text,
    DROP COLUMN unavailable_time_text,
    DROP COLUMN workload_requirement,
    DROP COLUMN special_note,
    DROP COLUMN vector_text,
    DROP COLUMN vector_indexed;
