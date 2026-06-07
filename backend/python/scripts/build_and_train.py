#!/usr/bin/env python3
"""
从部门课表 Excel 构建训练数据 → 重训 Placement Model。
"""
import csv, json, os, re, sys
from collections import Counter, defaultdict
from pathlib import Path

import lightgbm as lgb
import pandas as pd
import xlrd
from sklearn.model_selection import GroupShuffleSplit

DATA_DIR     = Path(__file__).resolve().parents[2] / "data"
SCHEMA_DIR   = DATA_DIR / "schema01"
PARSED_DIR   = DATA_DIR / "parsed"
TRAIN_DIR    = (DATA_DIR / "training"); TRAIN_DIR.mkdir(parents=True, exist_ok=True)
MODEL_DIR    = Path(__file__).resolve().parents[2] / "models"
OUTPUT_CSV   = TRAIN_DIR / "v3_training_samples.csv"

ALLOWED_CT   = frozenset({"理论课", "上机课"})
FEATURES     = ["course_name_code","course_code_code","teacher_no_code",
                "teacher_name_code","class_name_code","class_major_code",
                "class_department_code","class_grade","class_no",
                "student_count","total_hours","course_type_code",
                "required_room_type_code"]
CSV_FIELDS   = ["source_key","resource_key","course_name","course_code",
                "teacher_no","teacher_no_source","teacher_name","class_name",
                "class_major","class_department","class_grade","class_no",
                "student_count","total_hours","course_type","required_room_type",
                "classroom_name","classroom_type","classroom_capacity",
                "day_of_week","period_index","observed_weeks","source_period_labels"]

def load_jsonl(path):
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]

def by_key(rows, key):
    return {str(r.get(key,"")).strip(): r for r in rows if str(r.get(key,"")).strip()}

def period_index_from_offset(offset):
    return offset + 1  # offset 0 → period 1

def day_from_col(col):
    # col 2-6 → Monday(1), 7-11 → Tuesday(2) ... 32-36 → Sunday(7)
    return (col - 2) // 5 + 1

def parse_title(row0):
    m = re.search(r'(\d{4}级.+?\d+班)', row0)
    cls_name = m.group(1) if m else ""
    m = re.search(r'第\d+学期(.+?)\(学院\)', row0)
    dept = (m.group(1).strip() + "(学院)") if m else ""
    m = re.search(r'(\d+)人', row0)
    stu = int(m.group(1)) if m else 0
    m = re.search(r'\(专业\)', row0)
    major = ""
    if m:
        before = row0[:m.start()]
        parts = re.findall(r'([^()]+)', before)
        if parts: major = parts[-1].strip()
    return cls_name, dept, major, stu

def extract_detail_courses(text):
    """Row 24 → [{code, teachers}]"""
    results = []
    for m in re.finditer(r'(.+?)\(([^)]+)\)\(ID\[\d+\]学分\[([^\]]*)\]\s*时\[([^\]]*)\]\s*师\[([^\]]*)\]\s*室\[([^\]]*)\]', text):
        code = m.group(2).strip()
        teachers = [t.strip() for t in m.group(5).split(",") if t.strip()]
        results.append({"code": code, "teachers": teachers})
    return results

def parse_schedule_cell(val):
    if not val or not isinstance(val, str): return None
    cell = val.strip()
    if not cell: return None
    skip = {"报到注册","国庆节","中秋节","元旦节","期末考试","全国计算机等级考试","大学英语四、六级考试","入学教育","军训","毕业教育","实践周","运动会"}
    if cell in skip or "报到" in cell or "节" in cell or "考试" in cell: return None
    parts = cell.split("\n")
    code = parts[0].strip()
    code_clean = re.sub(r'\(\d+[-\d,]*\)', "", code).strip()
    if not code_clean: return None
    room = ""
    for p in parts[1:]:
        p = p.strip()
        if p and p not in skip: room = p; break
    return (code_clean, room)

# ── Step 1: Parse Excel files → timetable records ──
print("="*50)
print("Step 1: 解析 Excel 课表")
print("="*50)

