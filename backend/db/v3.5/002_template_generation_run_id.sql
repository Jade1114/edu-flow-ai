-- V3.5 template generation batch support
-- Allows multiple V3.5 generations for the same allocation_task to coexist.

ALTER TABLE schedule_template
    ADD COLUMN generation_run_id VARCHAR(64) NULL COMMENT 'V3.5生成批次ID' AFTER allocation_task_id;

ALTER TABLE schedule_template_week
    ADD COLUMN generation_run_id VARCHAR(64) NULL COMMENT 'V3.5生成批次ID' AFTER allocation_task_id;

ALTER TABLE schedule_template_fragment
    ADD COLUMN generation_run_id VARCHAR(64) NULL COMMENT 'V3.5生成批次ID' AFTER allocation_task_id;

ALTER TABLE schedule_template_fragment_slot
    ADD COLUMN generation_run_id VARCHAR(64) NULL COMMENT 'V3.5生成批次ID' AFTER allocation_task_id;

ALTER TABLE schedule_template DROP INDEX uk_allocation_template_code;
ALTER TABLE schedule_template ADD UNIQUE KEY uk_allocation_run_template_code (allocation_task_id, generation_run_id, template_code);

ALTER TABLE schedule_template_week DROP INDEX uk_allocation_week;
ALTER TABLE schedule_template_week ADD UNIQUE KEY uk_allocation_run_week (allocation_task_id, generation_run_id, week_number);

ALTER TABLE schedule_template ADD KEY idx_allocation_run (allocation_task_id, generation_run_id);
ALTER TABLE schedule_template_week ADD KEY idx_allocation_run (allocation_task_id, generation_run_id);
ALTER TABLE schedule_template_fragment ADD KEY idx_allocation_run (allocation_task_id, generation_run_id);
ALTER TABLE schedule_template_fragment_slot ADD KEY idx_allocation_run (allocation_task_id, generation_run_id);
