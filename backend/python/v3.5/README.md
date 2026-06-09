# V3.5 Placement 实验区

当前目录先作为 V3.5 排课方案的实验沙盒，不急着拆到正式模块。

## 一键 Pipeline

```bash
cd backend/python
source .venv/bin/activate
python v3.5/run_pipeline.py --allocation-task-id 1 --total-weeks 18 --top-k 300 --max-templates 8
```

默认复用现有单模型，不重训、不写 DB；如果要重训模型，加 `--train-model`；如果要入库，加 `--import-db --truncate-db`。

默认输出：

```text
backend/models/v3.5/placement/pipeline_summary.json
backend/models/v3.5/placement/runs/<timestamp>/pipeline_summary.json
```

当前 smoke test 结果：`846` 个规律任务全部覆盖，`2` 份模板，DB draft 验收问题为 `0`。

## Placement 模型

文件：

- `placement_single_model.py`：当前主推方案，单模型直接预测 `resource_key = classroom|day|period`。
- `placement_model.py`：早期两阶段实验版，先预测 slot 再预测 room。

模型契约：

```text
input  = teaching-task features
output = TopK weekly-template placements: classroom_name | day_of_week | period_index
```

当前单模型结构：

1. 输入教学任务特征。
2. LightGBM 直接预测 `resource_key = classroom_name|day_of_week|period_index`。
3. 输出 TopK 候选：`resource_key`, `classroom_name`, `day_of_week`, `period_index`, `score`。
4. 后续由周模板排课器或 CP-SAT 处理全局冲突。

## 样本清洗

```bash
cd backend/python
source .venv/bin/activate
python v3.5/clean_training_samples.py
```

默认输出：

```text
backend/models/v3.5/placement/clean_training_samples.jsonl
backend/models/v3.5/placement/dropped_training_samples.jsonl
backend/models/v3.5/placement/clean_training_report.json
```

## 训练

```bash
cd backend/python
source .venv/bin/activate
python v3.5/placement_single_model.py train --data ../models/v3.5/placement/clean_training_samples.jsonl --rounds 160
```

推荐读取：

```text
backend/models/v3.5/placement/clean_training_samples.jsonl
```

默认输出：

```text
backend/models/v3.5/placement_single/
```

## 推理样例

```bash
cd backend/python
source .venv/bin/activate
python v3.5/placement_single_model.py predict-sample --index 0 --top-k 20
```

## 质量评估

```bash
cd backend/python
source .venv/bin/activate
python v3.5/evaluate_placement_quality.py \
  --model-type single \
  --data ../models/v3.5/placement/clean_training_samples.jsonl \
  --model-dir ../models/v3.5/placement_single \
  --report ../models/v3.5/placement_single/quality_report.json
```

默认输出：

```text
backend/models/v3.5/placement/quality_report.json
```

评估内容：

- TopK 是否命中真实历史资源/slot。
- Top1 placement 的资源重复率。
- Top1 placement 的教师、班级、教室模板冲突。
- TopK 候选池整体资源重复率。

## Pattern 构建

```bash
cd backend/python
source .venv/bin/activate
python v3.5/pattern_builder.py
python v3.5/validate_patterns.py
```

默认输出：

```text
backend/models/v3.5/placement/task_patterns.jsonl
backend/models/v3.5/placement/pattern_report.json
backend/models/v3.5/placement/pattern_validation_report.json
```

当前清洗样本里的 `total_hours` 全是 `0`，所以 Pattern 暂时从真实历史 `observed_weeks + slot` 反推；后续接真实 teaching_tasks 后优先走课时规则。

默认过滤 `weekly_slot_count > 6` 的特殊任务，输出到：

```text
backend/models/v3.5/placement/dropped_task_patterns.jsonl
```

这类任务通常是军训、校企实训、集中实践等非规律课程，先交给教务手动处理，不进入自动排课 Pattern 库。

## Template v1 构建

```bash
cd backend/python
source .venv/bin/activate
python v3.5/template_builder_v1.py --top-k 300 --repair-depth 0
python v3.5/validate_template_v1.py
```

默认输出：

```text
backend/models/v3.5/placement/template_v1.json
backend/models/v3.5/placement/template_v1_unresolved.jsonl
backend/models/v3.5/placement/template_v1_report.json
backend/models/v3.5/placement/template_v1_validation_report.json
```

