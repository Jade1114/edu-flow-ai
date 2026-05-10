USE edu_flow_ai;

-- Basic seed data for MVP local demo / integration testing.
-- This file intentionally does NOT seed teacher_profile, allocation_scheme,
-- allocation_item, course_assignment, adjustment_request, conflict_check_result,
-- or any vector/RAG/AI-generated runtime data.

START TRANSACTION;

INSERT INTO teacher (name, department, title, max_weekly_hours, status)
SELECT '张明', '软件工程系', '副教授', 8, 'ACTIVE'
WHERE NOT EXISTS (SELECT 1 FROM teacher WHERE name = '张明' AND department = '软件工程系');

INSERT INTO teacher (name, department, title, max_weekly_hours, status)
SELECT '李娜', '软件工程系', '讲师', 10, 'ACTIVE'
WHERE NOT EXISTS (SELECT 1 FROM teacher WHERE name = '李娜' AND department = '软件工程系');

INSERT INTO teacher (name, department, title, max_weekly_hours, status)
SELECT '王强', '计算机科学系', '教授', 6, 'ACTIVE'
WHERE NOT EXISTS (SELECT 1 FROM teacher WHERE name = '王强' AND department = '计算机科学系');

INSERT INTO teacher (name, department, title, max_weekly_hours, status)
SELECT '赵敏', '人工智能系', '讲师', 8, 'ACTIVE'
WHERE NOT EXISTS (SELECT 1 FROM teacher WHERE name = '赵敏' AND department = '人工智能系');

INSERT INTO teacher (name, department, title, max_weekly_hours, status)
SELECT '陈涛', '软件工程系', '实验师', 12, 'ACTIVE'
WHERE NOT EXISTS (SELECT 1 FROM teacher WHERE name = '陈涛' AND department = '软件工程系');

INSERT INTO teacher (name, department, title, max_weekly_hours, status)
SELECT '刘洋', '计算机科学系', '讲师', 10, 'ACTIVE'
WHERE NOT EXISTS (SELECT 1 FROM teacher WHERE name = '刘洋' AND department = '计算机科学系');

INSERT INTO teacher (name, department, title, max_weekly_hours, status)
SELECT '孙悦', '网络工程系', '副教授', 8, 'ACTIVE'
WHERE NOT EXISTS (SELECT 1 FROM teacher WHERE name = '孙悦' AND department = '网络工程系');

INSERT INTO teacher (name, department, title, max_weekly_hours, status)
SELECT '周凯', '数据科学系', '讲师', 8, 'ACTIVE'
WHERE NOT EXISTS (SELECT 1 FROM teacher WHERE name = '周凯' AND department = '数据科学系');

INSERT INTO teacher (name, department, title, max_weekly_hours, status)
SELECT '何静', '软件工程系', '教授', 6, 'ACTIVE'
WHERE NOT EXISTS (SELECT 1 FROM teacher WHERE name = '何静' AND department = '软件工程系');

INSERT INTO teacher (name, department, title, max_weekly_hours, status)
SELECT '郭磊', '人工智能系', '实验师', 12, 'ACTIVE'
WHERE NOT EXISTS (SELECT 1 FROM teacher WHERE name = '郭磊' AND department = '人工智能系');

INSERT INTO course (name, course_type, required_hours, required_skill, description, status)
SELECT 'Java 程序设计', '专业核心课', 48, 'Java 基础、面向对象编程、后端开发经验', '软件工程专业核心编程课程', 'ACTIVE'
WHERE NOT EXISTS (SELECT 1 FROM course WHERE name = 'Java 程序设计');

INSERT INTO course (name, course_type, required_hours, required_skill, description, status)
SELECT '数据库原理', '专业核心课', 48, '关系数据库、SQL、事务与索引设计', '数据库基础理论与实践课程', 'ACTIVE'
WHERE NOT EXISTS (SELECT 1 FROM course WHERE name = '数据库原理');

INSERT INTO course (name, course_type, required_hours, required_skill, description, status)
SELECT 'Web 应用开发', '专业方向课', 40, 'Web 前后端开发、HTTP、RESTful API', 'Web 应用开发与项目实践课程', 'ACTIVE'
WHERE NOT EXISTS (SELECT 1 FROM course WHERE name = 'Web 应用开发');

