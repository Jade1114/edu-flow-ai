USE edu_flow_ai;

-- ============================================================
-- 种子数据：电子信息与计算机工程系 · 2025秋季学期
-- 规模：10名教师 / 14门课程 / 8个班级 / 10间教室 / 第1~18周
-- ============================================================

START TRANSACTION;

-- ============================================================
-- 管理员
-- ============================================================
INSERT INTO teacher (employee_no, password, role, name, department, title, max_weekly_hours, status)
SELECT 'ADMIN001', '123456', 'ADMIN', '教务管理员', '电子信息与计算机工程系', '管理员', NULL, 'ACTIVE'
WHERE NOT EXISTS (SELECT 1 FROM teacher WHERE employee_no = 'ADMIN001');

-- ============================================================
-- 教师（10人）
-- ============================================================
INSERT INTO teacher (employee_no, password, role, name, department, title, max_weekly_hours, status) VALUES
('T1001', '123456', 'TEACHER', '张明', '电子信息与计算机工程系', '教授',   12, 'ACTIVE'),
('T1002', '123456', 'TEACHER', '李娜', '电子信息与计算机工程系', '副教授', 12, 'ACTIVE'),
('T1003', '123456', 'TEACHER', '王强', '电子信息与计算机工程系', '副教授', 12, 'ACTIVE'),
('T1004', '123456', 'TEACHER', '赵敏', '电子信息与计算机工程系', '讲师',   14, 'ACTIVE'),
('T1005', '123456', 'TEACHER', '陈涛', '电子信息与计算机工程系', '讲师',   14, 'ACTIVE'),
('T1006', '123456', 'TEACHER', '刘洋', '电子信息与计算机工程系', '讲师',   14, 'ACTIVE'),
('T1007', '123456', 'TEACHER', '孙丽', '电子信息与计算机工程系', '讲师',   14, 'ACTIVE'),
('T1008', '123456', 'TEACHER', '周伟', '电子信息与计算机工程系', '副教授', 12, 'ACTIVE'),
('T1009', '123456', 'TEACHER', '吴芳', '电子信息与计算机工程系', '讲师',   14, 'ACTIVE'),
('T1010', '123456', 'TEACHER', '郑宇', '电子信息与计算机工程系', '教授',   10, 'ACTIVE')
ON DUPLICATE KEY UPDATE name = VALUES(name);

-- ============================================================
-- 课程（14门）
-- 总课时说明：
--   48h → 每周约3课时，18周×3=54（留机动）
--   36h → 每周约2课时
--   24h → 每周约1.5课时
-- ============================================================
INSERT INTO course (name, course_type, required_hours, description, status) VALUES
('Java程序设计',        '专业核心课', 48, '面向对象编程、集合框架、IO流、多线程', 'ACTIVE'),
('数据库原理',          '专业核心课', 48, '关系模型、SQL、范式设计、事务管理', 'ACTIVE'),
('数据结构',            '专业核心课', 48, '线性表、树、图、排序与查找算法', 'ACTIVE'),
('计算机网络',          '专业核心课', 48, 'TCP/IP协议栈、路由、网络安全基础', 'ACTIVE'),
('操作系统',            '专业核心课', 48, '进程管理、内存管理、文件系统、设备管理', 'ACTIVE'),
('软件工程导论',        '专业核心课', 36, '需求分析、设计模式、测试方法、敏捷开发', 'ACTIVE'),
('Python程序设计',      '专业选修课', 36, 'Python语法、数据处理、可视化基础', 'ACTIVE'),
('Web前端开发',         '专业选修课', 36, 'HTML5、CSS3、JavaScript、Vue入门', 'ACTIVE'),
('算法设计与分析',      '专业核心课', 48, '分治、动态规划、贪心、图算法', 'ACTIVE'),
('计算机组成原理',      '专业核心课', 48, '数字逻辑、CPU设计、存储体系、指令系统', 'ACTIVE'),
('人工智能导论',        '专业选修课', 36, '机器学习基础、神经网络、自然语言处理入门', 'ACTIVE'),
('大数据技术基础',      '专业选修课', 36, 'Hadoop、Spark、数据仓库、NoSQL', 'ACTIVE'),
('Linux系统应用',       '专业选修课', 24, 'Linux命令、Shell脚本、服务配置', 'ACTIVE'),
('项目管理',            '专业选修课', 24, '项目计划、风险管理、团队协作、文档规范', 'ACTIVE')
ON DUPLICATE KEY UPDATE description = VALUES(description);

