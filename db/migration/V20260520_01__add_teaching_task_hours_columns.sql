ALTER TABLE conflict_check_result
  ADD COLUMN teaching_task_id BIGINT NULL AFTER related_time_slot_id,
  ADD COLUMN course_name VARCHAR(200) NULL AFTER teaching_task_id,
  ADD COLUMN expected_hours INT NULL AFTER course_name,
  ADD COLUMN actual_hours INT NULL AFTER expected_hours,
  ADD INDEX idx_ccr_teaching_task (teaching_task_id);
