-- ============================================================
-- 教师画像种子数据（固定周矩阵 + 其他说明 + LLM 结构化结果）
-- ============================================================

SET @empty_matrix = '[[0,0,0,0,0,0,0],[0,0,0,0,0,0,0],[0,0,0,0,0,0,0],[0,0,0,0,0,0,0],[0,0,0,0,0,0,0]]';
SET @wed_unavailable_matrix = '[[0,0,-1,0,0,0,0],[0,0,-1,0,0,0,0],[0,0,-1,0,0,0,0],[0,0,-1,0,0,0,0],[0,0,-1,0,0,0,0]]';
SET @fri_afternoon_unavailable_matrix = '[[0,0,0,0,0,0,0],[0,0,0,0,0,0,0],[0,0,0,0,-1,0,0],[0,0,0,0,-1,0,0],[0,0,0,0,-1,0,0]]';

INSERT INTO teacher_profile (teacher_id, availability_matrix_json, profile_note, profile_preference_json)
SELECT id,
       @empty_matrix,
       '希望每周不超过 10 课时，尽量不要集中在同一天。',
       '{"preferredMaxWeeklyHours":10,"preferredMaxDailyHours":null,"preferredMaxConsecutiveHours":null,"avoidFirstPeriod":false,"avoidLastPeriod":false,"preferCompactSchedule":false,"preferredWeekdays":[],"avoidSlots":[],"courseTypePreferences":[],"summary":"教师希望控制周课时负载，并避免单日过度集中。","warnings":[]}'
FROM teacher WHERE employee_no = 'T1001'
ON DUPLICATE KEY UPDATE
    availability_matrix_json = VALUES(availability_matrix_json),
    profile_note = VALUES(profile_note),
    profile_preference_json = VALUES(profile_preference_json);

INSERT INTO teacher_profile (teacher_id, availability_matrix_json, profile_note, profile_preference_json)
SELECT id,
       @wed_unavailable_matrix,
       '周三需参加课题组会议，尽量不要排课；希望课程集中在周一到周四。',
       '{"preferredMaxWeeklyHours":null,"preferredMaxDailyHours":null,"preferredMaxConsecutiveHours":null,"avoidFirstPeriod":false,"avoidLastPeriod":false,"preferCompactSchedule":true,"preferredWeekdays":[1,2,4],"avoidSlots":["周三"],"courseTypePreferences":[],"summary":"教师周三有会议，倾向避开周三并集中排课。","warnings":["周三会议如需作为硬约束，请在固定周矩阵中标记不可用。"]}'
FROM teacher WHERE employee_no = 'T1002'
ON DUPLICATE KEY UPDATE
    availability_matrix_json = VALUES(availability_matrix_json),
    profile_note = VALUES(profile_note),
    profile_preference_json = VALUES(profile_preference_json);

INSERT INTO teacher_profile (teacher_id, availability_matrix_json, profile_note, profile_preference_json)
SELECT id,
       @empty_matrix,
       '实验课尽量安排在下午，理论课上午也可以；希望不要连续上 4 节以上。',
       '{"preferredMaxWeeklyHours":null,"preferredMaxDailyHours":null,"preferredMaxConsecutiveHours":3,"avoidFirstPeriod":false,"avoidLastPeriod":false,"preferCompactSchedule":false,"preferredWeekdays":[],"avoidSlots":[],"courseTypePreferences":[{"courseType":"EXPERIMENT","preferredPeriods":[3,4,5]},{"courseType":"THEORY","preferredPeriods":[1,2,3]}],"summary":"教师倾向实验课下午、理论课上午，并避免过长连续上课。","warnings":[]}'
FROM teacher WHERE employee_no = 'T1003'
ON DUPLICATE KEY UPDATE
    availability_matrix_json = VALUES(availability_matrix_json),
    profile_note = VALUES(profile_note),
    profile_preference_json = VALUES(profile_preference_json);

INSERT INTO teacher_profile (teacher_id, availability_matrix_json, profile_note, profile_preference_json)
SELECT id,
       @empty_matrix,
       '科研任务较多，希望每周不超过 8 课时，尽量避免第 1 节。',
       '{"preferredMaxWeeklyHours":8,"preferredMaxDailyHours":null,"preferredMaxConsecutiveHours":null,"avoidFirstPeriod":true,"avoidLastPeriod":false,"preferCompactSchedule":false,"preferredWeekdays":[],"avoidSlots":[],"courseTypePreferences":[],"summary":"教师希望降低周课时负载，并尽量避免早课。","warnings":[]}'
FROM teacher WHERE employee_no = 'T1004'
ON DUPLICATE KEY UPDATE
    availability_matrix_json = VALUES(availability_matrix_json),
    profile_note = VALUES(profile_note),
    profile_preference_json = VALUES(profile_preference_json);

INSERT INTO teacher_profile (teacher_id, availability_matrix_json, profile_note, profile_preference_json)
SELECT id,
       @empty_matrix,
       '希望课程尽量集中在 2 到 3 天内，不要每天零散排一两节。',
       '{"preferredMaxWeeklyHours":null,"preferredMaxDailyHours":null,"preferredMaxConsecutiveHours":null,"avoidFirstPeriod":false,"avoidLastPeriod":false,"preferCompactSchedule":true,"preferredWeekdays":[],"avoidSlots":[],"courseTypePreferences":[],"summary":"教师倾向紧凑排课，避免过度分散。","warnings":[]}'
