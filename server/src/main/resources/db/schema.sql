CREATE DATABASE IF NOT EXISTS edu_flow_ai
    DEFAULT CHARACTER SET utf8mb4
    DEFAULT COLLATE utf8mb4_unicode_ci;

USE edu_flow_ai;

CREATE TABLE IF NOT EXISTS teacher (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(50) NOT NULL,
    department VARCHAR(100) NOT NULL,
    title VARCHAR(50) NULL,
    max_weekly_hours INT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_teacher_status (status),
    INDEX idx_teacher_name (name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS teacher_profile (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    teacher_id BIGINT NOT NULL,
    skill_text TEXT NULL,
    available_time_text TEXT NULL,
    unavailable_time_text TEXT NULL,
    workload_requirement TEXT NULL,
    special_note TEXT NULL,
    vector_text TEXT NULL,
    vector_indexed BOOLEAN NOT NULL DEFAULT FALSE,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_teacher_profile_teacher (teacher_id),
    CONSTRAINT fk_teacher_profile_teacher FOREIGN KEY (teacher_id) REFERENCES teacher (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS course (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(100) NOT NULL,
    course_type VARCHAR(50) NULL,
    required_hours INT NULL,
    required_skill TEXT NULL,
    description TEXT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
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

CREATE TABLE IF NOT EXISTS allocation_task (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(100) NOT NULL,
    description TEXT NULL,
    priority_rule VARCHAR(100) NULL,
    status VARCHAR(30) NOT NULL DEFAULT 'DRAFT',
    created_by VARCHAR(50) NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_allocation_task_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS allocation_scheme (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    task_id BIGINT NOT NULL,
    scheme_name VARCHAR(100) NOT NULL,
    summary TEXT NULL,
    score INT NULL,
    satisfied_summary TEXT NULL,
    conflict_summary TEXT NULL,
    valid BOOLEAN NOT NULL DEFAULT TRUE,
    status VARCHAR(30) NOT NULL DEFAULT 'CANDIDATE',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_allocation_scheme_task (task_id),
    INDEX idx_allocation_scheme_status (status),
    CONSTRAINT fk_allocation_scheme_task FOREIGN KEY (task_id) REFERENCES allocation_task (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS allocation_item (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    scheme_id BIGINT NOT NULL,
    course_id BIGINT NOT NULL,
    class_group_id BIGINT NOT NULL,
    teacher_id BIGINT NOT NULL,
    classroom_id BIGINT NOT NULL,
    time_slot_id BIGINT NOT NULL,
    valid BOOLEAN NOT NULL DEFAULT TRUE,
    conflict_message TEXT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_allocation_item_scheme (scheme_id),
    INDEX idx_allocation_item_teacher_time (teacher_id, time_slot_id),
    INDEX idx_allocation_item_class_time (class_group_id, time_slot_id),
    INDEX idx_allocation_item_classroom_time (classroom_id, time_slot_id),
    CONSTRAINT fk_allocation_item_scheme FOREIGN KEY (scheme_id) REFERENCES allocation_scheme (id),
    CONSTRAINT fk_allocation_item_course FOREIGN KEY (course_id) REFERENCES course (id),
    CONSTRAINT fk_allocation_item_class_group FOREIGN KEY (class_group_id) REFERENCES class_group (id),
    CONSTRAINT fk_allocation_item_teacher FOREIGN KEY (teacher_id) REFERENCES teacher (id),
    CONSTRAINT fk_allocation_item_classroom FOREIGN KEY (classroom_id) REFERENCES classroom (id),
    CONSTRAINT fk_allocation_item_time_slot FOREIGN KEY (time_slot_id) REFERENCES time_slot (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS course_assignment (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    source_scheme_id BIGINT NULL,
    course_id BIGINT NOT NULL,
    class_group_id BIGINT NOT NULL,
    teacher_id BIGINT NOT NULL,
    classroom_id BIGINT NOT NULL,
    time_slot_id BIGINT NOT NULL,
    status VARCHAR(30) NOT NULL DEFAULT 'ACTIVE',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_course_assignment_scheme (source_scheme_id),
    INDEX idx_course_assignment_teacher_time (teacher_id, time_slot_id),
    INDEX idx_course_assignment_class_time (class_group_id, time_slot_id),
    INDEX idx_course_assignment_classroom_time (classroom_id, time_slot_id),
    INDEX idx_course_assignment_status (status),
    CONSTRAINT fk_course_assignment_scheme FOREIGN KEY (source_scheme_id) REFERENCES allocation_scheme (id),
    CONSTRAINT fk_course_assignment_course FOREIGN KEY (course_id) REFERENCES course (id),
    CONSTRAINT fk_course_assignment_class_group FOREIGN KEY (class_group_id) REFERENCES class_group (id),
    CONSTRAINT fk_course_assignment_teacher FOREIGN KEY (teacher_id) REFERENCES teacher (id),
    CONSTRAINT fk_course_assignment_classroom FOREIGN KEY (classroom_id) REFERENCES classroom (id),
    CONSTRAINT fk_course_assignment_time_slot FOREIGN KEY (time_slot_id) REFERENCES time_slot (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS adjustment_request (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    assignment_id BIGINT NOT NULL,
    teacher_id BIGINT NOT NULL,
    reason TEXT NOT NULL,
    preferred_time_text TEXT NULL,
    preferred_time_slot_id BIGINT NULL,
    preferred_classroom_id BIGINT NULL,
    ai_suggestion TEXT NULL,
    status VARCHAR(30) NOT NULL DEFAULT 'SUBMITTED',
    review_note TEXT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_adjustment_request_assignment (assignment_id),
    INDEX idx_adjustment_request_teacher (teacher_id),
    INDEX idx_adjustment_request_status (status),
    CONSTRAINT fk_adjustment_request_assignment FOREIGN KEY (assignment_id) REFERENCES course_assignment (id),
    CONSTRAINT fk_adjustment_request_teacher FOREIGN KEY (teacher_id) REFERENCES teacher (id),
    CONSTRAINT fk_adjustment_request_preferred_time FOREIGN KEY (preferred_time_slot_id) REFERENCES time_slot (id),
    CONSTRAINT fk_adjustment_request_preferred_classroom FOREIGN KEY (preferred_classroom_id) REFERENCES classroom (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

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
    resolved BOOLEAN NOT NULL DEFAULT FALSE,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_conflict_biz (biz_type, biz_id),
    INDEX idx_conflict_type (conflict_type),
    INDEX idx_conflict_resolved (resolved),
    CONSTRAINT fk_conflict_teacher FOREIGN KEY (related_teacher_id) REFERENCES teacher (id),
    CONSTRAINT fk_conflict_class_group FOREIGN KEY (related_class_group_id) REFERENCES class_group (id),
    CONSTRAINT fk_conflict_classroom FOREIGN KEY (related_classroom_id) REFERENCES classroom (id),
    CONSTRAINT fk_conflict_time_slot FOREIGN KEY (related_time_slot_id) REFERENCES time_slot (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
