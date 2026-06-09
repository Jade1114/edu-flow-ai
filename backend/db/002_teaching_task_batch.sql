-- Add batch/term marker for teaching tasks.
-- Examples: DEFAULT, 2026学期上, 测试用例01, NEXT-2026-FALL.

ALTER TABLE teaching_task
    ADD COLUMN task_batch VARCHAR(64) NOT NULL DEFAULT 'DEFAULT' COMMENT '教学任务批次/学期/测试用例标识' AFTER required_room_type;

ALTER TABLE teaching_task
    ADD KEY idx_teaching_task_batch (task_batch);