-- ============================================================
-- 班级（8个班，4个专业 × 2个班，均为2023级）
-- ============================================================
INSERT INTO class_group (name, major, grade, student_count, description) VALUES
('23级软件工程1班',              '软件工程',              '2023', 42, '软件工程专业2023级1班'),
('23级软件工程2班',              '软件工程',              '2023', 40, '软件工程专业2023级2班'),
('23级计算机科学与技术1班',      '计算机科学与技术',      '2023', 45, '计科专业2023级1班'),
('23级计算机科学与技术2班',      '计算机科学与技术',      '2023', 43, '计科专业2023级2班'),
('23级人工智能1班',              '人工智能',              '2023', 38, '人工智能专业2023级1班'),
('23级人工智能2班',              '人工智能',              '2023', 36, '人工智能专业2023级2班'),
('23级数据科学与大数据技术1班',  '数据科学与大数据技术',  '2023', 40, '数据专业2023级1班'),
('23级数据科学与大数据技术2班',  '数据科学与大数据技术',  '2023', 38, '数据专业2023级2班')
ON DUPLICATE KEY UPDATE description = VALUES(description);

-- ============================================================
-- 教室（10间，两栋楼各5间）
-- ============================================================
INSERT INTO classroom (name, building, capacity, classroom_type, status) VALUES
('08101', '综合楼A座', 80,  '普通教室',  'ACTIVE'),
('08102', '综合楼A座', 80,  '普通教室',  'ACTIVE'),
('08103', '综合楼A座', 80,  '普通教室',  'ACTIVE'),
('08104', '综合楼A座', 100, '阶梯教室',  'ACTIVE'),
('08105', '综合楼A座', 60,  '机房/实验室', 'ACTIVE'),
('08201', '综合楼B座', 80,  '普通教室',  'ACTIVE'),
('08202', '综合楼B座', 80,  '普通教室',  'ACTIVE'),
('08203', '综合楼B座', 90,  '阶梯教室',  'ACTIVE'),
('08204', '综合楼B座', 60,  '机房/实验室', 'ACTIVE'),
('08205', '综合楼B座', 60,  '机房/实验室', 'ACTIVE')
ON DUPLICATE KEY UPDATE building = VALUES(building);

-- ============================================================
-- 时间段（第1~18周，周一~周日，每天5节）
-- ============================================================
INSERT INTO time_slot (week_number, day_of_week, period_index, label)
WITH RECURSIVE
weeks(w) AS (SELECT 1 UNION ALL SELECT w + 1 FROM weeks WHERE w < 18),
days(d) AS (SELECT 1 UNION ALL SELECT d + 1 FROM days WHERE d < 7),
periods(p) AS (SELECT 1 UNION ALL SELECT p + 1 FROM periods WHERE p < 5)
SELECT
    w.w, d.d, p.p,
    CONCAT('第', w.w, '周 周',
        CASE d.d WHEN 1 THEN '一' WHEN 2 THEN '二' WHEN 3 THEN '三'
                 WHEN 4 THEN '四' WHEN 5 THEN '五' WHEN 6 THEN '六'
                 WHEN 7 THEN '日' END,
        ' 第', p.p, '节')
FROM weeks w CROSS JOIN days d CROSS JOIN periods p
WHERE NOT EXISTS (
    SELECT 1 FROM time_slot ts
    WHERE ts.week_number = w.w AND ts.day_of_week = d.d AND ts.period_index = p.p
);

-- ============================================================
-- 教学任务（18个）
-- ============================================================

-- TT1: Java程序设计 → 张明 → 软件1班+软件2班 → 48h → 08101(80座)
INSERT INTO teaching_task (course_id, primary_teacher_id, classroom_id, total_hours, notes, status)
SELECT c.id, t.id, cr.id, 48, '合班授课，需80座教室', 'ACTIVE'
FROM course c, teacher t, classroom cr WHERE c.name='Java程序设计' AND t.employee_no='T1001' AND cr.name='08101'
AND NOT EXISTS (SELECT 1 FROM teaching_task x WHERE x.course_id=c.id AND x.primary_teacher_id=t.id);

