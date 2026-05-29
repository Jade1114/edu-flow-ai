-- Scoring config fields for allocation_task_generation_config
--
-- Adds the missing weight/penalty fields that the new L0-L5 scoring pipeline
-- (scoring.py) reads. Run against the edu_flow_ai database.
--
-- Usage:
--   mysql -u root -p edu_flow_ai < 04-scoring-config-fields-migration.sql
--
-- See: docs/architecture/13-评分体系与约束分层设计.md

ALTER TABLE allocation_task_generation_config
    ADD COLUMN llm_overrides TEXT DEFAULT NULL COMMENT 'JSON: LLM constraint overrides from constraint editor',
    ADD COLUMN model_weight DECIMAL(5,2) DEFAULT 0.60 COMMENT 'L3 LightGBM score weight (alpha) in quality_score',
    ADD COLUMN llm_weight   DECIMAL(5,2) DEFAULT 0.40 COMMENT 'L5 LLM override weight (beta) in quality_score',
    ADD COLUMN same_day_weight         DECIMAL(7,2) DEFAULT 0.05 COMMENT 'L2 S1: penalty per same-day duplicate assignment',
    ADD COLUMN capacity_waste_penalty  DECIMAL(7,2) DEFAULT 0.00 COMMENT 'L2 S8: penalty if capacity_ratio < 0.6 (0=disabled)',
    ADD COLUMN teacher_day_load_penalty DECIMAL(7,2) DEFAULT 0.00 COMMENT 'L2 S5: penalty per extra teacher session on same day',
    ADD COLUMN class_day_load_penalty   DECIMAL(7,2) DEFAULT 0.00 COMMENT 'L2 S6: penalty per extra class session on same day',
    ADD COLUMN teacher_overload_penalty DECIMAL(7,2) DEFAULT 0.00 COMMENT 'L2 S7: penalty if teacher weekly hours > max';

-- Update default values to match scoring.py DEFAULT_CONFIG
UPDATE allocation_task_generation_config
SET
    model_weight = 0.60,
    llm_weight = 0.40,
    same_day_weight = 0.05,
    capacity_waste_penalty = 0.00,
    teacher_day_load_penalty = 0.00,
    class_day_load_penalty = 0.00,
    teacher_overload_penalty = 0.00
WHERE task_id IS NOT NULL;
