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

-- ============================================================
-- v6 扩展：补全 T1006~T1020 教师画像
-- ============================================================

-- 刘洋 T1006 — 讲师, max_weekly_hours=14
INSERT INTO teacher_profile (teacher_id, available_time_text, unavailable_time_text, workload_requirement, special_note, vector_text)
SELECT id, '周一全天、周二上午、周三全天、周四下午、周五上午', '周四上午',
       '希望每周不超过 10 课时', '周四上午带学生竞赛',
       '刘洋可用时间：周一全天、周二上午、周三全天、周四下午、周五上午。刘洋不可用时间：周四上午。刘洋课时要求：每周不超过10课时。刘洋特殊说明：周四上午带学生竞赛。'
FROM teacher WHERE employee_no = 'T1006'
ON DUPLICATE KEY UPDATE
    available_time_text = VALUES(available_time_text),
    unavailable_time_text = VALUES(unavailable_time_text),
    workload_requirement = VALUES(workload_requirement),
    special_note = VALUES(special_note),
    vector_text = VALUES(vector_text),
    vector_indexed = FALSE;

-- 孙丽 T1007 — 讲师, max_weekly_hours=14
INSERT INTO teacher_profile (teacher_id, available_time_text, unavailable_time_text, workload_requirement, special_note, vector_text)
SELECT id, '周二全天、周三上午、周四全天、周五全天', '周一全天',
       '希望每周不超过 12 课时', '周一需照顾家庭',
       '孙丽可用时间：周二全天、周三上午、周四全天、周五全天。孙丽不可用时间：周一全天。孙丽课时要求：每周不超过12课时。孙丽特殊说明：周一需照顾家庭。'
FROM teacher WHERE employee_no = 'T1007'
ON DUPLICATE KEY UPDATE
    available_time_text = VALUES(available_time_text),
    unavailable_time_text = VALUES(unavailable_time_text),
    workload_requirement = VALUES(workload_requirement),
    special_note = VALUES(special_note),
    vector_text = VALUES(vector_text),
    vector_indexed = FALSE;

-- 周伟 T1008 — 副教授, max_weekly_hours=12
INSERT INTO teacher_profile (teacher_id, available_time_text, unavailable_time_text, workload_requirement, special_note, vector_text)
SELECT id, '周一上午、周二全天、周三全天、周四上午、周五下午', '周四下午、周五上午',
       '希望每周不超过 8 课时', '周四下午有行政会议',
       '周伟可用时间：周一上午、周二全天、周三全天、周四上午、周五下午。周伟不可用时间：周四下午、周五上午。周伟课时要求：每周不超过8课时。周伟特殊说明：周四下午有行政会议。'
FROM teacher WHERE employee_no = 'T1008'
ON DUPLICATE KEY UPDATE
    available_time_text = VALUES(available_time_text),
    unavailable_time_text = VALUES(unavailable_time_text),
    workload_requirement = VALUES(workload_requirement),
    special_note = VALUES(special_note),
    vector_text = VALUES(vector_text),
    vector_indexed = FALSE;

-- 吴芳 T1009 — 讲师, max_weekly_hours=14
INSERT INTO teacher_profile (teacher_id, available_time_text, unavailable_time_text, workload_requirement, special_note, vector_text)
SELECT id, '周一全天、周三全天、周四全天、周五上午', '周二全天',
       '希望每周不超过 10 课时', '周二有校外培训',
       '吴芳可用时间：周一全天、周三全天、周四全天、周五上午。吴芳不可用时间：周二全天。吴芳课时要求：每周不超过10课时。吴芳特殊说明：周二有校外培训。'
FROM teacher WHERE employee_no = 'T1009'
ON DUPLICATE KEY UPDATE
    available_time_text = VALUES(available_time_text),
    unavailable_time_text = VALUES(unavailable_time_text),
    workload_requirement = VALUES(workload_requirement),
    special_note = VALUES(special_note),
    vector_text = VALUES(vector_text),
    vector_indexed = FALSE;

-- 郑宇 T1010 — 教授, max_weekly_hours=10
INSERT INTO teacher_profile (teacher_id, available_time_text, unavailable_time_text, workload_requirement, special_note, vector_text)
SELECT id, '周二上午、周三全天、周四全天、周五上午', '周一全天、周二下午',
       '希望每周不超过 6 课时', '周一有学术会议，需减少课时',
       '郑宇可用时间：周二上午、周三全天、周四全天、周五上午。郑宇不可用时间：周一全天、周二下午。郑宇课时要求：每周不超过6课时。郑宇特殊说明：周一有学术会议。'