-- TT2: 数据库原理 → 李娜 → 软件1班 → 48h → 08102(80座)
INSERT INTO teaching_task (course_id, primary_teacher_id, classroom_id, total_hours, notes, status)
SELECT c.id, t.id, cr.id, 48, NULL, 'ACTIVE'
FROM course c, teacher t, classroom cr WHERE c.name='数据库原理' AND t.employee_no='T1002' AND cr.name='08102'
AND NOT EXISTS (SELECT 1 FROM teaching_task x WHERE x.course_id=c.id AND x.primary_teacher_id=t.id);

-- TT3: 数据结构 → 王强 → 计科1班 → 48h → 08103(80座)
INSERT INTO teaching_task (course_id, primary_teacher_id, classroom_id, total_hours, notes, status)
SELECT c.id, t.id, cr.id, 48, NULL, 'ACTIVE'
FROM course c, teacher t, classroom cr WHERE c.name='数据结构' AND t.employee_no='T1003' AND cr.name='08103'
AND NOT EXISTS (SELECT 1 FROM teaching_task x WHERE x.course_id=c.id AND x.primary_teacher_id=t.id);

-- TT4: 计算机网络 → 赵敏 → 人工智能1班+人工智能2班 → 48h → 08104(100座阶梯)
INSERT INTO teaching_task (course_id, primary_teacher_id, classroom_id, total_hours, notes, status)
SELECT c.id, t.id, cr.id, 48, '合班授课', 'ACTIVE'
FROM course c, teacher t, classroom cr WHERE c.name='计算机网络' AND t.employee_no='T1004' AND cr.name='08104'
AND NOT EXISTS (SELECT 1 FROM teaching_task x WHERE x.course_id=c.id AND x.primary_teacher_id=t.id);

-- TT5: 操作系统 → 陈涛 → 计科2班 → 48h → 08201(80座)
INSERT INTO teaching_task (course_id, primary_teacher_id, classroom_id, total_hours, notes, status)
SELECT c.id, t.id, cr.id, 48, NULL, 'ACTIVE'
FROM course c, teacher t, classroom cr WHERE c.name='操作系统' AND t.employee_no='T1005' AND cr.name='08201'
AND NOT EXISTS (SELECT 1 FROM teaching_task x WHERE x.course_id=c.id AND x.primary_teacher_id=t.id);

-- TT6: 软件工程导论 → 刘洋 → 数据1班 → 36h → 08203(90座阶梯)
INSERT INTO teaching_task (course_id, primary_teacher_id, classroom_id, total_hours, notes, status)
SELECT c.id, t.id, cr.id, 36, NULL, 'ACTIVE'
FROM course c, teacher t, classroom cr WHERE c.name='软件工程导论' AND t.employee_no='T1006' AND cr.name='08203'
AND NOT EXISTS (SELECT 1 FROM teaching_task x WHERE x.course_id=c.id AND x.primary_teacher_id=t.id);

-- TT7: Python程序设计 → 孙丽 → 软件2班 → 36h → 08105(60座机房)
INSERT INTO teaching_task (course_id, primary_teacher_id, classroom_id, total_hours, notes, status)
SELECT c.id, t.id, cr.id, 36, '上机实践课', 'ACTIVE'
FROM course c, teacher t, classroom cr WHERE c.name='Python程序设计' AND t.employee_no='T1007' AND cr.name='08105'
AND NOT EXISTS (SELECT 1 FROM teaching_task x WHERE x.course_id=c.id AND x.primary_teacher_id=t.id);

-- TT8: Web前端开发 → 吴芳 → 软件1班 → 36h → 08204(60座机房)
INSERT INTO teaching_task (course_id, primary_teacher_id, classroom_id, total_hours, notes, status)
SELECT c.id, t.id, cr.id, 36, '上机实践课', 'ACTIVE'
FROM course c, teacher t, classroom cr WHERE c.name='Web前端开发' AND t.employee_no='T1009' AND cr.name='08204'
AND NOT EXISTS (SELECT 1 FROM teaching_task x WHERE x.course_id=c.id AND x.primary_teacher_id=t.id);

-- TT9: 算法设计与分析 → 王强 → 计科1班+计科2班 → 48h → 08104(100座阶梯)
INSERT INTO teaching_task (course_id, primary_teacher_id, classroom_id, total_hours, notes, status)
SELECT c.id, t.id, cr.id, 48, '合班授课', 'ACTIVE'
FROM course c, teacher t, classroom cr WHERE c.name='算法设计与分析' AND t.employee_no='T1003' AND cr.name='08104'
AND NOT EXISTS (SELECT 1 FROM teaching_task x WHERE x.course_id=c.id AND x.primary_teacher_id=t.id);

