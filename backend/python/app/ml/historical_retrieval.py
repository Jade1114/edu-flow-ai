"""
Historical timetable retrieval for placement candidates.

Instead of training a model to predict (room, day, period), this module
directly retrieves historical assignments for similar tasks from the
actual timetable data (allocation_items.jsonl).
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

DATA_DIR = Path(__file__).resolve().parents[3] / "data"
ALLOC_PATH = DATA_DIR / "allocation_items.jsonl"

# 公共课代码（排除）
PUBLIC_CODES = {
    '形027','形029','形031','形033','形154',
    '思040','军010','毛927','中019',
    '大002','大003','大004','大006','大008','大035',
    '学312','工034','概037','沟048','高038',
}


class HistoricalRetrievalModel:
    """直接检索历史排课记录的候选推荐器。"""

    def __init__(self):
        self.course_index: dict[str, list[dict]] = {}   # course_code → 历史记录
        self.teacher_index: dict[str, list[dict]] = {}  # teacher_name → 历史记录
        self.all_records: list[dict] = []

    @classmethod
    def load(cls) -> "HistoricalRetrievalModel":
        """从 allocation_items.jsonl 加载历史排课记录。"""
        m = cls()
        if not ALLOC_PATH.exists():
            raise FileNotFoundError(f"Historical timetable not found: {ALLOC_PATH}")

        seen = set()
        for line in ALLOC_PATH.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            rec = json.loads(line)
            # 过滤公共课
            if rec.get("course_code") in PUBLIC_CODES:
                continue
            # 去重：同一 (course_code, teacher, class_group, week, day, period, room) 只保留一次
            key = (rec.get("course_code"), rec.get("teacher_name"),
                   rec.get("room_name"), rec.get("day_of_week"), rec.get("period_index"))
            if key in seen:
                continue
            seen.add(key)
            m.all_records.append(rec)
            # 按课程代码索引
            code = rec.get("course_code", "")
            if code not in m.course_index:
                m.course_index[code] = []
            m.course_index[code].append(rec)
            # 按教师名索引
            teacher = rec.get("teacher_name", "")
            if teacher not in m.teacher_index:
                m.teacher_index[teacher] = []
            m.teacher_index[teacher].append(rec)

        return m

    def predict_topk(self, task_like: dict[str, Any], *, top_k: int) -> list[tuple[str, float]]:
        """检索历史排课记录，返回 top-k (room, day, period) 候选。

        Args:
            task_like: 包含 course_code, teacher_name 等字段的 dict
            top_k: 返回候选数
        Returns:
            [(resource_key, score)] 列表，resource_key 格式为 "room|day|period"
        """
        candidates: dict[str, float] = {}
        code = str(task_like.get("course_code", ""))
        teacher = str(task_like.get("teacher_name", ""))

        # 1. 精确匹配：同一门课的历史记录
        for rec in self.course_index.get(code, []):
            key = f"{rec['room_name']}|{rec['day_of_week']}|{rec['period_index']}"
            candidates[key] = candidates.get(key, 0) + 1.0

        # 2. 教师匹配：同一教师的其他课历史记录
        for rec in self.teacher_index.get(teacher, []):
            key = f"{rec['room_name']}|{rec['day_of_week']}|{rec['period_index']}"
            candidates[key] = candidates.get(key, 0) + 0.5

        # 3. 按频率排序
        ranked = sorted(candidates.items(), key=lambda x: -x[1])
        
        # 4. 补充分散：如果候选不够，从所有可用 (day, period, room) 里随机取
        if len(ranked) < top_k:
            existing = set(k for k, _ in ranked)
            # 遍历所有教师历史记录做补充
            for rec in self.teacher_index.get(teacher, []):
                key = f"{rec['room_name']}|{rec['day_of_week']}|{rec['period_index']}"
                if key not in existing:
                    ranked.append((key, 0.01))
                    existing.add(key)
                if len(ranked) >= top_k:
                    break
        
        # 5. 还不够就遍历所有记录
        if len(ranked) < top_k:
            for rec in self.all_records:
                key = f"{rec['room_name']}|{rec['day_of_week']}|{rec['period_index']}"
                if key not in existing:
                    ranked.append((key, 0.005))
                    existing.add(key)
                if len(ranked) >= top_k:
                    break

        return ranked[:top_k]
