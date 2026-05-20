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

-- TT1: Java程序设计 → 张明 → 软件1班+软件2班 → 48h
INSERT INTO teaching_task (course_id, primary_teacher_id, total_hours, notes, status)
SELECT c.id, t.id, 48, '合班授课，需80座教室', 'ACTIVE'
FROM course c, teacher t WHERE c.name='Java程序设计' AND t.employee_no='T1001'
AND NOT EXISTS (SELECT 1 FROM teaching_task x WHERE x.course_id=c.id AND x.primary_teacher_id=t.id);

-- TT2: 数据库原理 → 李娜 → 软件1班 → 48h
INSERT INTO teaching_task (course_id, primary_teacher_id, total_hours, notes, status)
SELECT c.id, t.id, 48, NULL, 'ACTIVE'
FROM course c, teacher t WHERE c.name='数据库原理' AND t.employee_no='T1002'
AND NOT EXISTS (SELECT 1 FROM teaching_task x WHERE x.course_id=c.id AND x.primary_teacher_id=t.id);

-- TT3: 数据结构 → 王强 → 计科1班 → 48h
INSERT INTO teaching_task (course_id, primary_teacher_id, total_hours, notes, status)
SELECT c.id, t.id, 48, NULL, 'ACTIVE'
FROM course c, teacher t WHERE c.name='数据结构' AND t.employee_no='T1003'
AND NOT EXISTS (SELECT 1 FROM teaching_task x WHERE x.course_id=c.id AND x.primary_teacher_id=t.id);

-- TT4: 计算机网络 → 赵敏 → 人工智能1班+人工智能2班 → 48h
INSERT INTO teaching_task (course_id, primary_teacher_id, total_hours, notes, status)
SELECT c.id, t.id, 48, '合班授课', 'ACTIVE'
FROM course c, teacher t WHERE c.name='计算机网络' AND t.employee_no='T1004'
AND NOT EXISTS (SELECT 1 FROM teaching_task x WHERE x.course_id=c.id AND x.primary_teacher_id=t.id);

-- TT5: 操作系统 → 陈涛 → 计科2班 → 48h
INSERT INTO teaching_task (course_id, primary_teacher_id, total_hours, notes, status)
SELECT c.id, t.id, 48, NULL, 'ACTIVE'
FROM course c, teacher t WHERE c.name='操作系统' AND t.employee_no='T1005'
AND NOT EXISTS (SELECT 1 FROM teaching_task x WHERE x.course_id=c.id AND x.primary_teacher_id=t.id);

-- TT6: 软件工程导论 → 刘洋 → 数据1班 → 36h
INSERT INTO teaching_task (course_id, primary_teacher_id, total_hours, notes, status)
SELECT c.id, t.id, 36, NULL, 'ACTIVE'
FROM course c, teacher t WHERE c.name='软件工程导论' AND t.employee_no='T1006'
AND NOT EXISTS (SELECT 1 FROM teaching_task x WHERE x.course_id=c.id AND x.primary_teacher_id=t.id);

-- TT7: Python程序设计 → 孙丽 → 软件2班 → 36h
INSERT INTO teaching_task (course_id, primary_teacher_id, total_hours, notes, status)
SELECT c.id, t.id, 36, '上机实践课', 'ACTIVE'
FROM course c, teacher t WHERE c.name='Python程序设计' AND t.employee_no='T1007'
AND NOT EXISTS (SELECT 1 FROM teaching_task x WHERE x.course_id=c.id AND x.primary_teacher_id=t.id);

-- TT8: Web前端开发 → 吴芳 → 软件1班 → 36h
INSERT INTO teaching_task (course_id, primary_teacher_id, total_hours, notes, status)
SELECT c.id, t.id, 36, '上机实践课', 'ACTIVE'
FROM course c, teacher t WHERE c.name='Web前端开发' AND t.employee_no='T1009'
AND NOT EXISTS (SELECT 1 FROM teaching_task x WHERE x.course_id=c.id AND x.primary_teacher_id=t.id);

