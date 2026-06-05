-- V3 stress/feasibility mode fields for allocation_task_generation_config.
-- Safe for existing demo databases that already contain the V3 tuning fields.

ALTER TABLE allocation_task_generation_config
    ADD COLUMN generation_mode VARCHAR(32) NOT NULL DEFAULT 'QUALITY'
    COMMENT 'V3 运行模式：FEASIBILITY/QUALITY/STRESS'
    AFTER solver_time_limit_seconds;

UPDATE allocation_task_generation_config
SET generation_mode = 'QUALITY'
WHERE generation_mode IS NULL OR generation_mode = '';