INSERT INTO course (name, course_type, required_hours, required_skill, description, status)
SELECT '软件工程导论', '专业基础课', 32, '软件过程、需求分析、设计建模、项目管理', '软件工程方法与过程基础课程', 'ACTIVE'
WHERE NOT EXISTS (SELECT 1 FROM course WHERE name = '软件工程导论');

INSERT INTO course (name, course_type, required_hours, required_skill, description, status)
SELECT '人工智能基础', '专业方向课', 40, '机器学习基础、Python、AI 应用理解', '人工智能基础概念与应用课程', 'ACTIVE'
WHERE NOT EXISTS (SELECT 1 FROM course WHERE name = '人工智能基础');

INSERT INTO course (name, course_type, required_hours, required_skill, description, status)
SELECT '操作系统', '专业核心课', 48, '进程管理、内存管理、文件系统、Linux 基础', '计算机系统基础核心课程', 'ACTIVE'
WHERE NOT EXISTS (SELECT 1 FROM course WHERE name = '操作系统');

INSERT INTO course (name, course_type, required_hours, required_skill, description, status)
SELECT '计算机网络', '专业核心课', 48, 'TCP/IP、网络协议、网络应用开发基础', '计算机网络原理与实践课程', 'ACTIVE'
WHERE NOT EXISTS (SELECT 1 FROM course WHERE name = '计算机网络');

INSERT INTO course (name, course_type, required_hours, required_skill, description, status)
SELECT '数据结构', '专业基础课', 48, '线性表、树、图、算法复杂度分析', '程序设计与算法能力基础课程', 'ACTIVE'
WHERE NOT EXISTS (SELECT 1 FROM course WHERE name = '数据结构');

INSERT INTO course (name, course_type, required_hours, required_skill, description, status)
SELECT '软件测试', '专业方向课', 32, '测试用例设计、自动化测试、质量保障流程', '软件质量保障与测试实践课程', 'ACTIVE'
WHERE NOT EXISTS (SELECT 1 FROM course WHERE name = '软件测试');

INSERT INTO course (name, course_type, required_hours, required_skill, description, status)
SELECT '数据分析基础', '专业方向课', 40, 'Python、数据处理、统计分析、可视化基础', '数据科学方向基础实践课程', 'ACTIVE'
WHERE NOT EXISTS (SELECT 1 FROM course WHERE name = '数据分析基础');

INSERT INTO class_group (name, major, grade, student_count, description)
SELECT '软件工程 2301', '软件工程', '2023', 45, '软件工程专业 2023 级 1 班'
WHERE NOT EXISTS (SELECT 1 FROM class_group WHERE name = '软件工程 2301');

INSERT INTO class_group (name, major, grade, student_count, description)
SELECT '软件工程 2302', '软件工程', '2023', 43, '软件工程专业 2023 级 2 班'
WHERE NOT EXISTS (SELECT 1 FROM class_group WHERE name = '软件工程 2302');

INSERT INTO class_group (name, major, grade, student_count, description)
SELECT '计算机科学 2301', '计算机科学与技术', '2023', 46, '计算机科学与技术专业 2023 级 1 班'
WHERE NOT EXISTS (SELECT 1 FROM class_group WHERE name = '计算机科学 2301');

INSERT INTO class_group (name, major, grade, student_count, description)
SELECT '人工智能 2301', '人工智能', '2023', 40, '人工智能专业 2023 级 1 班'
WHERE NOT EXISTS (SELECT 1 FROM class_group WHERE name = '人工智能 2301');

INSERT INTO class_group (name, major, grade, student_count, description)
SELECT '软件工程 2401', '软件工程', '2024', 44, '软件工程专业 2024 级 1 班'
WHERE NOT EXISTS (SELECT 1 FROM class_group WHERE name = '软件工程 2401');

INSERT INTO class_group (name, major, grade, student_count, description)
SELECT '软件工程 2402', '软件工程', '2024', 42, '软件工程专业 2024 级 2 班'
WHERE NOT EXISTS (SELECT 1 FROM class_group WHERE name = '软件工程 2402');

INSERT INTO class_group (name, major, grade, student_count, description)
SELECT '网络工程 2301', '网络工程', '2023', 41, '网络工程专业 2023 级 1 班'
WHERE NOT EXISTS (SELECT 1 FROM class_group WHERE name = '网络工程 2301');