-- TT9: 算法设计与分析 → 王强 → 计科1班+计科2班 → 48h
INSERT INTO teaching_task (course_id, primary_teacher_id, total_hours, notes, status)
SELECT c.id, t.id, 48, '合班授课', 'ACTIVE'
FROM course c, teacher t WHERE c.name='算法设计与分析' AND t.employee_no='T1003'
AND NOT EXISTS (SELECT 1 FROM teaching_task x WHERE x.course_id=c.id AND x.primary_teacher_id=t.id);

-- TT10: 计算机组成原理 → 周伟 → 计科1班 → 48h
INSERT INTO teaching_task (course_id, primary_teacher_id, total_hours, notes, status)
SELECT c.id, t.id, 48, NULL, 'ACTIVE'
FROM course c, teacher t WHERE c.name='计算机组成原理' AND t.employee_no='T1008'
AND NOT EXISTS (SELECT 1 FROM teaching_task x WHERE x.course_id=c.id AND x.primary_teacher_id=t.id);

-- TT11: 人工智能导论 → 郑宇 → 人工智能1班 → 36h
INSERT INTO teaching_task (course_id, primary_teacher_id, total_hours, notes, status)
SELECT c.id, t.id, 36, NULL, 'ACTIVE'
FROM course c, teacher t WHERE c.name='人工智能导论' AND t.employee_no='T1010'
AND NOT EXISTS (SELECT 1 FROM teaching_task x WHERE x.course_id=c.id AND x.primary_teacher_id=t.id);

-- TT12: 大数据技术基础 → 李娜 → 数据2班 → 36h
INSERT INTO teaching_task (course_id, primary_teacher_id, total_hours, notes, status)
SELECT c.id, t.id, 36, NULL, 'ACTIVE'
FROM course c, teacher t WHERE c.name='大数据技术基础' AND t.employee_no='T1002'
AND NOT EXISTS (SELECT 1 FROM teaching_task x WHERE x.course_id=c.id AND x.primary_teacher_id=t.id);

-- TT13: Linux系统应用 → 陈涛 → 计科2班 → 24h
INSERT INTO teaching_task (course_id, primary_teacher_id, total_hours, notes, status)
SELECT c.id, t.id, 24, '上机实践课', 'ACTIVE'
FROM course c, teacher t WHERE c.name='Linux系统应用' AND t.employee_no='T1005'
AND NOT EXISTS (SELECT 1 FROM teaching_task x WHERE x.course_id=c.id AND x.primary_teacher_id=t.id);

-- TT14: 项目管理 → 刘洋 → 数据1班 → 24h
INSERT INTO teaching_task (course_id, primary_teacher_id, total_hours, notes, status)
SELECT c.id, t.id, 24, NULL, 'ACTIVE'
FROM course c, teacher t WHERE c.name='项目管理' AND t.employee_no='T1006'
AND NOT EXISTS (SELECT 1 FROM teaching_task x WHERE x.course_id=c.id AND x.primary_teacher_id=t.id);

-- TT15: 数据库原理 → 李娜 → 数据1班 → 48h（李娜带两门课：DB给软工+DB给数据）
INSERT INTO teaching_task (course_id, primary_teacher_id, total_hours, notes, status)
SELECT c.id, t.id, 48, '数据专业单独开班', 'ACTIVE'
FROM course c, teacher t WHERE c.name='数据库原理' AND t.employee_no='T1002'
AND NOT EXISTS (
    SELECT 1 FROM teaching_task x
    WHERE x.course_id=c.id AND x.primary_teacher_id=t.id AND x.notes='数据专业单独开班'
);

