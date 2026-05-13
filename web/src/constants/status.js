/**
 * 状态常量定义，与后端枚举保持一致。
 * 后端枚举位置：com.yuy.eduflow.enums
 */

// 基础实体活跃状态（教师、课程、教室、教学任务等）
export const ActiveStatus = {
  ACTIVE: 'ACTIVE',
  INACTIVE: 'INACTIVE',
}

// 分课任务状态
export const TaskStatus = {
  DRAFT: 'DRAFT',
  PENDING: 'PENDING',
  CONFIRMED: 'CONFIRMED',
  REJECTED: 'REJECTED',
}

// 分课方案状态
export const SchemeStatus = {
  CANDIDATE: 'CANDIDATE',
  CONFIRMED: 'CONFIRMED',
  REJECTED: 'REJECTED',
}

// 课表安排状态
export const AssignmentStatus = {
  ACTIVE: 'ACTIVE',
  INACTIVE: 'INACTIVE',
}

// 教师角色
export const TeacherRole = {
  TEACHER: 'TEACHER',
  ADMIN: 'ADMIN',
}
