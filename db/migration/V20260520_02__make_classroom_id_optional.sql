-- 先删除旧外键约束
ALTER TABLE teaching_task DROP FOREIGN KEY fk_teaching_task_classroom;

-- 修改列为可空
ALTER TABLE teaching_task MODIFY COLUMN classroom_id BIGINT NULL;

-- 重新添加外键约束（级联设为 NULL）
ALTER TABLE teaching_task
  ADD CONSTRAINT fk_teaching_task_classroom
    FOREIGN KEY (classroom_id) REFERENCES classroom (id) ON DELETE SET NULL;