v1 当前按 `Placement TopK → fallback 全局扫描` 填充，保证已填片段无教师/班级/教室硬冲突；置换 repair 暂时关闭，后续单独实现。若要关闭保底扫描，可加 `--disable-fallback`。

## Template Cover v1

```bash
cd backend/python
source .venv/bin/activate
python v3.5/template_cover_v1.py --top-k 300 --max-templates 8
python v3.5/validate_template_cover_v1.py
```

默认输出：

```text
backend/models/v3.5/placement/template_cover_v1.json
backend/models/v3.5/placement/template_cover_v1_report.json
backend/models/v3.5/placement/template_cover_v1_unresolved.jsonl
backend/models/v3.5/placement/template_cover_v1_validation_report.json
```

Cover v1 每轮只处理剩余未完成任务；已生成的前序模板不回滚、不挪动。当前测试用 2 份模板覆盖 846 个规律任务，验收硬冲突为 0。

## DB Dry-run 导出

```bash
cd backend/python
source .venv/bin/activate
python v3.5/export_template_cover_db_draft.py --allocation-task-id 1 --total-weeks 18
python v3.5/validate_db_draft_export.py
```

默认输出：

```text
backend/models/v3.5/placement/db_draft/schedule_templates.jsonl
backend/models/v3.5/placement/db_draft/schedule_template_weeks.jsonl
backend/models/v3.5/placement/db_draft/schedule_template_fragments.jsonl
backend/models/v3.5/placement/db_draft/schedule_template_fragment_slots.jsonl
backend/models/v3.5/placement/db_draft/export_report.json
backend/models/v3.5/placement/db_draft/validation_report.json
```

当前 dry-run 导出 2 个模板、18 周映射、1214 个模板片段、1791 个实际课段占用，验收引用问题为 0。

## DB Draft 查询与换周模拟

```bash
cd backend/python
source .venv/bin/activate
python v3.5/query_db_draft_timetable.py --week 5 --swap 5 8
```

默认输出：

```text
backend/models/v3.5/placement/db_draft/week_query_result.json
backend/models/v3.5/placement/db_draft/week_swap_simulation.json
```

该脚本用于验证：只交换 `schedule_template_week` 中两周的模板映射，模板片段和课段占用不变，但对应周课表会跟着切换。

## DB Insert Dry-run

```bash
cd backend/python
source .venv/bin/activate
python v3.5/import_db_draft_to_mysql.py
```

默认只检查 JSONL 和目标表，不写入数据库。真实执行需要先建表：

```bash
mysql < backend/db/v3.5/001_schedule_template_tables.sql
```

确认后再执行：

```bash
cd backend/python
source .venv/bin/activate
python v3.5/import_db_draft_to_mysql.py --execute --truncate
```

当前已完成真实入库：`2 / 18 / 1214 / 1791`。

## Java 查询接口

```text
GET /api/allocation-tasks/{allocationTaskId}/templates
GET /api/allocation-tasks/{allocationTaskId}/templates/weeks
GET /api/allocation-tasks/{allocationTaskId}/templates/weeks/{weekNumber}
GET /api/allocation-tasks/{allocationTaskId}/templates/weeks/{weekNumber}/timetable
```

当前 Java 后端已新增只读查询接口，并通过：

```bash
cd backend/java
mvn -q -DskipTests compile
```

## 班级课表 Excel 导入预处理

第一步只做文件解析，不写数据库、不调用 LLM：

```bash
cd backend/python
source .venv/bin/activate
python v3.5/parse_schedule_excel.py \
  --input /path/to/class_schedule.xlsx \
  --output-dir ../data/parsed/schedule_imports/demo \
  --task-batch 2026学期上
```

输出：`courses.csv`、`teachers.csv`、`classrooms.csv`、`class_groups.csv`、`teaching_tasks.csv`、`timetable_occurrences.csv`、`parse_report.json`。

再转 JSONL：

```bash
python v3.5/csv_to_jsonl.py --input-dir ../data/parsed/schedule_imports/demo
```

## 当前边界

- 这是 V3.5 的第一版 placement MVP，只负责生成周模板候选。
- 不处理教师/班级/教室全局冲突，冲突留给后续周模板分配器或 CP-SAT。
- 暂时不接入生产 V3 pipeline。
