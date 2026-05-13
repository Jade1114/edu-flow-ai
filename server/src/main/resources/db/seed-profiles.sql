-- ============================================================
-- 教师画像种子数据（用于测试 RAG 检索 + 工作量冲突检测）
-- 直接 INSERT + 自动调用向量索引，无需手动操作
-- ============================================================
-- 注意：以下 teacher_id 基于 seed-basic.sql 的顺序：
--   ADMIN001(id=1), T1001张明(id=2), T1002李娜(id=3),
--   T1003王强(id=4), T1004赵敏(id=5), T1005陈涛(id=6),
--   T1006刘洋(id=7), T1007孙丽(id=8), T1008周伟(id=9),
--   T1009吴芳(id=10), T1010郑宇(id=11)

-- 张明 — 教授, max_weekly_hours=12
INSERT INTO teacher_profile (teacher_id, available_time_text, unavailable_time_text, workload_requirement, special_note, vector_text)
SELECT id, '周二上午、周三全天、周四下午、周五上午', '周一全天、周五下午',
       '希望每周不超过 10 课时', '',
       '张明可用时间：周二上午、周三全天、周四下午、周五上午。张明不可用时间：周一全天、周五下午。张明课时要求：每周不超过10课时。'
FROM teacher WHERE employee_no = 'T1001'
ON DUPLICATE KEY UPDATE
    available_time_text = VALUES(available_time_text),
    unavailable_time_text = VALUES(unavailable_time_text),
    workload_requirement = VALUES(workload_requirement),
    special_note = VALUES(special_note),
    vector_text = VALUES(vector_text),
    vector_indexed = FALSE;

-- 李娜 — 副教授, max_weekly_hours=12
INSERT INTO teacher_profile (teacher_id, available_time_text, unavailable_time_text, workload_requirement, special_note, vector_text)
SELECT id, '周一上午、周二全天、周四全天、周五上午', '周三全天、周五下午',
       '希望每周不超过 8 课时', '周三需参加课题组会议',
       '李娜可用时间：周一上午、周二全天、周四全天、周五上午。李娜不可用时间：周三全天、周五下午。李娜课时要求：每周不超过8课时。李娜特殊说明：周三需参加课题组会议。'
FROM teacher WHERE employee_no = 'T1002'
ON DUPLICATE KEY UPDATE
    available_time_text = VALUES(available_time_text),
    unavailable_time_text = VALUES(unavailable_time_text),
    workload_requirement = VALUES(workload_requirement),
    special_note = VALUES(special_note),
    vector_text = VALUES(vector_text),
    vector_indexed = FALSE;

-- 王强 — 副教授, max_weekly_hours=12
INSERT INTO teacher_profile (teacher_id, available_time_text, unavailable_time_text, workload_requirement, special_note, vector_text)
SELECT id, '周一至周四上午、周五全天', '周四下午',
       '每周不超过 10 课时', '周四下午指导研究生',
       '王强可用时间：周一至周四上午、周五全天。王强不可用时间：周四下午。王强课时要求：每周不超过10课时。王强特殊说明：周四下午指导研究生。'
FROM teacher WHERE employee_no = 'T1003'
ON DUPLICATE KEY UPDATE
    available_time_text = VALUES(available_time_text),
    unavailable_time_text = VALUES(unavailable_time_text),
    workload_requirement = VALUES(workload_requirement),
    special_note = VALUES(special_note),
    vector_text = VALUES(vector_text),
    vector_indexed = FALSE;

-- 赵敏 — 讲师, max_weekly_hours=14
INSERT INTO teacher_profile (teacher_id, available_time_text, unavailable_time_text, workload_requirement, special_note, vector_text)
SELECT id, '周一全天、周二上午、周三全天、周四上午、周五全天', '周二下午',
       '无特殊要求', '',
       '赵敏可用时间：周一全天、周二上午、周三全天、周四上午、周五全天。赵敏不可用时间：周二下午。赵敏课时要求：无特殊要求。'
FROM teacher WHERE employee_no = 'T1004'
ON DUPLICATE KEY UPDATE
    available_time_text = VALUES(available_time_text),
    unavailable_time_text = VALUES(unavailable_time_text),
    workload_requirement = VALUES(workload_requirement),
    special_note = VALUES(special_note),
    vector_text = VALUES(vector_text),
    vector_indexed = FALSE;

-- 陈涛 — 讲师, max_weekly_hours=14
INSERT INTO teacher_profile (teacher_id, available_time_text, unavailable_time_text, workload_requirement, special_note, vector_text)
SELECT id, '周一上午、周二全天、周三下午、周四全天、周五上午', '周三上午',
       '希望每周不超过 12 课时', '周三上午有固定教研活动',
       '陈涛可用时间：周一上午、周二全天、周三下午、周四全天、周五上午。陈涛不可用时间：周三上午。陈涛课时要求：每周不超过12课时。陈涛特殊说明：周三上午有固定教研活动。'
FROM teacher WHERE employee_no = 'T1005'
ON DUPLICATE KEY UPDATE
    available_time_text = VALUES(available_time_text),
    unavailable_time_text = VALUES(unavailable_time_text),
    workload_requirement = VALUES(workload_requirement),
    special_note = VALUES(special_note),
    vector_text = VALUES(vector_text),
    vector_indexed = FALSE;