-- TT10: 计算机组成原理 → 周伟 → 计科1班 → 48h → 08201(80座)
INSERT INTO teaching_task (course_id, primary_teacher_id, classroom_id, total_hours, notes, status)
SELECT c.id, t.id, cr.id, 48, NULL, 'ACTIVE'
FROM course c, teacher t, classroom cr WHERE c.name='计算机组成原理' AND t.employee_no='T1008' AND cr.name='08201'
AND NOT EXISTS (SELECT 1 FROM teaching_task x WHERE x.course_id=c.id AND x.primary_teacher_id=t.id);

-- TT11: 人工智能导论 → 郑宇 → 人工智能1班 → 36h → 08203(90座阶梯)
INSERT INTO teaching_task (course_id, primary_teacher_id, classroom_id, total_hours, notes, status)
SELECT c.id, t.id, cr.id, 36, NULL, 'ACTIVE'
FROM course c, teacher t, classroom cr WHERE c.name='人工智能导论' AND t.employee_no='T1010' AND cr.name='08203'
AND NOT EXISTS (SELECT 1 FROM teaching_task x WHERE x.course_id=c.id AND x.primary_teacher_id=t.id);

-- TT12: 大数据技术基础 → 李娜 → 数据2班 → 36h → 08205(60座机房)
INSERT INTO teaching_task (course_id, primary_teacher_id, classroom_id, total_hours, notes, status)
SELECT c.id, t.id, cr.id, 36, NULL, 'ACTIVE'
FROM course c, teacher t, classroom cr WHERE c.name='大数据技术基础' AND t.employee_no='T1002' AND cr.name='08205'
AND NOT EXISTS (SELECT 1 FROM teaching_task x WHERE x.course_id=c.id AND x.primary_teacher_id=t.id);

-- TT13: Linux系统应用 → 陈涛 → 计科2班 → 24h → 08204(60座机房)
INSERT INTO teaching_task (course_id, primary_teacher_id, classroom_id, total_hours, notes, status)
SELECT c.id, t.id, cr.id, 24, '上机实践课', 'ACTIVE'
FROM course c, teacher t, classroom cr WHERE c.name='Linux系统应用' AND t.employee_no='T1005' AND cr.name='08204'
AND NOT EXISTS (SELECT 1 FROM teaching_task x WHERE x.course_id=c.id AND x.primary_teacher_id=t.id);

-- TT14: 项目管理 → 刘洋 → 数据1班 → 24h → 08202(80座)
INSERT INTO teaching_task (course_id, primary_teacher_id, classroom_id, total_hours, notes, status)
SELECT c.id, t.id, cr.id, 24, NULL, 'ACTIVE'
FROM course c, teacher t, classroom cr WHERE c.name='项目管理' AND t.employee_no='T1006' AND cr.name='08202'
AND NOT EXISTS (SELECT 1 FROM teaching_task x WHERE x.course_id=c.id AND x.primary_teacher_id=t.id);

-- TT15: 数据库原理 → 李娜 → 数据1班 → 48h → 08102(80座)（李娜带两门课：DB给软工+DB给数据）
INSERT INTO teaching_task (course_id, primary_teacher_id, classroom_id, total_hours, notes, status)
SELECT c.id, t.id, cr.id, 48, '数据专业单独开班', 'ACTIVE'
FROM course c, teacher t, classroom cr WHERE c.name='数据库原理' AND t.employee_no='T1002' AND cr.name='08102'
AND NOT EXISTS (
    SELECT 1 FROM teaching_task x
    WHERE x.course_id=c.id AND x.primary_teacher_id=t.id AND x.notes='数据专业单独开班'
);

-- TT16: 数据结构 → 王强 → 计科2班 → 48h → 08103(80座)（王强也带两门）
INSERT INTO teaching_task (course_id, primary_teacher_id, classroom_id, total_hours, notes, status)
SELECT c.id, t.id, cr.id, 48, '计科2班单独开班', 'ACTIVE'
FROM course c, teacher t, classroom cr WHERE c.name='数据结构' AND t.employee_no='T1003' AND cr.name='08103'
AND NOT EXISTS (
    SELECT 1 FROM teaching_task x
    WHERE x.course_id=c.id AND x.primary_teacher_id=t.id AND x.notes='计科2班单独开班'
);