xls_files = sorted(SCHEMA_DIR.glob("*.xls"))
records = []  # list of dicts
teacher_map_detail = {}  # course_code → [teacher_names] (from Row 24)

for fpath in xls_files:
    wb = xlrd.open_workbook(str(fpath))
    sheet = wb.sheet_by_index(0)
    if sheet.nrows < 25: continue
    title = str(sheet.cell_value(0,0) or "")
    cls_name, dept, major, stu = parse_title(title)
    if not cls_name: continue

    # Parse Row 24
    detail_text = str(sheet.cell_value(24,0) or "")
    for c in extract_detail_courses(detail_text):
        if c["code"] not in teacher_map_detail:
            teacher_map_detail[c["code"]] = c["teachers"]

    # Parse schedule rows (4-23)
    for r in range(4, min(24, sheet.nrows - 1)):
        week = int(float(sheet.cell_value(r,0))) if sheet.cell_value(r,0) else 0
        if week <= 0: continue
        for c in range(2, sheet.ncols):
            parsed = parse_schedule_cell(str(sheet.cell_value(r,c)))
            if not parsed: continue
            code, room = parsed
            day = day_from_col(c)
            offset = (c - 2) % 5
            period = period_index_from_offset(offset)
            records.append({
                "course_code": code, "class_group_name": cls_name,
                "week": week, "day": day, "period": period, "room": room
            })

print(f"  文件数: {len(xls_files)}")
print(f"  原始记录: {len(records)}")

# ── Step 2: Attach teacher from detail map ──
for rec in records:
    rec["teacher_name"] = (teacher_map_detail.get(rec["course_code"]) or [""])[0]

# ── Step 3: Load parsed data ──
print("\nStep 2: 加载解析数据")
courses_raw = by_key(load_jsonl(PARSED_DIR / "courses.jsonl"), "code")
classrooms_raw = by_key(load_jsonl(PARSED_DIR / "classrooms.jsonl"), "name")
class_groups_raw = by_key(load_jsonl(PARSED_DIR / "class_groups.jsonl"), "name")

# ── Step 4: Enrich records & write CSV ──
print("\nStep 3: 构建训练样本")
rows_out = []
skip_ct = Counter()
seen = set()

for rec in records:
    code = rec["course_code"]
    teacher = rec["teacher_name"]
    cls_name = rec["class_group_name"]
    room_name = rec["room"]
    day = rec["day"]
    period = rec["period"]

    course = courses_raw.get(code)
    if not course: skip_ct["no_course"] += 1; continue
    if course.get("course_type") not in ALLOWED_CT: skip_ct["course_type"] += 1; continue

    cg = class_groups_raw.get(cls_name)
    if not cg: skip_ct["no_classgroup"] += 1; continue

    cr = classrooms_raw.get(room_name)
    if not cr:
        # 教室不在 parsed 列表里——动态建一个默认记录
        cr = {"name": room_name, "classroom_type": ("机房" if room_name.startswith("9") else "普通教室")}

    source_key = f"{code}|{teacher}|{cls_name}"
    resource_key = f"{room_name}|{day}|{period}"
    dedup_key = (source_key, resource_key)
    if dedup_key in seen: continue
    seen.add(dedup_key)

    row = {
        "source_key": source_key,
        "resource_key": resource_key,
        "course_name": course.get("name",""),
        "course_code": code,
        "teacher_no": "",
        "teacher_no_source": "",
        "teacher_name": teacher,
        "class_name": cls_name,
        "class_major": cg.get("major",""),
        "class_department": cg.get("department",""),
        "class_grade": cg.get("grade",""),
        "class_no": re.search(r'(\d+)班', cls_name).group(1) if re.search(r'(\d+)班', cls_name) else "",
        "student_count": cg.get("student_count",0),
        "total_hours": 0,
        "course_type": course.get("course_type",""),
        "required_room_type": cr.get("classroom_type","普通教室"),
        "classroom_name": room_name,
        "classroom_type": cr.get("classroom_type","普通教室"),
        "classroom_capacity": 80,
        "day_of_week": day,
        "period_index": period,
        "observed_weeks": str(rec["week"]),
        "source_period_labels": "",
    }
    rows_out.append(row)