-- TT16: 数据结构 → 王强 → 计科2班 → 48h（王强也带两门）
INSERT INTO teaching_task (course_id, primary_teacher_id, total_hours, notes, status)
SELECT c.id, t.id, 48, '计科2班单独开班', 'ACTIVE'
FROM course c, teacher t WHERE c.name='数据结构' AND t.employee_no='T1003'
AND NOT EXISTS (
    SELECT 1 FROM teaching_task x
    WHERE x.course_id=c.id AND x.primary_teacher_id=t.id AND x.notes='计科2班单独开班'
);

-- TT17: 操作系统 → 周伟 → 人工智能2班 → 48h（周伟同时带组成原理和操作系统）
INSERT INTO teaching_task (course_id, primary_teacher_id, total_hours, notes, status)
SELECT c.id, t.id, 48, NULL, 'ACTIVE'
FROM course c, teacher t WHERE c.name='操作系统' AND t.employee_no='T1008'
AND NOT EXISTS (SELECT 1 FROM teaching_task x WHERE x.course_id=c.id AND x.primary_teacher_id=t.id);

-- TT18: Java程序设计 → 张明 → 数据2班 → 48h（张明Java带两拨）
INSERT INTO teaching_task (course_id, primary_teacher_id, total_hours, notes, status)
SELECT c.id, t.id, 48, '数据专业单独开班', 'ACTIVE'
FROM course c, teacher t WHERE c.name='Java程序设计' AND t.employee_no='T1001'
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
WHERE c.name='Java程序设计' AND t.employee_no='T1001' AND tt.notes='合班授课'
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

COMMIT;

-- ============================================================
-- v6 扩展：数据规模翻倍
-- 教师 10→20 / 课程 14→24 / 班级 8→16 / 教室 10→18 / 教学任务 18→36
-- ============================================================

START TRANSACTION;

-- ============================================================
-- 扩展教师（+10人）
-- ============================================================
INSERT INTO teacher (employee_no, password, role, name, department, title, max_weekly_hours, status) VALUES
('T1011', '123456', 'TEACHER', '马超', '电子信息与计算机工程系', '教授',   10, 'ACTIVE'),
('T1012', '123456', 'TEACHER', '黄丽', '电子信息与计算机工程系', '副教授', 12, 'ACTIVE'),
('T1013', '123456', 'TEACHER', '林杰', '电子信息与计算机工程系', '副教授', 12, 'ACTIVE'),
('T1014', '123456', 'TEACHER', '何雪', '电子信息与计算机工程系', '讲师',   14, 'ACTIVE'),
('T1015', '123456', 'TEACHER', '胡刚', '电子信息与计算机工程系', '讲师',   14, 'ACTIVE'),
('T1016', '123456', 'TEACHER', '徐静', '电子信息与计算机工程系', '讲师',   14, 'ACTIVE'),
('T1017', '123456', 'TEACHER', '叶枫', '电子信息与计算机工程系', '副教授', 12, 'ACTIVE'),
('T1018', '123456', 'TEACHER', '罗敏', '电子信息与计算机工程系', '讲师',   14, 'ACTIVE'),
('T1019', '123456', 'TEACHER', '邓辉', '电子信息与计算机工程系', '教授',   10, 'ACTIVE'),
('T1020', '123456', 'TEACHER', '沈婷', '电子信息与计算机工程系', '讲师',   14, 'ACTIVE')
ON DUPLICATE KEY UPDATE name = VALUES(name);