-- TT17: 操作系统 → 周伟 → 人工智能2班 → 48h → 08202(80座)（周伟同时带组成原理和操作系统）
INSERT INTO teaching_task (course_id, primary_teacher_id, classroom_id, total_hours, notes, status)
SELECT c.id, t.id, cr.id, 48, NULL, 'ACTIVE'
FROM course c, teacher t, classroom cr WHERE c.name='操作系统' AND t.employee_no='T1008' AND cr.name='08202'
AND NOT EXISTS (SELECT 1 FROM teaching_task x WHERE x.course_id=c.id AND x.primary_teacher_id=t.id);

-- TT18: Java程序设计 → 张明 → 数据2班 → 48h → 08101(80座)（张明Java带两拨）
INSERT INTO teaching_task (course_id, primary_teacher_id, classroom_id, total_hours, notes, status)
SELECT c.id, t.id, cr.id, 48, '数据专业单独开班', 'ACTIVE'
FROM course c, teacher t, classroom cr WHERE c.name='Java程序设计' AND t.employee_no='T1001' AND cr.name='08101'
AND NOT EXISTS (
    SELECT 1 FROM teaching_task x
    WHERE x.course_id=c.id AND x.primary_teacher_id=t.id AND x.notes='数据专业单独开班'
);

-- ============================================================
-- 教学任务-班级关联
-- 每个 INSERT 使用与教学任务完全相同的匹配条件（课程名+工号+notes）
-- ============================================================

-- TT1: Java程序设计 → 张明 → 软件1班+软件2班
INSERT IGNORE INTO teaching_task_class_group (teaching_task_id, class_group_id)
SELECT tt.id, cg.id FROM teaching_task tt
JOIN course c ON tt.course_id = c.id
JOIN teacher t ON tt.primary_teacher_id = t.id
CROSS JOIN class_group cg
WHERE c.name='Java程序设计' AND t.employee_no='T1001' AND tt.notes='合班授课，需80座教室'
  AND cg.name IN ('23级软件工程1班','23级软件工程2班');

-- TT2: 数据库原理 → 李娜 → 软件1班
INSERT IGNORE INTO teaching_task_class_group (teaching_task_id, class_group_id)
SELECT tt.id, cg.id FROM teaching_task tt
JOIN course c ON tt.course_id = c.id
JOIN teacher t ON tt.primary_teacher_id = t.id
CROSS JOIN class_group cg
WHERE c.name='数据库原理' AND t.employee_no='T1002' AND tt.notes IS NULL
  AND cg.name='23级软件工程1班';

-- TT3: 数据结构 → 王强 → 计科1班
INSERT IGNORE INTO teaching_task_class_group (teaching_task_id, class_group_id)
SELECT tt.id, cg.id FROM teaching_task tt
JOIN course c ON tt.course_id = c.id
JOIN teacher t ON tt.primary_teacher_id = t.id
CROSS JOIN class_group cg
WHERE c.name='数据结构' AND t.employee_no='T1003' AND tt.notes IS NULL
  AND cg.name='23级计算机科学与技术1班';

-- TT4: 计算机网络 → 赵敏 → 人工智能1班+人工智能2班
INSERT IGNORE INTO teaching_task_class_group (teaching_task_id, class_group_id)
SELECT tt.id, cg.id FROM teaching_task tt
JOIN course c ON tt.course_id = c.id
JOIN teacher t ON tt.primary_teacher_id = t.id
CROSS JOIN class_group cg
WHERE c.name='计算机网络' AND t.employee_no='T1004' AND tt.notes='合班授课'
  AND cg.name IN ('23级人工智能1班','23级人工智能2班');

-- TT5: 操作系统 → 陈涛 → 计科2班
INSERT IGNORE INTO teaching_task_class_group (teaching_task_id, class_group_id)
SELECT tt.id, cg.id FROM teaching_task tt
JOIN course c ON tt.course_id = c.id
JOIN teacher t ON tt.primary_teacher_id = t.id
CROSS JOIN class_group cg
WHERE c.name='操作系统' AND t.employee_no='T1005'
  AND cg.name='23级计算机科学与技术2班';