FROM teacher WHERE employee_no = 'T1010'
ON DUPLICATE KEY UPDATE
    available_time_text = VALUES(available_time_text),
    unavailable_time_text = VALUES(unavailable_time_text),
    workload_requirement = VALUES(workload_requirement),
    special_note = VALUES(special_note),
    vector_text = VALUES(vector_text),
    vector_indexed = FALSE;

-- 马超 T1011 — 教授, max_weekly_hours=10
INSERT INTO teacher_profile (teacher_id, available_time_text, unavailable_time_text, workload_requirement, special_note, vector_text)
SELECT id, '周一上午、周二全天、周三上午、周五全天', '周四全天',
       '希望每周不超过 8 课时', '周四需到外校讲学',
       '马超可用时间：周一上午、周二全天、周三上午、周五全天。马超不可用时间：周四全天。马超课时要求：每周不超过8课时。马超特殊说明：周四需到外校讲学。'
FROM teacher WHERE employee_no = 'T1011'
ON DUPLICATE KEY UPDATE
    available_time_text = VALUES(available_time_text),
    unavailable_time_text = VALUES(unavailable_time_text),
    workload_requirement = VALUES(workload_requirement),
    special_note = VALUES(special_note),
    vector_text = VALUES(vector_text),
    vector_indexed = FALSE;

-- 黄丽 T1012 — 副教授, max_weekly_hours=12
INSERT INTO teacher_profile (teacher_id, available_time_text, unavailable_time_text, workload_requirement, special_note, vector_text)
SELECT id, '周一全天、周二下午、周三全天、周五全天', '周四全天',
       '希望每周不超过 10 课时', '',
       '黄丽可用时间：周一全天、周二下午、周三全天、周五全天。黄丽不可用时间：周四全天。黄丽课时要求：每周不超过10课时。'
FROM teacher WHERE employee_no = 'T1012'
ON DUPLICATE KEY UPDATE
    available_time_text = VALUES(available_time_text),
    unavailable_time_text = VALUES(unavailable_time_text),
    workload_requirement = VALUES(workload_requirement),
    special_note = VALUES(special_note),
    vector_text = VALUES(vector_text),
    vector_indexed = FALSE;

-- 林杰 T1013 — 副教授, max_weekly_hours=12
INSERT INTO teacher_profile (teacher_id, available_time_text, unavailable_time_text, workload_requirement, special_note, vector_text)
SELECT id, '周二全天、周三全天、周四上午、周五全天', '周一全天',
       '希望每周不超过 10 课时', '周一需完成科研任务',
       '林杰可用时间：周二全天、周三全天、周四上午、周五全天。林杰不可用时间：周一全天。林杰课时要求：每周不超过10课时。林杰特殊说明：周一需完成科研任务。'
FROM teacher WHERE employee_no = 'T1013'
ON DUPLICATE KEY UPDATE
    available_time_text = VALUES(available_time_text),
    unavailable_time_text = VALUES(unavailable_time_text),
    workload_requirement = VALUES(workload_requirement),
    special_note = VALUES(special_note),
    vector_text = VALUES(vector_text),
    vector_indexed = FALSE;

-- 何雪 T1014 — 讲师, max_weekly_hours=14
INSERT INTO teacher_profile (teacher_id, available_time_text, unavailable_time_text, workload_requirement, special_note, vector_text)
SELECT id, '周一全天、周三全天、周四全天、周五下午', '周二全天',
       '希望每周不超过 12 课时', '',
       '何雪可用时间：周一全天、周三全天、周四全天、周五下午。何雪不可用时间：周二全天。何雪课时要求：每周不超过12课时。'
FROM teacher WHERE employee_no = 'T1014'
ON DUPLICATE KEY UPDATE
    available_time_text = VALUES(available_time_text),
    unavailable_time_text = VALUES(unavailable_time_text),
    workload_requirement = VALUES(workload_requirement),
    special_note = VALUES(special_note),
    vector_text = VALUES(vector_text),
    vector_indexed = FALSE;

-- 胡刚 T1015 — 讲师, max_weekly_hours=14
INSERT INTO teacher_profile (teacher_id, available_time_text, unavailable_time_text, workload_requirement, special_note, vector_text)
SELECT id, '周一上午、周二全天、周四全天、周五上午', '周三全天',
       '希望每周不超过 10 课时', '周三参加校企合作项目',
       '胡刚可用时间：周一上午、周二全天、周四全天、周五上午。胡刚不可用时间：周三全天。胡刚课时要求：每周不超过10课时。胡刚特殊说明：周三参加校企合作项目。'