INSERT INTO class_group (name, major, grade, student_count, description)
SELECT '数据科学 2301', '数据科学与大数据技术', '2023', 39, '数据科学与大数据技术专业 2023 级 1 班'
WHERE NOT EXISTS (SELECT 1 FROM class_group WHERE name = '数据科学 2301');

INSERT INTO classroom (name, building, capacity, classroom_type, status)
SELECT 'A101', '第一教学楼', 60, '普通教室', 'ACTIVE'
WHERE NOT EXISTS (SELECT 1 FROM classroom WHERE name = 'A101' AND building = '第一教学楼');

INSERT INTO classroom (name, building, capacity, classroom_type, status)
SELECT 'A102', '第一教学楼', 60, '普通教室', 'ACTIVE'
WHERE NOT EXISTS (SELECT 1 FROM classroom WHERE name = 'A102' AND building = '第一教学楼');

INSERT INTO classroom (name, building, capacity, classroom_type, status)
SELECT 'B201', '第二教学楼', 80, '多媒体教室', 'ACTIVE'
WHERE NOT EXISTS (SELECT 1 FROM classroom WHERE name = 'B201' AND building = '第二教学楼');

INSERT INTO classroom (name, building, capacity, classroom_type, status)
SELECT 'C301', '实验楼', 50, '机房', 'ACTIVE'
WHERE NOT EXISTS (SELECT 1 FROM classroom WHERE name = 'C301' AND building = '实验楼');

INSERT INTO classroom (name, building, capacity, classroom_type, status)
SELECT 'C302', '实验楼', 50, '机房', 'ACTIVE'
WHERE NOT EXISTS (SELECT 1 FROM classroom WHERE name = 'C302' AND building = '实验楼');

INSERT INTO classroom (name, building, capacity, classroom_type, status)
SELECT 'B202', '第二教学楼', 80, '多媒体教室', 'ACTIVE'
WHERE NOT EXISTS (SELECT 1 FROM classroom WHERE name = 'B202' AND building = '第二教学楼');

INSERT INTO classroom (name, building, capacity, classroom_type, status)
SELECT 'B203', '第二教学楼', 70, '普通教室', 'ACTIVE'
WHERE NOT EXISTS (SELECT 1 FROM classroom WHERE name = 'B203' AND building = '第二教学楼');

INSERT INTO classroom (name, building, capacity, classroom_type, status)
SELECT 'D401', '创新楼', 48, '研讨教室', 'ACTIVE'
WHERE NOT EXISTS (SELECT 1 FROM classroom WHERE name = 'D401' AND building = '创新楼');

INSERT INTO classroom (name, building, capacity, classroom_type, status)
SELECT 'D402', '创新楼', 48, '研讨教室', 'ACTIVE'
WHERE NOT EXISTS (SELECT 1 FROM classroom WHERE name = 'D402' AND building = '创新楼');

INSERT INTO classroom (name, building, capacity, classroom_type, status)
SELECT 'E501', '综合楼', 100, '阶梯教室', 'ACTIVE'
WHERE NOT EXISTS (SELECT 1 FROM classroom WHERE name = 'E501' AND building = '综合楼');

INSERT INTO time_slot (week_number, day_of_week, period_index, label)
WITH RECURSIVE
weeks(week_number) AS (
    SELECT 1
    UNION ALL
    SELECT week_number + 1 FROM weeks WHERE week_number < 18
),
days(day_of_week) AS (
    SELECT 1
    UNION ALL
    SELECT day_of_week + 1 FROM days WHERE day_of_week < 7
),
periods(period_index) AS (
    SELECT 1
    UNION ALL
    SELECT period_index + 1 FROM periods WHERE period_index < 6
)
SELECT
    w.week_number,
    d.day_of_week,
    p.period_index,
    CONCAT('第', w.week_number, '周 周',
        CASE d.day_of_week
            WHEN 1 THEN '一'
            WHEN 2 THEN '二'
            WHEN 3 THEN '三'
            WHEN 4 THEN '四'
            WHEN 5 THEN '五'
            WHEN 6 THEN '六'
            WHEN 7 THEN '日'
        END,
        ' 第', p.period_index, '节') AS label
FROM weeks w
CROSS JOIN days d
CROSS JOIN periods p
WHERE NOT EXISTS (
    SELECT 1
    FROM time_slot ts
    WHERE ts.week_number = w.week_number
      AND ts.day_of_week = d.day_of_week
      AND ts.period_index = p.period_index
);

COMMIT;