-- TT6: 软件工程导论 → 刘洋 → 数据1班
INSERT IGNORE INTO teaching_task_class_group (teaching_task_id, class_group_id)
SELECT tt.id, cg.id FROM teaching_task tt
JOIN course c ON tt.course_id = c.id
JOIN teacher t ON tt.primary_teacher_id = t.id
CROSS JOIN class_group cg
WHERE c.name='软件工程导论' AND t.employee_no='T1006'
  AND cg.name='23级数据科学与大数据技术1班';

-- TT7: Python程序设计 → 孙丽 → 软件2班
INSERT IGNORE INTO teaching_task_class_group (teaching_task_id, class_group_id)
SELECT tt.id, cg.id FROM teaching_task tt
JOIN course c ON tt.course_id = c.id
JOIN teacher t ON tt.primary_teacher_id = t.id
CROSS JOIN class_group cg
WHERE c.name='Python程序设计' AND t.employee_no='T1007'
  AND cg.name='23级软件工程2班';

-- TT8: Web前端开发 → 吴芳 → 软件1班
INSERT IGNORE INTO teaching_task_class_group (teaching_task_id, class_group_id)
SELECT tt.id, cg.id FROM teaching_task tt
JOIN course c ON tt.course_id = c.id
JOIN teacher t ON tt.primary_teacher_id = t.id
CROSS JOIN class_group cg
WHERE c.name='Web前端开发' AND t.employee_no='T1009'
  AND cg.name='23级软件工程1班';

-- TT9: 算法设计与分析 → 王强 → 计科1班+计科2班
INSERT IGNORE INTO teaching_task_class_group (teaching_task_id, class_group_id)
SELECT tt.id, cg.id FROM teaching_task tt
JOIN course c ON tt.course_id = c.id
JOIN teacher t ON tt.primary_teacher_id = t.id
CROSS JOIN class_group cg
WHERE c.name='算法设计与分析' AND t.employee_no='T1003'
  AND cg.name IN ('23级计算机科学与技术1班','23级计算机科学与技术2班');

-- TT10: 计算机组成原理 → 周伟 → 计科1班
INSERT IGNORE INTO teaching_task_class_group (teaching_task_id, class_group_id)
SELECT tt.id, cg.id FROM teaching_task tt
JOIN course c ON tt.course_id = c.id
JOIN teacher t ON tt.primary_teacher_id = t.id
CROSS JOIN class_group cg
WHERE c.name='计算机组成原理' AND t.employee_no='T1008'
  AND cg.name='23级计算机科学与技术1班';

-- TT11: 人工智能导论 → 郑宇 → 人工智能1班
INSERT IGNORE INTO teaching_task_class_group (teaching_task_id, class_group_id)
SELECT tt.id, cg.id FROM teaching_task tt
JOIN course c ON tt.course_id = c.id
JOIN teacher t ON tt.primary_teacher_id = t.id
CROSS JOIN class_group cg
WHERE c.name='人工智能导论' AND t.employee_no='T1010'
  AND cg.name='23级人工智能1班';

-- TT12: 大数据技术基础 → 李娜 → 数据2班
INSERT IGNORE INTO teaching_task_class_group (teaching_task_id, class_group_id)
SELECT tt.id, cg.id FROM teaching_task tt
JOIN course c ON tt.course_id = c.id
JOIN teacher t ON tt.primary_teacher_id = t.id
CROSS JOIN class_group cg
WHERE c.name='大数据技术基础' AND t.employee_no='T1002'
  AND cg.name='23级数据科学与大数据技术2班';

-- TT13: Linux系统应用 → 陈涛 → 计科2班
INSERT IGNORE INTO teaching_task_class_group (teaching_task_id, class_group_id)
SELECT tt.id, cg.id FROM teaching_task tt
JOIN course c ON tt.course_id = c.id
JOIN teacher t ON tt.primary_teacher_id = t.id
CROSS JOIN class_group cg
WHERE c.name='Linux系统应用' AND t.employee_no='T1005'
  AND cg.name='23级计算机科学与技术2班';

-- TT14: 项目管理 → 刘洋 → 数据1班
INSERT IGNORE INTO teaching_task_class_group (teaching_task_id, class_group_id)
SELECT tt.id, cg.id FROM teaching_task tt
JOIN course c ON tt.course_id = c.id
JOIN teacher t ON tt.primary_teacher_id = t.id
CROSS JOIN class_group cg
WHERE c.name='项目管理' AND t.employee_no='T1006'
  AND cg.name='23级数据科学与大数据技术1班';