-- ============================================================
-- 扩展课程（+10门）
-- ============================================================
INSERT INTO course (name, course_type, required_room_type, required_hours, description, status) VALUES
('编译原理',            '专业核心课', '普通教室',   48, '词法分析、语法分析、语义分析、代码优化', 'ACTIVE'),
('计算机图形学',        '专业选修课', '机房实验室', 36, '图形管线、变换、光照模型、渲染基础', 'ACTIVE'),
('嵌入式系统',          '专业核心课', '机房实验室', 48, 'ARM体系结构、嵌入式Linux、驱动开发', 'ACTIVE'),
('数字图像处理',        '专业选修课', '机房实验室', 36, '图像增强、滤波、分割、特征提取', 'ACTIVE'),
('分布式系统',          '专业选修课', '普通教室',   36, '分布式共识、CAP理论、微服务架构', 'ACTIVE'),
('软件测试',            '专业选修课', '机房实验室', 36, '测试方法、自动化测试、性能测试', 'ACTIVE'),
('信息安全概论',        '专业核心课', '普通教室',   48, '密码学基础、网络安全、系统安全', 'ACTIVE'),
('移动应用开发',        '专业选修课', '机房实验室', 36, 'Android/iOS基础、Flutter跨平台开发', 'ACTIVE'),
('云计算概论',          '专业选修课', '普通教室',   36, '虚拟化、容器技术、云原生架构', 'ACTIVE'),
('数据挖掘',            '专业选修课', '机房实验室', 36, '关联规则、聚类、分类、推荐系统', 'ACTIVE')
ON DUPLICATE KEY UPDATE description = VALUES(description);

-- ============================================================
-- 扩展班级（+8个 2024级）
-- ============================================================
INSERT INTO class_group (name, major, grade, student_count, description) VALUES
('24级软件工程1班',              '软件工程',              '2024', 44, '软件工程专业2024级1班'),
('24级软件工程2班',              '软件工程',              '2024', 41, '软件工程专业2024级2班'),
('24级计算机科学与技术1班',      '计算机科学与技术',      '2024', 46, '计科专业2024级1班'),
('24级计算机科学与技术2班',      '计算机科学与技术',      '2024', 43, '计科专业2024级2班'),
('24级人工智能1班',              '人工智能',              '2024', 40, '人工智能专业2024级1班'),
('24级人工智能2班',              '人工智能',              '2024', 38, '人工智能专业2024级2班'),
('24级数据科学与大数据技术1班',  '数据科学与大数据技术',  '2024', 42, '数据专业2024级1班'),
('24级数据科学与大数据技术2班',  '数据科学与大数据技术',  '2024', 39, '数据专业2024级2班')
ON DUPLICATE KEY UPDATE description = VALUES(description);

-- ============================================================
-- 扩展教室（+8间）
-- ============================================================
INSERT INTO classroom (name, building, capacity, classroom_type, status) VALUES
('08301', '综合楼C座', 80,  '普通教室',  'ACTIVE'),
('08302', '综合楼C座', 80,  '普通教室',  'ACTIVE'),
('08303', '综合楼C座', 100, '阶梯教室',  'ACTIVE'),
('08304', '综合楼C座', 60,  '机房实验室', 'ACTIVE'),
('08305', '综合楼C座', 60,  '机房实验室', 'ACTIVE'),
('08106', '综合楼A座', 120, '阶梯教室',  'ACTIVE'),
('08206', '综合楼B座', 70,  '普通教室',  'ACTIVE'),
('08207', '综合楼B座', 70,  '普通教室',  'ACTIVE')
ON DUPLICATE KEY UPDATE building = VALUES(building);

-- ============================================================
-- 扩展教学任务（+18个，TT19~TT36）
-- 新教师 + 新课程 + 2024级班级
-- ============================================================

-- TT19: 编译原理 → 马超 → 软件1班(23级) → 48h
INSERT INTO teaching_task (course_id, primary_teacher_id, total_hours, notes, status)
SELECT c.id, t.id, 48, NULL, 'ACTIVE'
FROM course c, teacher t WHERE c.name='编译原理' AND t.employee_no='T1011';

-- TT20: 计算机图形学 → 黄丽 → 计科1班(23级) → 36h
INSERT INTO teaching_task (course_id, primary_teacher_id, total_hours, notes, status)
SELECT c.id, t.id, 36, '上机实践课', 'ACTIVE'
FROM course c, teacher t WHERE c.name='计算机图形学' AND t.employee_no='T1012';