FROM teacher WHERE employee_no = 'T1005'
ON DUPLICATE KEY UPDATE
    availability_matrix_json = VALUES(availability_matrix_json),
    profile_note = VALUES(profile_note),
    profile_preference_json = VALUES(profile_preference_json);

INSERT INTO teacher_profile (teacher_id, availability_matrix_json, profile_note, profile_preference_json)
SELECT id,
       @fri_afternoon_unavailable_matrix,
       '周五下午固定参加学院活动，不能排课；其余时间尽量安排在周二或周四。',
       '{"preferredMaxWeeklyHours":12,"preferredMaxDailyHours":null,"preferredMaxConsecutiveHours":null,"avoidFirstPeriod":false,"avoidLastPeriod":true,"preferCompactSchedule":false,"preferredWeekdays":[2,4],"avoidSlots":[],"courseTypePreferences":[],"summary":"教师周五下午不可排，偏好周二或周四。","warnings":[]}'
FROM teacher WHERE employee_no = 'T1006'
ON DUPLICATE KEY UPDATE
    availability_matrix_json = VALUES(availability_matrix_json),
    profile_note = VALUES(profile_note),
    profile_preference_json = VALUES(profile_preference_json);

INSERT INTO teacher_profile (teacher_id, availability_matrix_json, profile_note, profile_preference_json)
SELECT id,
       @empty_matrix,
       '上机课希望安排在下午，尽量不要第 1 节。',
       '{"preferredMaxWeeklyHours":null,"preferredMaxDailyHours":null,"preferredMaxConsecutiveHours":null,"avoidFirstPeriod":true,"avoidLastPeriod":false,"preferCompactSchedule":false,"preferredWeekdays":[],"avoidSlots":[],"courseTypePreferences":[{"courseType":"上机实践课","preferredPeriods":[3,4]}],"summary":"教师偏好下午上机，尽量避开早课。","warnings":[]}'
FROM teacher WHERE employee_no = 'T1007'
ON DUPLICATE KEY UPDATE
    availability_matrix_json = VALUES(availability_matrix_json),
    profile_note = VALUES(profile_note),
    profile_preference_json = VALUES(profile_preference_json);

INSERT INTO teacher_profile (teacher_id, availability_matrix_json, profile_note, profile_preference_json)
SELECT id,
       @empty_matrix,
       '希望不要排晚课，课程尽量分布均衡。',
       '{"preferredMaxWeeklyHours":12,"preferredMaxDailyHours":null,"preferredMaxConsecutiveHours":null,"avoidFirstPeriod":false,"avoidLastPeriod":true,"preferCompactSchedule":false,"preferredWeekdays":[],"avoidSlots":[],"courseTypePreferences":[],"summary":"教师希望避开晚课并保持分布均衡。","warnings":[]}'
FROM teacher WHERE employee_no = 'T1008'
ON DUPLICATE KEY UPDATE
    availability_matrix_json = VALUES(availability_matrix_json),
    profile_note = VALUES(profile_note),
    profile_preference_json = VALUES(profile_preference_json);

INSERT INTO teacher_profile (teacher_id, availability_matrix_json, profile_note, profile_preference_json)
SELECT id,
       @empty_matrix,
       '希望集中在周一、周三、周五，避免课程过于零散。',
       '{"preferredMaxWeeklyHours":14,"preferredMaxDailyHours":null,"preferredMaxConsecutiveHours":null,"avoidFirstPeriod":false,"avoidLastPeriod":false,"preferCompactSchedule":true,"preferredWeekdays":[1,3,5],"avoidSlots":[],"courseTypePreferences":[],"summary":"教师偏好周一、周三、周五并倾向集中排课。","warnings":[]}'
FROM teacher WHERE employee_no = 'T1009'
ON DUPLICATE KEY UPDATE
    availability_matrix_json = VALUES(availability_matrix_json),
    profile_note = VALUES(profile_note),
    profile_preference_json = VALUES(profile_preference_json);

INSERT INTO teacher_profile (teacher_id, availability_matrix_json, profile_note, profile_preference_json)
SELECT id,
       @empty_matrix,
       '科研任务较重，希望每周不超过 8 课时，优先安排上午。',
       '{"preferredMaxWeeklyHours":8,"preferredMaxDailyHours":null,"preferredMaxConsecutiveHours":null,"avoidFirstPeriod":false,"avoidLastPeriod":true,"preferCompactSchedule":false,"preferredWeekdays":[],"avoidSlots":[],"courseTypePreferences":[],"summary":"教师希望控制周课时，偏好上午并避开较晚节次。","warnings":[]}'
FROM teacher WHERE employee_no = 'T1010'
ON DUPLICATE KEY UPDATE
    availability_matrix_json = VALUES(availability_matrix_json),
    profile_note = VALUES(profile_note),
    profile_preference_json = VALUES(profile_preference_json);
