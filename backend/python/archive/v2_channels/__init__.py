"""V2 排课引擎通道模块。

基于候选空间压缩与学习评分引导的高校智能排课架构。

使用方式：
    from python.channels import generate_v2
    
    result = generate_v2(tasks, classrooms, time_slots, 
                         high_cross_teachers=["张彤", "邹建", ...])
"""

from .beam_constructor import construct_timetable
from .teacher_classifier import classify_teachers
from .template_generator import generate_templates
from .room_ranker import rank_rooms

__all__ = ["generate_v2", "construct_timetable", "classify_teachers"]