-- TT21: 嵌入式系统 → 林杰 → 人工智能1班+2班(23级) → 48h
INSERT INTO teaching_task (course_id, primary_teacher_id, total_hours, notes, status)
SELECT c.id, t.id, 48, '合班授课，上机实践', 'ACTIVE'
FROM course c, teacher t WHERE c.name='嵌入式系统' AND t.employee_no='T1013';

-- TT22: 数字图像处理 → 何雪 → 数据1班(23级) → 36h
INSERT INTO teaching_task (course_id, primary_teacher_id, total_hours, notes, status)
SELECT c.id, t.id, 36, '上机实践课', 'ACTIVE'
FROM course c, teacher t WHERE c.name='数字图像处理' AND t.employee_no='T1014';

-- TT23: 分布式系统 → 胡刚 → 软件2班(23级) → 36h
INSERT INTO teaching_task (course_id, primary_teacher_id, total_hours, notes, status)
SELECT c.id, t.id, 36, NULL, 'ACTIVE'
FROM course c, teacher t WHERE c.name='分布式系统' AND t.employee_no='T1015';

-- TT24: 软件测试 → 徐静 → 软件1班(23级) → 36h
INSERT INTO teaching_task (course_id, primary_teacher_id, total_hours, notes, status)
SELECT c.id, t.id, 36, '上机实践课', 'ACTIVE'
FROM course c, teacher t WHERE c.name='软件测试' AND t.employee_no='T1016';

-- TT25: 信息安全概论 → 叶枫 → 计科1班+计科2班(23级) → 48h
INSERT INTO teaching_task (course_id, primary_teacher_id, total_hours, notes, status)
SELECT c.id, t.id, 48, '合班授课', 'ACTIVE'
FROM course c, teacher t WHERE c.name='信息安全概论' AND t.employee_no='T1017';

-- TT26: 移动应用开发 → 罗敏 → 软件2班(23级) → 36h
INSERT INTO teaching_task (course_id, primary_teacher_id, total_hours, notes, status)
SELECT c.id, t.id, 36, '上机实践课', 'ACTIVE'
FROM course c, teacher t WHERE c.name='移动应用开发' AND t.employee_no='T1018';

-- TT27: 云计算概论 → 邓辉 → 数据2班(23级) → 36h
INSERT INTO teaching_task (course_id, primary_teacher_id, total_hours, notes, status)
SELECT c.id, t.id, 36, NULL, 'ACTIVE'
FROM course c, teacher t WHERE c.name='云计算概论' AND t.employee_no='T1019';

-- TT28: 数据挖掘 → 沈婷 → 数据1班(23级) → 36h
INSERT INTO teaching_task (course_id, primary_teacher_id, total_hours, notes, status)
SELECT c.id, t.id, 36, '上机实践课', 'ACTIVE'
FROM course c, teacher t WHERE c.name='数据挖掘' AND t.employee_no='T1020';

-- TT29: 编译原理 → 马超 → 软件1班+2班(24级) → 48h
INSERT INTO teaching_task (course_id, primary_teacher_id, total_hours, notes, status)
SELECT c.id, t.id, 48, '合班授课，24级', 'ACTIVE'
FROM course c, teacher t WHERE c.name='编译原理' AND t.employee_no='T1011';

-- TT30: 嵌入式系统 → 林杰 → 计科1班(24级) → 48h
INSERT INTO teaching_task (course_id, primary_teacher_id, total_hours, notes, status)
SELECT c.id, t.id, 48, '24级单独开班', 'ACTIVE'
FROM course c, teacher t WHERE c.name='嵌入式系统' AND t.employee_no='T1013';

-- TT31: 信息安全概论 → 叶枫 → 软件1班(24级) → 48h
INSERT INTO teaching_task (course_id, primary_teacher_id, total_hours, notes, status)
SELECT c.id, t.id, 48, '24级单独开班', 'ACTIVE'
FROM course c, teacher t WHERE c.name='信息安全概论' AND t.employee_no='T1017';

