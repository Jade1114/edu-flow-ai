-- V3.5 template-based scheduling tables draft
-- Status: dry-run design, review before applying to production DB.
-- Design doc: docs/architecture/22-V3.5-模板化排课落库设计.md
-- Core idea: template -> week mapping -> template fragments -> occupied slots.

CREATE TABLE IF NOT EXISTS schedule_template (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    allocation_task_id BIGINT NOT NULL COMMENT '排课任务ID',
    template_code VARCHAR(64) NOT NULL COMMENT '模板编码，如 cover_v1_template_1',
    template_name VARCHAR(128) NULL COMMENT '模板名称',
    template_order INT NOT NULL DEFAULT 1 COMMENT '模板顺序',
    source_type VARCHAR(32) NOT NULL DEFAULT 'AUTO' COMMENT 'AUTO/MANUAL/ADJUSTED',
    algorithm_version VARCHAR(64) NULL COMMENT '算法版本，如 v3.5-cover-v1',
    status VARCHAR(32) NOT NULL DEFAULT 'ACTIVE' COMMENT 'ACTIVE/ARCHIVED',
    fragment_count INT NOT NULL DEFAULT 0,
    task_count INT NOT NULL DEFAULT 0,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_allocation_template_code (allocation_task_id, template_code),
    KEY idx_allocation_task (allocation_task_id)
) COMMENT='排课模板表';

CREATE TABLE IF NOT EXISTS schedule_template_week (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    allocation_task_id BIGINT NOT NULL COMMENT '排课任务ID',
    week_number INT NOT NULL COMMENT '教学周',
    template_id BIGINT NOT NULL COMMENT '使用的模板ID',
    template_code VARCHAR(64) NOT NULL COMMENT 'dry-run 阶段用于关联模板编码',
    source_type VARCHAR(32) NOT NULL DEFAULT 'AUTO' COMMENT 'AUTO/MANUAL_ADJUSTED',
    notes VARCHAR(255) NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_allocation_week (allocation_task_id, week_number),
    KEY idx_template (template_id),
    KEY idx_allocation_template (allocation_task_id, template_id)
) COMMENT='排课任务每周模板映射表';

CREATE TABLE IF NOT EXISTS schedule_template_fragment (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    template_id BIGINT NOT NULL COMMENT '模板ID',
    template_code VARCHAR(64) NOT NULL COMMENT 'dry-run 阶段用于关联模板编码',
    allocation_task_id BIGINT NOT NULL COMMENT '排课任务ID',
    fragment_code VARCHAR(255) NOT NULL COMMENT '算法片段ID，如 source_key#frag1',
    teaching_task_id BIGINT NULL COMMENT '教学任务ID',
    source_key VARCHAR(255) NULL COMMENT '算法侧任务标识，过渡期使用',
    course_id BIGINT NULL,
    course_name VARCHAR(255) NULL,
    teacher_id BIGINT NULL,
    teacher_name VARCHAR(128) NULL,
    class_group_id BIGINT NULL,
    class_name VARCHAR(128) NULL,
    classroom_id BIGINT NULL,
    classroom_name VARCHAR(128) NOT NULL,
    day_of_week INT NOT NULL COMMENT '星期 1-7',
    period_index INT NOT NULL COMMENT '起始课段',
    consecutive_slots INT NOT NULL DEFAULT 1 COMMENT '连续课段数，理论=1，上机=2',
    required_room_type VARCHAR(32) NULL COMMENT '普通教室/机房',
    source_type VARCHAR(32) NOT NULL DEFAULT 'AUTO' COMMENT 'AUTO/MANUAL/ADJUSTED',
    lock_status VARCHAR(32) NOT NULL DEFAULT 'UNLOCKED' COMMENT 'LOCKED/UNLOCKED',
    score DECIMAL(12, 8) NULL COMMENT 'placement score',
    candidate_rank INT NULL COMMENT '候选排名，fallback 可记为 top_k+1',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_template_fragment_code (template_id, fragment_code),
    KEY idx_template (template_id),
    KEY idx_allocation_task (allocation_task_id),
    KEY idx_teaching_task (teaching_task_id),
    KEY idx_template_time (template_id, day_of_week, period_index),
    KEY idx_template_room_time (template_id, classroom_id, day_of_week, period_index),
    KEY idx_template_class_time (template_id, class_group_id, day_of_week, period_index),
    KEY idx_template_teacher_time (template_id, teacher_id, day_of_week, period_index)
) COMMENT='排课模板片段表';

CREATE TABLE IF NOT EXISTS schedule_template_fragment_slot (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    template_fragment_id BIGINT NOT NULL,
    fragment_code VARCHAR(255) NOT NULL COMMENT 'dry-run 阶段用于关联片段编码',
    template_id BIGINT NOT NULL,
    template_code VARCHAR(64) NOT NULL,
    allocation_task_id BIGINT NOT NULL,
    teaching_task_id BIGINT NULL,
    classroom_id BIGINT NULL,
    teacher_id BIGINT NULL,
    class_group_id BIGINT NULL,
    day_of_week INT NOT NULL,
    period_index INT NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    KEY idx_fragment (template_fragment_id),
    KEY idx_template_time (template_id, day_of_week, period_index),
    KEY idx_template_room_time (template_id, classroom_id, day_of_week, period_index),
    KEY idx_template_class_time (template_id, class_group_id, day_of_week, period_index),
    KEY idx_template_teacher_time (template_id, teacher_id, day_of_week, period_index)
) COMMENT='模板片段实际课段占用表';

CREATE TABLE IF NOT EXISTS schedule_timetable_entry (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    allocation_task_id BIGINT NOT NULL,
    week_number INT NOT NULL,
    template_id BIGINT NOT NULL,
    template_fragment_id BIGINT NOT NULL,
    teaching_task_id BIGINT NULL,
    course_id BIGINT NULL,
    teacher_id BIGINT NULL,
    class_group_id BIGINT NULL,
    classroom_id BIGINT NULL,
    day_of_week INT NOT NULL,
    period_index INT NOT NULL,
    source_type VARCHAR(32) NOT NULL DEFAULT 'TEMPLATE' COMMENT 'TEMPLATE/MANUAL_ADJUSTED',
    status VARCHAR(32) NOT NULL DEFAULT 'ACTIVE',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    KEY idx_week (allocation_task_id, week_number),
    KEY idx_week_class (allocation_task_id, week_number, class_group_id),
    KEY idx_week_teacher (allocation_task_id, week_number, teacher_id),
    KEY idx_week_room (allocation_task_id, week_number, classroom_id)
) COMMENT='最终周课表展开记录表';
