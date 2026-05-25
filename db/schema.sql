CREATE DATABASE IF NOT EXISTS edu_flow_ai
    DEFAULT CHARACTER SET utf8mb4
    DEFAULT COLLATE utf8mb4_unicode_ci;

USE edu_flow_ai;

CREATE TABLE IF NOT EXISTS teacher (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    employee_no VARCHAR(50) NOT NULL,
    password VARCHAR(100) NOT NULL,
    role VARCHAR(20) NOT NULL DEFAULT 'TEACHER',
    name VARCHAR(50) NOT NULL,
    department VARCHAR(100) NOT NULL,
    title VARCHAR(50) NULL,
    max_weekly_hours INT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_teacher_employee_no (employee_no),
    INDEX idx_teacher_status (status),
    INDEX idx_teacher_name (name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- v3: 教师个人倾向（教师自己提交的可用/不可用时间等偏好）
CREATE TABLE IF NOT EXISTS teacher_profile (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    teacher_id BIGINT NOT NULL,
    availability_matrix_json TEXT NULL COMMENT '教师固定周可用性矩阵 JSON，5x7，matrix[period-1][weekday-1]，-1不可用/0随意/1明确可用',
    profile_note TEXT NULL COMMENT '教师其他排课说明，自然语言，由 LLM 解析为软约束',
    profile_preference_json TEXT NULL COMMENT '教师其他排课说明的 LLM 结构化解析结果 JSON',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_teacher_profile_teacher_id (teacher_id),
    CONSTRAINT fk_teacher_profile_teacher FOREIGN KEY (teacher_id) REFERENCES teacher (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS course (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(100) NOT NULL,
    course_type VARCHAR(50) NULL,
    required_room_type VARCHAR(50) NULL COMMENT '课程所需教室类型 普通教室/阶梯教室/机房实验室',
    required_hours INT NULL,
    description TEXT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_course_name (name),
    INDEX idx_course_status (status),
    INDEX idx_course_name (name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS class_group (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(100) NOT NULL,
    major VARCHAR(100) NULL,
    grade VARCHAR(20) NULL,
    student_count INT NULL,
    description TEXT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_class_group_name (name),
    INDEX idx_class_group_name (name),
    INDEX idx_class_group_major (major)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS classroom (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(100) NOT NULL,
    building VARCHAR(100) NULL,
    capacity INT NULL,
    classroom_type VARCHAR(50) NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_classroom_name (name),
    INDEX idx_classroom_status (status),
    INDEX idx_classroom_name (name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS time_slot (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    week_number INT NOT NULL,
    day_of_week INT NOT NULL,
    period_index INT NOT NULL,
    label VARCHAR(50) NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_time_slot_coordinate (week_number, day_of_week, period_index),
    INDEX idx_time_slot_week_day (week_number, day_of_week)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- v2: 教学任务 - 排课最小单元
CREATE TABLE IF NOT EXISTS teaching_task (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    course_id BIGINT NOT NULL,
    primary_teacher_id BIGINT NOT NULL,
    assistant_teacher_id BIGINT NULL,
    classroom_id BIGINT NULL,
    total_hours INT NOT NULL,
    required_room_type VARCHAR(50) NULL,
    notes TEXT NULL,
    status VARCHAR(30) NOT NULL DEFAULT 'ACTIVE',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_teaching_task_course (course_id),
    INDEX idx_teaching_task_teacher (primary_teacher_id),
    INDEX idx_teaching_task_classroom (classroom_id),
    INDEX idx_teaching_task_status (status),
    CONSTRAINT fk_teaching_task_course FOREIGN KEY (course_id) REFERENCES course (id),
    CONSTRAINT fk_teaching_task_teacher FOREIGN KEY (primary_teacher_id) REFERENCES teacher (id),
    CONSTRAINT fk_teaching_task_assistant FOREIGN KEY (assistant_teacher_id) REFERENCES teacher (id),
    CONSTRAINT fk_teaching_task_classroom FOREIGN KEY (classroom_id) REFERENCES classroom (id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- v2: 教学任务-班级关联（1-2个班级）
CREATE TABLE IF NOT EXISTS teaching_task_class_group (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    teaching_task_id BIGINT NOT NULL,
    class_group_id BIGINT NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_ttcg (teaching_task_id, class_group_id),
    INDEX idx_ttcg_task (teaching_task_id),
    INDEX idx_ttcg_group (class_group_id),
    CONSTRAINT fk_ttcg_task FOREIGN KEY (teaching_task_id) REFERENCES teaching_task (id) ON DELETE CASCADE,
    CONSTRAINT fk_ttcg_group FOREIGN KEY (class_group_id) REFERENCES class_group (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- v2: 教学任务-候选教室关联（可选，为空时使用院系全部可用教室）
CREATE TABLE IF NOT EXISTS teaching_task_classroom (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    teaching_task_id BIGINT NOT NULL,
    classroom_id BIGINT NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_ttc (teaching_task_id, classroom_id),
    INDEX idx_ttc_task (teaching_task_id),
    INDEX idx_ttc_classroom (classroom_id),
    CONSTRAINT fk_ttc_task FOREIGN KEY (teaching_task_id) REFERENCES teaching_task (id) ON DELETE CASCADE,
    CONSTRAINT fk_ttc_classroom FOREIGN KEY (classroom_id) REFERENCES classroom (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- v2: 排课任务（增加 startWeek/endWeek，移除 priorityRule）
CREATE TABLE IF NOT EXISTS allocation_task (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(100) NOT NULL,
    description TEXT NULL,
    start_week INT NOT NULL DEFAULT 1,
    end_week INT NOT NULL DEFAULT 18,
    status VARCHAR(30) NOT NULL DEFAULT 'DRAFT',
    created_by VARCHAR(50) NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_allocation_task_name (name),
    INDEX idx_allocation_task_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- v8: 排课任务生成配置快照（教务可配置 HARD 时间片裁剪 + SOFT 偏好权重；GA 内部参数不入库）
CREATE TABLE IF NOT EXISTS allocation_task_generation_config (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    task_id BIGINT NOT NULL,
    allowed_weeks VARCHAR(128) NOT NULL DEFAULT '1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18' COMMENT '允许参与排课的周次，多选结果，逗号分隔',
    allowed_weekdays VARCHAR(32) NOT NULL DEFAULT '1,2,3,4,5' COMMENT '允许参与排课的星期，多选结果，1=周一，7=周日',
    allowed_periods VARCHAR(32) NOT NULL DEFAULT '1,2,3,4' COMMENT '允许参与排课的节次，多选结果，默认不排晚课',
    scheme_count INT NOT NULL DEFAULT 3 COMMENT '生成候选方案数量',
    teacher_profile_penalty_scale DECIMAL(10,4) NOT NULL DEFAULT 80.0000 COMMENT '教师软画像惩罚缩放',
    distribution_penalty_scale DECIMAL(10,4) NOT NULL DEFAULT 10.0000 COMMENT '分布均衡惩罚缩放',
    classroom_stickiness_weight DECIMAL(10,4) NOT NULL DEFAULT 15.0000 COMMENT '教室粘性权重，含绑定教室软偏好',
    compact_bonus_weight DECIMAL(10,4) NOT NULL DEFAULT 0.0000 COMMENT '紧凑排课奖励权重',
    weekday_load_penalty DECIMAL(10,6) NOT NULL DEFAULT 0.030000,
    room_day_load_penalty DECIMAL(10,6) NOT NULL DEFAULT 0.015000,
    room_week_load_penalty DECIMAL(10,6) NOT NULL DEFAULT 0.008000,
    task_day_load_penalty DECIMAL(10,6) NOT NULL DEFAULT 0.050000,
    early_period_penalty DECIMAL(10,6) NOT NULL DEFAULT 0.040000,
    late_period_penalty DECIMAL(10,6) NOT NULL DEFAULT 0.030000,
    random_jitter DECIMAL(10,6) NOT NULL DEFAULT 0.001000,
    classroom_stickiness_bonus DECIMAL(10,6) NOT NULL DEFAULT 0.020000,
    weekend_penalty DECIMAL(10,6) NOT NULL DEFAULT 0.050000,
    llm_prompt TEXT NULL COMMENT '教务自然语言策略原文，可选',
    llm_result_json TEXT NULL COMMENT 'LLM Parser 标准化输出快照，可选',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_generation_config_task (task_id),
    CONSTRAINT fk_generation_config_task FOREIGN KEY (task_id) REFERENCES allocation_task (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- v2: 排课任务-教学任务关联
CREATE TABLE IF NOT EXISTS allocation_task_teaching_task (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    allocation_task_id BIGINT NOT NULL,
    teaching_task_id BIGINT NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_att (allocation_task_id, teaching_task_id),
    INDEX idx_att_task (allocation_task_id),
    INDEX idx_att_teaching (teaching_task_id),
    CONSTRAINT fk_att_task FOREIGN KEY (allocation_task_id) REFERENCES allocation_task (id) ON DELETE CASCADE,
    CONSTRAINT fk_att_teaching FOREIGN KEY (teaching_task_id) REFERENCES teaching_task (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- v2: 候选方案（不变）
-- v5: 方案评估字段 + 反馈表
CREATE TABLE IF NOT EXISTS allocation_scheme (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    task_id BIGINT NOT NULL,
    scheme_name VARCHAR(100) NOT NULL,
    summary TEXT NULL,
    scheme_score DOUBLE NULL COMMENT '评估器综合分 0-100',
    evaluation_summary TEXT NULL COMMENT '评估结果 JSON',
    policy VARCHAR(32) NULL COMMENT '生成策略名称',
    policy_params TEXT NULL COMMENT '生成策略参数 JSON',
    model_version VARCHAR(16) NULL COMMENT '模型版本 v1/v2',
    conflict_summary TEXT NULL,
    valid BOOLEAN NOT NULL DEFAULT TRUE,
    status VARCHAR(30) NOT NULL DEFAULT 'CANDIDATE',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_allocation_scheme_task (task_id),
    INDEX idx_allocation_scheme_status (status),
    CONSTRAINT fk_allocation_scheme_task FOREIGN KEY (task_id) REFERENCES allocation_task (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- v5: 方案反馈（教务选择/调整/确认行为记录）
CREATE TABLE IF NOT EXISTS allocation_scheme_feedback (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    scheme_id BIGINT NOT NULL,
    task_id BIGINT NOT NULL,
    feedback_type VARCHAR(30) NOT NULL COMMENT 'SELECTED/ADJUSTED/CONFIRMED',
    adjustment_count INT NOT NULL DEFAULT 0 COMMENT '调整次数',
    created_by VARCHAR(100) NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_scheme_feedback_scheme (scheme_id),
    INDEX idx_scheme_feedback_task (task_id),
    INDEX idx_scheme_feedback_type (feedback_type),
    CONSTRAINT fk_scheme_feedback_scheme FOREIGN KEY (scheme_id) REFERENCES allocation_scheme (id),
    CONSTRAINT fk_scheme_feedback_task FOREIGN KEY (task_id) REFERENCES allocation_task (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- v5: 人工调整日志（记录每次拖拽/编辑的前后状态）
CREATE TABLE IF NOT EXISTS allocation_item_adjustment_log (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    scheme_id BIGINT NOT NULL,
    item_id BIGINT NOT NULL,
    teaching_task_id BIGINT NOT NULL,
    from_time_slot_id BIGINT NULL,
    to_time_slot_id BIGINT NULL,
    from_classroom_id BIGINT NULL,
    to_classroom_id BIGINT NULL,
    reason VARCHAR(500) NULL,
    created_by VARCHAR(100) NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_item_adj_scheme (scheme_id),
    INDEX idx_item_adj_item (item_id),
    CONSTRAINT fk_item_adj_scheme FOREIGN KEY (scheme_id) REFERENCES allocation_scheme (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- v2: 排课片段（改为 teaching_task_id 替代 course/classGroup/teacher）
CREATE TABLE IF NOT EXISTS allocation_item (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    scheme_id BIGINT NOT NULL,
    teaching_task_id BIGINT NOT NULL,
    classroom_id BIGINT NOT NULL,
    time_slot_id BIGINT NOT NULL,
    valid BOOLEAN NOT NULL DEFAULT TRUE,
    conflict_message TEXT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_allocation_item_scheme (scheme_id),
    INDEX idx_allocation_item_teaching_task (teaching_task_id),
    INDEX idx_allocation_item_classroom_time (classroom_id, time_slot_id),
    CONSTRAINT fk_allocation_item_scheme FOREIGN KEY (scheme_id) REFERENCES allocation_scheme (id),
    CONSTRAINT fk_allocation_item_teaching_task FOREIGN KEY (teaching_task_id) REFERENCES teaching_task (id),
    CONSTRAINT fk_allocation_item_classroom FOREIGN KEY (classroom_id) REFERENCES classroom (id),
    CONSTRAINT fk_allocation_item_time_slot FOREIGN KEY (time_slot_id) REFERENCES time_slot (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- v2: 正式课表（改为 teaching_task_id 替代 course/classGroup/teacher）
CREATE TABLE IF NOT EXISTS course_assignment (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    source_scheme_id BIGINT NULL,
    teaching_task_id BIGINT NOT NULL,
    classroom_id BIGINT NOT NULL,
    time_slot_id BIGINT NOT NULL,
    status VARCHAR(30) NOT NULL DEFAULT 'ACTIVE',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_course_assignment_scheme (source_scheme_id),
    INDEX idx_course_assignment_teaching_task (teaching_task_id),
    INDEX idx_course_assignment_classroom_time (classroom_id, time_slot_id),
    INDEX idx_course_assignment_status (status),
    CONSTRAINT fk_course_assignment_scheme FOREIGN KEY (source_scheme_id) REFERENCES allocation_scheme (id),
    CONSTRAINT fk_course_assignment_teaching_task FOREIGN KEY (teaching_task_id) REFERENCES teaching_task (id),
    CONSTRAINT fk_course_assignment_classroom FOREIGN KEY (classroom_id) REFERENCES classroom (id),
    CONSTRAINT fk_course_assignment_time_slot FOREIGN KEY (time_slot_id) REFERENCES time_slot (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- v2: 冲突检测结果
CREATE TABLE IF NOT EXISTS conflict_check_result (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    biz_type VARCHAR(30) NOT NULL,
    biz_id BIGINT NOT NULL,
    conflict_type VARCHAR(50) NOT NULL,
    message TEXT NOT NULL,
    related_teacher_id BIGINT NULL,
    related_class_group_id BIGINT NULL,
    related_classroom_id BIGINT NULL,
    related_time_slot_id BIGINT NULL,
    teaching_task_id BIGINT NULL,
    course_name VARCHAR(200) NULL,
    expected_hours INT NULL,
    actual_hours INT NULL,
    resolved BOOLEAN NOT NULL DEFAULT FALSE,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_ccr_teaching_task (teaching_task_id),
    INDEX idx_conflict_biz (biz_type, biz_id),
    INDEX idx_conflict_type (conflict_type),
    INDEX idx_conflict_resolved (resolved),
    CONSTRAINT fk_conflict_teacher FOREIGN KEY (related_teacher_id) REFERENCES teacher (id),
    CONSTRAINT fk_conflict_class_group FOREIGN KEY (related_class_group_id) REFERENCES class_group (id),
    CONSTRAINT fk_conflict_classroom FOREIGN KEY (related_classroom_id) REFERENCES classroom (id),
    CONSTRAINT fk_conflict_time_slot FOREIGN KEY (related_time_slot_id) REFERENCES time_slot (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- v4: 调课申请
CREATE TABLE IF NOT EXISTS adjustment_request (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    assignment_id BIGINT NOT NULL COMMENT '原正式课表 ID',
    teacher_id BIGINT NOT NULL COMMENT '申请教师 ID',
    reason VARCHAR(500) NOT NULL COMMENT '调课原因',
    preferred_time_text VARCHAR(500) DEFAULT NULL COMMENT '调课倾向（自然语言）',
    status VARCHAR(20) NOT NULL DEFAULT 'PENDING' COMMENT 'PENDING / APPROVED / REJECTED',
    review_note VARCHAR(500) DEFAULT NULL COMMENT '审核意见',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_adjustment_teacher (teacher_id),
    INDEX idx_adjustment_status (status),
    CONSTRAINT fk_adjustment_assignment FOREIGN KEY (assignment_id) REFERENCES course_assignment (id),
    CONSTRAINT fk_adjustment_teacher FOREIGN KEY (teacher_id) REFERENCES teacher (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- v6: 模型训练日志（记录每次重训的版本、指标、数据来源）
CREATE TABLE IF NOT EXISTS model_training_log (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    model_version VARCHAR(16) NOT NULL COMMENT '模型版本号 v1/v2/...',
    training_type VARCHAR(30) NOT NULL COMMENT 'INITIAL / FEEDBACK / FULL',
    scheme_count INT NOT NULL DEFAULT 0 COMMENT '参与训练的方案数',
    item_count INT NOT NULL DEFAULT 0 COMMENT '参与训练的明细数',
    feedback_count INT NOT NULL DEFAULT 0 COMMENT '反馈记录数',
    adjustment_count INT NOT NULL DEFAULT 0 COMMENT '调整记录数',
    conflict_count INT NOT NULL DEFAULT 0 COMMENT '冲突记录数',
    sample_count INT NOT NULL DEFAULT 0 COMMENT '生成样本总数',
    positive_count INT NOT NULL DEFAULT 0 COMMENT '正样本数',
    negative_count INT NOT NULL DEFAULT 0 COMMENT '负样本数',
    train_accuracy DOUBLE NULL COMMENT '训练集准确率',
    train_auc DOUBLE NULL COMMENT '训练集 AUC',
    eval_accuracy DOUBLE NULL COMMENT '验证集准确率',
    eval_auc DOUBLE NULL COMMENT '验证集 AUC',
    model_path VARCHAR(500) NULL COMMENT '模型文件路径',
    sample_path VARCHAR(500) NULL COMMENT '训练样本路径',
    metrics_json TEXT NULL COMMENT '完整指标 JSON',
    status VARCHAR(20) NOT NULL DEFAULT 'RUNNING' COMMENT 'RUNNING / SUCCEEDED / FAILED',
    error_message TEXT NULL,
    train_started_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    train_finished_at DATETIME NULL,
    INDEX idx_training_log_version (model_version),
    INDEX idx_training_log_type (training_type),
    INDEX idx_training_log_status (status),
    INDEX idx_training_log_started (train_started_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- v7: 反馈事件台账（先沉淀事实，再构建训练样本）
CREATE TABLE IF NOT EXISTS ml_feedback_event (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    event_type VARCHAR(50) NOT NULL COMMENT 'SCHEME_CONFIRMED / ITEM_MOVED / ITEM_MARKED_GOOD / ITEM_MARKED_BAD',
    task_id BIGINT NOT NULL,
    scheme_id BIGINT NOT NULL,
    item_id BIGINT NULL,
    teaching_task_id BIGINT NULL,
    actor_type VARCHAR(30) NOT NULL DEFAULT 'ADMIN',
    actor_id VARCHAR(100) NULL,
    reason_code VARCHAR(50) NULL,
    reason_text VARCHAR(500) NULL,
    before_snapshot_json TEXT NULL,
    after_snapshot_json TEXT NULL,
    context_snapshot_json TEXT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_feedback_event_task (task_id),
    INDEX idx_feedback_event_scheme (scheme_id),
    INDEX idx_feedback_event_item (item_id),
    INDEX idx_feedback_event_type (event_type),
    INDEX idx_feedback_event_created (created_at),
    CONSTRAINT fk_feedback_event_task FOREIGN KEY (task_id) REFERENCES allocation_task (id),
    CONSTRAINT fk_feedback_event_scheme FOREIGN KEY (scheme_id) REFERENCES allocation_scheme (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