-- TT32: 计算机图形学 → 黄丽 → 人工智能1班(24级) → 36h
INSERT INTO teaching_task (course_id, primary_teacher_id, total_hours, notes, status)
SELECT c.id, t.id, 36, '上机实践课，24级', 'ACTIVE'
FROM course c, teacher t WHERE c.name='计算机图形学' AND t.employee_no='T1012';

-- TT33: 数字图像处理 → 何雪 → 人工智能2班(24级) → 36h
INSERT INTO teaching_task (course_id, primary_teacher_id, total_hours, notes, status)
SELECT c.id, t.id, 36, '上机实践课，24级', 'ACTIVE'
FROM course c, teacher t WHERE c.name='数字图像处理' AND t.employee_no='T1014';

-- TT34: 分布式系统 → 胡刚 → 计科2班(24级) → 36h
INSERT INTO teaching_task (course_id, primary_teacher_id, total_hours, notes, status)
SELECT c.id, t.id, 36, '24级单独开班', 'ACTIVE'
FROM course c, teacher t WHERE c.name='分布式系统' AND t.employee_no='T1015';

-- TT35: 软件测试 → 徐静 → 数据2班(24级) → 36h
INSERT INTO teaching_task (course_id, primary_teacher_id, total_hours, notes, status)
SELECT c.id, t.id, 36, '上机实践课，24级', 'ACTIVE'
FROM course c, teacher t WHERE c.name='软件测试' AND t.employee_no='T1016';

-- TT36: 数据挖掘 → 沈婷 → 数据1班(24级) → 36h
INSERT INTO teaching_task (course_id, primary_teacher_id, total_hours, notes, status)
SELECT c.id, t.id, 36, '上机实践课，24级', 'ACTIVE'
FROM course c, teacher t WHERE c.name='数据挖掘' AND t.employee_no='T1020';

-- ============================================================
-- 扩展教学任务-班级关联
-- ============================================================

-- TT19: 编译原理 → 马超 → 软件1班(23级)
INSERT IGNORE INTO teaching_task_class_group (teaching_task_id, class_group_id)
SELECT tt.id, cg.id FROM teaching_task tt
JOIN course c ON tt.course_id = c.id JOIN teacher t ON tt.primary_teacher_id = t.id
CROSS JOIN class_group cg
WHERE c.name='编译原理' AND t.employee_no='T1011' AND tt.notes IS NULL
  AND cg.name='23级软件工程1班';

-- TT20: 计算机图形学 → 黄丽 → 计科1班(23级)
INSERT IGNORE INTO teaching_task_class_group (teaching_task_id, class_group_id)
SELECT tt.id, cg.id FROM teaching_task tt
JOIN course c ON tt.course_id = c.id JOIN teacher t ON tt.primary_teacher_id = t.id
CROSS JOIN class_group cg
WHERE c.name='计算机图形学' AND t.employee_no='T1012' AND tt.notes='上机实践课'
  AND cg.name='23级计算机科学与技术1班';

-- TT21: 嵌入式系统 → 林杰 → AI1+AI2(23级)
INSERT IGNORE INTO teaching_task_class_group (teaching_task_id, class_group_id)
SELECT tt.id, cg.id FROM teaching_task tt
JOIN course c ON tt.course_id = c.id JOIN teacher t ON tt.primary_teacher_id = t.id
CROSS JOIN class_group cg
WHERE c.name='嵌入式系统' AND t.employee_no='T1013' AND tt.notes='合班授课，上机实践'
  AND cg.name IN ('23级人工智能1班','23级人工智能2班');

-- TT22: 数字图像处理 → 何雪 → 数据1班(23级)
INSERT IGNORE INTO teaching_task_class_group (teaching_task_id, class_group_id)
SELECT tt.id, cg.id FROM teaching_task tt
JOIN course c ON tt.course_id = c.id JOIN teacher t ON tt.primary_teacher_id = t.id
CROSS JOIN class_group cg
WHERE c.name='数字图像处理' AND t.employee_no='T1014' AND tt.notes='上机实践课'
  AND cg.name='23级数据科学与大数据技术1班';