FROM teacher WHERE employee_no = 'T1015'
ON DUPLICATE KEY UPDATE
    available_time_text = VALUES(available_time_text),
    unavailable_time_text = VALUES(unavailable_time_text),
    workload_requirement = VALUES(workload_requirement),
    special_note = VALUES(special_note),
    vector_text = VALUES(vector_text),
    vector_indexed = FALSE;

-- 徐静 T1016 — 讲师, max_weekly_hours=14
INSERT INTO teacher_profile (teacher_id, available_time_text, unavailable_time_text, workload_requirement, special_note, vector_text)
SELECT id, '周一全天、周二上午、周三全天、周五全天', '周四全天',
       '希望每周不超过 12 课时', '周四有教研室活动',
       '徐静可用时间：周一全天、周二上午、周三全天、周五全天。徐静不可用时间：周四全天。徐静课时要求：每周不超过12课时。徐静特殊说明：周四有教研室活动。'
FROM teacher WHERE employee_no = 'T1016'
ON DUPLICATE KEY UPDATE
    available_time_text = VALUES(available_time_text),
    unavailable_time_text = VALUES(unavailable_time_text),
    workload_requirement = VALUES(workload_requirement),
    special_note = VALUES(special_note),
    vector_text = VALUES(vector_text),
    vector_indexed = FALSE;

-- 叶枫 T1017 — 副教授, max_weekly_hours=12
INSERT INTO teacher_profile (teacher_id, available_time_text, unavailable_time_text, workload_requirement, special_note, vector_text)
SELECT id, '周二全天、周三上午、周四全天、周五上午', '周一全天',
       '希望每周不超过 8 课时', '周一有项目管理会议',
       '叶枫可用时间：周二全天、周三上午、周四全天、周五上午。叶枫不可用时间：周一全天。叶枫课时要求：每周不超过8课时。叶枫特殊说明：周一有项目管理会议。'
FROM teacher WHERE employee_no = 'T1017'
ON DUPLICATE KEY UPDATE
    available_time_text = VALUES(available_time_text),
    unavailable_time_text = VALUES(unavailable_time_text),
    workload_requirement = VALUES(workload_requirement),
    special_note = VALUES(special_note),
    vector_text = VALUES(vector_text),
    vector_indexed = FALSE;

-- 罗敏 T1018 — 讲师, max_weekly_hours=14
INSERT INTO teacher_profile (teacher_id, available_time_text, unavailable_time_text, workload_requirement, special_note, vector_text)
SELECT id, '周一全天、周三全天、周四上午、周五全天', '周二全天',
       '希望每周不超过 10 课时', '',
       '罗敏可用时间：周一全天、周三全天、周四上午、周五全天。罗敏不可用时间：周二全天。罗敏课时要求：每周不超过10课时。'
FROM teacher WHERE employee_no = 'T1018'
ON DUPLICATE KEY UPDATE
    available_time_text = VALUES(available_time_text),
    unavailable_time_text = VALUES(unavailable_time_text),
    workload_requirement = VALUES(workload_requirement),
    special_note = VALUES(special_note),
    vector_text = VALUES(vector_text),
    vector_indexed = FALSE;

-- 邓辉 T1019 — 教授, max_weekly_hours=10
INSERT INTO teacher_profile (teacher_id, available_time_text, unavailable_time_text, workload_requirement, special_note, vector_text)
SELECT id, '周一上午、周三全天、周四全天、周五上午', '周二全天',
       '希望每周不超过 6 课时', '兼任学术委员会工作',
       '邓辉可用时间：周一上午、周三全天、周四全天、周五上午。邓辉不可用时间：周二全天。邓辉课时要求：每周不超过6课时。邓辉特殊说明：兼任学术委员会工作。'
FROM teacher WHERE employee_no = 'T1019'
ON DUPLICATE KEY UPDATE
    available_time_text = VALUES(available_time_text),
    unavailable_time_text = VALUES(unavailable_time_text),
    workload_requirement = VALUES(workload_requirement),
    special_note = VALUES(special_note),
    vector_text = VALUES(vector_text),
    vector_indexed = FALSE;

-- 沈婷 T1020 — 讲师, max_weekly_hours=14
INSERT INTO teacher_profile (teacher_id, available_time_text, unavailable_time_text, workload_requirement, special_note, vector_text)
SELECT id, '周一全天、周二上午、周四全天、周五下午', '周三全天',
       '希望每周不超过 12 课时', '周三负责实验室管理',
       '沈婷可用时间：周一全天、周二上午、周四全天、周五下午。沈婷不可用时间：周三全天。沈婷课时要求：每周不超过12课时。沈婷特殊说明：周三负责实验室管理。'
FROM teacher WHERE employee_no = 'T1020'
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