-- TT15: 数据库原理 → 李娜 → 数据1班（李娜第二门DB，用 notes 区分）
INSERT IGNORE INTO teaching_task_class_group (teaching_task_id, class_group_id)
SELECT tt.id, cg.id FROM teaching_task tt
JOIN course c ON tt.course_id = c.id
JOIN teacher t ON tt.primary_teacher_id = t.id
CROSS JOIN class_group cg
WHERE c.name='数据库原理' AND t.employee_no='T1002' AND tt.notes='数据专业单独开班'
  AND cg.name='23级数据科学与大数据技术1班';

-- TT16: 数据结构 → 王强 → 计科2班（王强第二门DS，用 notes 区分）
INSERT IGNORE INTO teaching_task_class_group (teaching_task_id, class_group_id)
SELECT tt.id, cg.id FROM teaching_task tt
JOIN course c ON tt.course_id = c.id
JOIN teacher t ON tt.primary_teacher_id = t.id
CROSS JOIN class_group cg
WHERE c.name='数据结构' AND t.employee_no='T1003' AND tt.notes='计科2班单独开班'
  AND cg.name='23级计算机科学与技术2班';

-- TT17: 操作系统 → 周伟 → 人工智能2班
INSERT IGNORE INTO teaching_task_class_group (teaching_task_id, class_group_id)
SELECT tt.id, cg.id FROM teaching_task tt
JOIN course c ON tt.course_id = c.id
JOIN teacher t ON tt.primary_teacher_id = t.id
CROSS JOIN class_group cg
WHERE c.name='操作系统' AND t.employee_no='T1008'
  AND cg.name='23级人工智能2班';

-- TT18: Java程序设计 → 张明 → 数据2班
INSERT IGNORE INTO teaching_task_class_group (teaching_task_id, class_group_id)
SELECT tt.id, cg.id FROM teaching_task tt
JOIN course c ON tt.course_id = c.id
JOIN teacher t ON tt.primary_teacher_id = t.id
CROSS JOIN class_group cg
WHERE c.name='Java程序设计' AND t.employee_no='T1001' AND tt.notes='数据专业单独开班'
  AND cg.name='23级数据科学与大数据技术2班';

-- ============================================================
-- 为教学任务绑定固定教室
-- ============================================================
-- TT1: Java程序设计 → 张明 → 软件1班+2班 → 08101(普通教室,80座)
UPDATE teaching_task tt SET tt.classroom_id = (SELECT id FROM classroom WHERE name='08101')
WHERE tt.course_id = (SELECT id FROM course WHERE name='Java程序设计')
  AND tt.primary_teacher_id = (SELECT id FROM teacher WHERE employee_no='T1001')
  AND tt.notes = '合班授课，需80座教室';

-- TT2: 数据库原理 → 李娜 → 软件1班 → 08102(普通教室,80座)
UPDATE teaching_task tt SET tt.classroom_id = (SELECT id FROM classroom WHERE name='08102')
WHERE tt.course_id = (SELECT id FROM course WHERE name='数据库原理')
  AND tt.primary_teacher_id = (SELECT id FROM teacher WHERE employee_no='T1002')
  AND tt.notes IS NULL;

-- TT3: 数据结构 → 王强 → 计科1班 → 08103(普通教室,80座)
UPDATE teaching_task tt SET tt.classroom_id = (SELECT id FROM classroom WHERE name='08103')
WHERE tt.course_id = (SELECT id FROM course WHERE name='数据结构')
  AND tt.primary_teacher_id = (SELECT id FROM teacher WHERE employee_no='T1003')
  AND tt.notes IS NULL;

-- TT4: 计算机网络 → 赵敏 → AI1+2班 → 08104(阶梯教室,100座)
UPDATE teaching_task tt SET tt.classroom_id = (SELECT id FROM classroom WHERE name='08104')
WHERE tt.course_id = (SELECT id FROM course WHERE name='计算机网络');

-- TT5: 操作系统 → 陈涛 → 计科2班 → 08201(普通教室,80座)
UPDATE teaching_task tt SET tt.classroom_id = (SELECT id FROM classroom WHERE name='08201')
WHERE tt.course_id = (SELECT id FROM course WHERE name='操作系统')
  AND tt.primary_teacher_id = (SELECT id FROM teacher WHERE employee_no='T1005');