-- TT23: 分布式系统 → 胡刚 → 软件2班(23级)
INSERT IGNORE INTO teaching_task_class_group (teaching_task_id, class_group_id)
SELECT tt.id, cg.id FROM teaching_task tt
JOIN course c ON tt.course_id = c.id JOIN teacher t ON tt.primary_teacher_id = t.id
CROSS JOIN class_group cg
WHERE c.name='分布式系统' AND t.employee_no='T1015' AND tt.notes IS NULL
  AND cg.name='23级软件工程2班';

-- TT24: 软件测试 → 徐静 → 软件1班(23级)
INSERT IGNORE INTO teaching_task_class_group (teaching_task_id, class_group_id)
SELECT tt.id, cg.id FROM teaching_task tt
JOIN course c ON tt.course_id = c.id JOIN teacher t ON tt.primary_teacher_id = t.id
CROSS JOIN class_group cg
WHERE c.name='软件测试' AND t.employee_no='T1016' AND tt.notes='上机实践课'
  AND cg.name='23级软件工程1班';

-- TT25: 信息安全概论 → 叶枫 → 计科1+2(23级)
INSERT IGNORE INTO teaching_task_class_group (teaching_task_id, class_group_id)
SELECT tt.id, cg.id FROM teaching_task tt
JOIN course c ON tt.course_id = c.id JOIN teacher t ON tt.primary_teacher_id = t.id
CROSS JOIN class_group cg
WHERE c.name='信息安全概论' AND t.employee_no='T1017' AND tt.notes='合班授课'
  AND cg.name IN ('23级计算机科学与技术1班','23级计算机科学与技术2班');

-- TT26: 移动应用开发 → 罗敏 → 软件2班(23级)
INSERT IGNORE INTO teaching_task_class_group (teaching_task_id, class_group_id)
SELECT tt.id, cg.id FROM teaching_task tt
JOIN course c ON tt.course_id = c.id JOIN teacher t ON tt.primary_teacher_id = t.id
CROSS JOIN class_group cg
WHERE c.name='移动应用开发' AND t.employee_no='T1018'
  AND cg.name='23级软件工程2班';

-- TT27: 云计算概论 → 邓辉 → 数据2班(23级)
INSERT IGNORE INTO teaching_task_class_group (teaching_task_id, class_group_id)
SELECT tt.id, cg.id FROM teaching_task tt
JOIN course c ON tt.course_id = c.id JOIN teacher t ON tt.primary_teacher_id = t.id
CROSS JOIN class_group cg
WHERE c.name='云计算概论' AND t.employee_no='T1019'
  AND cg.name='23级数据科学与大数据技术2班';

-- TT28: 数据挖掘 → 沈婷 → 数据1班(23级)
INSERT IGNORE INTO teaching_task_class_group (teaching_task_id, class_group_id)
SELECT tt.id, cg.id FROM teaching_task tt
JOIN course c ON tt.course_id = c.id JOIN teacher t ON tt.primary_teacher_id = t.id
CROSS JOIN class_group cg
WHERE c.name='数据挖掘' AND t.employee_no='T1020' AND tt.notes='上机实践课'
  AND cg.name='23级数据科学与大数据技术1班';

-- TT29: 编译原理 → 马超 → 软件1+2班(24级)
INSERT IGNORE INTO teaching_task_class_group (teaching_task_id, class_group_id)
SELECT tt.id, cg.id FROM teaching_task tt
JOIN course c ON tt.course_id = c.id JOIN teacher t ON tt.primary_teacher_id = t.id
CROSS JOIN class_group cg
WHERE c.name='编译原理' AND t.employee_no='T1011' AND tt.notes='合班授课，24级'
  AND cg.name IN ('24级软件工程1班','24级软件工程2班');