print(f"  训练样本: {len(rows_out)}")
print(f"  跳过: {dict(skip_ct)}")

with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=CSV_FIELDS)
    w.writeheader()
    w.writerows(rows_out)
print(f"  CSV 输出: {OUTPUT_CSV}")

# ── Step 5: Train model ──
print("\n" + "="*50)
print("Step 4: 训练 LightGBM 模型")
print("="*50)

def stable_code(value, mod=10007):
    text = str(value or "").strip().lower().replace(" ", "")
    if not text: return 0.0
    total = 0
    for ch in text:
        total = (total * 131 + ord(ch)) % mod
    return float(total + 1)

df = pd.read_csv(OUTPUT_CSV)
df.columns = [str(c).strip() for c in df.columns]
for col in df.select_dtypes(include="object").columns:
    df[col] = df[col].astype(str).str.strip()

resource_keys = sorted(df["resource_key"].astype(str).unique())
label_map = {k: i for i, k in enumerate(resource_keys)}
print(f"  resource_key 类别数: {len(resource_keys)}")

df["label_id"] = df["resource_key"].map(label_map)
df["source_key_str"] = df["source_key"].astype(str)

# Build feature columns
for feat in FEATURES:
    if feat.endswith("_code") and feat not in df.columns:
        base = feat[:-5]  # strip "_code"
        df[feat] = df[base].apply(lambda x: stable_code(x))
    elif feat in ("class_grade", "class_no", "student_count", "total_hours"):
        if feat not in df.columns:
            df[feat] = 0
        df[feat] = pd.to_numeric(df[feat], errors="coerce").fillna(0)

X = df[FEATURES]
y = df["label_id"]
groups = df["class_name"] if "class_name" in df.columns else df["source_key_str"]

if len(X) < 100:
    print("  样本太少，跳过训练")
    sys.exit(0)

try:
    gss = GroupShuffleSplit(n_splits=1, test_size=0.1, random_state=42)
    train_idx, test_idx = next(gss.split(X, y, groups))
except ValueError:
    train_idx = list(range(len(X)))
    test_idx = []

x_train, y_train = X.iloc[train_idx], y.iloc[train_idx]
print(f"  训练集: {len(x_train)}, 测试集: {len(test_idx)}")

model = lgb.LGBMModel(
    objective="multiclass", num_class=len(resource_keys),
    num_leaves=127, learning_rate=0.1, n_estimators=200,
    class_weight="balanced",
    verbosity=-1, random_state=42, n_jobs=-1
)
eval_set = [(X.iloc[test_idx], y.iloc[test_idx])] if len(test_idx) > 0 else [(x_train, y_train)]
model.fit(x_train, y_train, eval_set=eval_set, eval_metric="multi_logloss")

if len(test_idx) > 0:
    acc = (model.predict(X.iloc[test_idx]).argmax(axis=1) == y.iloc[test_idx].values).mean()
    print(f"  hit@1 (test): {acc:.4f}")
    preds = model.predict(X.iloc[test_idx])
    top10 = preds.argsort(axis=1)[:, -10:]
    hit10 = sum(1 for i in range(len(test_idx)) if y.iloc[test_idx].values[i] in top10[i])
    print(f"  hit@10 (test): {hit10/len(test_idx):.4f}")

# Save model
model.booster_.save_model(str(MODEL_DIR / "placement_direct_model.txt"))
schema = {"features": FEATURES, "num_class": len(resource_keys), "feature_importance": {}}
(MODEL_DIR / "placement_direct_schema.json").write_text(json.dumps(schema, ensure_ascii=False), encoding="utf-8")
resource_by_label = {str(idx): rk for rk, idx in label_map.items()}
labels_json = {"resource_by_label": resource_by_label}
(MODEL_DIR / "placement_direct_labels.json").write_text(json.dumps(labels_json, ensure_ascii=False), encoding="utf-8")

print(f"\n✅ 模型已保存到 {MODEL_DIR}/")
print(f"  placement_direct_model.txt")
print(f"  placement_direct_schema.json")
print(f"  placement_direct_labels.json")