-- TT6: 软件工程导论 → 刘洋 → 数据1班 → 08203(阶梯教室,90座)
UPDATE teaching_task tt SET tt.classroom_id = (SELECT id FROM classroom WHERE name='08203')
WHERE tt.course_id = (SELECT id FROM course WHERE name='软件工程导论')
  AND tt.primary_teacher_id = (SELECT id FROM teacher WHERE employee_no='T1006');

-- TT7: Python → 孙丽 → 软件2班 → 08105(机房)
UPDATE teaching_task tt SET tt.classroom_id = (SELECT id FROM classroom WHERE name='08105')
WHERE tt.course_id = (SELECT id FROM course WHERE name='Python程序设计');

-- TT8: Web前端 → 吴芳 → 软件1班 → 08204(机房)
UPDATE teaching_task tt SET tt.classroom_id = (SELECT id FROM classroom WHERE name='08204')
WHERE tt.course_id = (SELECT id FROM course WHERE name='Web前端开发');

-- TT9: 算法 → 王强 → 计科1+2班合班 → 08203(阶梯教室,90座)
UPDATE teaching_task tt SET tt.classroom_id = (SELECT id FROM classroom WHERE name='08203')
WHERE tt.course_id = (SELECT id FROM course WHERE name='算法设计与分析');

-- TT10: 组成原理 → 周伟 → 计科1班 → 08202(普通教室,80座)
UPDATE teaching_task tt SET tt.classroom_id = (SELECT id FROM classroom WHERE name='08202')
WHERE tt.course_id = (SELECT id FROM course WHERE name='计算机组成原理');

-- TT11: AI导论 → 郑宇 → AI1班 → 08203(阶梯教室,90座)
UPDATE teaching_task tt SET tt.classroom_id = (SELECT id FROM classroom WHERE name='08203')
WHERE tt.course_id = (SELECT id FROM course WHERE name='人工智能导论');

-- TT12: 大数据 → 李娜 → 数据2班 → 08205(机房)
UPDATE teaching_task tt SET tt.classroom_id = (SELECT id FROM classroom WHERE name='08205')
WHERE tt.course_id = (SELECT id FROM course WHERE name='大数据技术基础');

-- TT13: Linux → 陈涛 → 计科2班 → 08204(机房)
UPDATE teaching_task tt SET tt.classroom_id = (SELECT id FROM classroom WHERE name='08204')
WHERE tt.course_id = (SELECT id FROM course WHERE name='Linux系统应用');

-- TT14: 项目管理 → 刘洋 → 数据1班 → 08202(普通教室,80座)
UPDATE teaching_task tt SET tt.classroom_id = (SELECT id FROM classroom WHERE name='08202')
WHERE tt.course_id = (SELECT id FROM course WHERE name='项目管理');

-- TT15: 数据库 → 李娜 → 数据1班 → 08102(普通教室,80座)
UPDATE teaching_task tt SET tt.classroom_id = (SELECT id FROM classroom WHERE name='08102')
WHERE tt.course_id = (SELECT id FROM course WHERE name='数据库原理')
  AND tt.notes = '数据专业单独开班';

-- TT16: 数据结构 → 王强 → 计科2班 → 08103(普通教室,80座)
UPDATE teaching_task tt SET tt.classroom_id = (SELECT id FROM classroom WHERE name='08103')
WHERE tt.course_id = (SELECT id FROM course WHERE name='数据结构')
  AND tt.notes = '计科2班单独开班';

-- TT17: 操作系统 → 周伟 → AI2班 → 08202(普通教室,80座)
UPDATE teaching_task tt SET tt.classroom_id = (SELECT id FROM classroom WHERE name='08202')
WHERE tt.course_id = (SELECT id FROM course WHERE name='操作系统')
  AND tt.primary_teacher_id = (SELECT id FROM teacher WHERE employee_no='T1008');

-- TT18: Java → 张明 → 数据2班 → 08101(普通教室,80座)
UPDATE teaching_task tt SET tt.classroom_id = (SELECT id FROM classroom WHERE name='08101')
WHERE tt.course_id = (SELECT id FROM course WHERE name='Java程序设计')
  AND tt.notes = '数据专业单独开班';

COMMIT;