-- TT30: 嵌入式系统 → 林杰 → 计科1班(24级)
INSERT IGNORE INTO teaching_task_class_group (teaching_task_id, class_group_id)
SELECT tt.id, cg.id FROM teaching_task tt
JOIN course c ON tt.course_id = c.id JOIN teacher t ON tt.primary_teacher_id = t.id
CROSS JOIN class_group cg
WHERE c.name='嵌入式系统' AND t.employee_no='T1013' AND tt.notes='24级单独开班'
  AND cg.name='24级计算机科学与技术1班';

-- TT31: 信息安全概论 → 叶枫 → 软件1班(24级)
INSERT IGNORE INTO teaching_task_class_group (teaching_task_id, class_group_id)
SELECT tt.id, cg.id FROM teaching_task tt
JOIN course c ON tt.course_id = c.id JOIN teacher t ON tt.primary_teacher_id = t.id
CROSS JOIN class_group cg
WHERE c.name='信息安全概论' AND t.employee_no='T1017' AND tt.notes='24级单独开班'
  AND cg.name='24级软件工程1班';

-- TT32: 计算机图形学 → 黄丽 → AI1班(24级)
INSERT IGNORE INTO teaching_task_class_group (teaching_task_id, class_group_id)
SELECT tt.id, cg.id FROM teaching_task tt
JOIN course c ON tt.course_id = c.id JOIN teacher t ON tt.primary_teacher_id = t.id
CROSS JOIN class_group cg
WHERE c.name='计算机图形学' AND t.employee_no='T1012' AND tt.notes='上机实践课，24级'
  AND cg.name='24级人工智能1班';

-- TT33: 数字图像处理 → 何雪 → AI2班(24级)
INSERT IGNORE INTO teaching_task_class_group (teaching_task_id, class_group_id)
SELECT tt.id, cg.id FROM teaching_task tt
JOIN course c ON tt.course_id = c.id JOIN teacher t ON tt.primary_teacher_id = t.id
CROSS JOIN class_group cg
WHERE c.name='数字图像处理' AND t.employee_no='T1014' AND tt.notes='上机实践课，24级'
  AND cg.name='24级人工智能2班';

-- TT34: 分布式系统 → 胡刚 → 计科2班(24级)
INSERT IGNORE INTO teaching_task_class_group (teaching_task_id, class_group_id)
SELECT tt.id, cg.id FROM teaching_task tt
JOIN course c ON tt.course_id = c.id JOIN teacher t ON tt.primary_teacher_id = t.id
CROSS JOIN class_group cg
WHERE c.name='分布式系统' AND t.employee_no='T1015' AND tt.notes='24级单独开班'
  AND cg.name='24级计算机科学与技术2班';

-- TT35: 软件测试 → 徐静 → 数据2班(24级)
INSERT IGNORE INTO teaching_task_class_group (teaching_task_id, class_group_id)
SELECT tt.id, cg.id FROM teaching_task tt
JOIN course c ON tt.course_id = c.id JOIN teacher t ON tt.primary_teacher_id = t.id
CROSS JOIN class_group cg
WHERE c.name='软件测试' AND t.employee_no='T1016' AND tt.notes='上机实践课，24级'
  AND cg.name='24级数据科学与大数据技术2班';

-- TT36: 数据挖掘 → 沈婷 → 数据1班(24级)
INSERT IGNORE INTO teaching_task_class_group (teaching_task_id, class_group_id)
SELECT tt.id, cg.id FROM teaching_task tt
JOIN course c ON tt.course_id = c.id JOIN teacher t ON tt.primary_teacher_id = t.id
CROSS JOIN class_group cg
WHERE c.name='数据挖掘' AND t.employee_no='T1020' AND tt.notes='上机实践课，24级'
  AND cg.name='24级数据科学与大数据技术1班';

COMMIT;
