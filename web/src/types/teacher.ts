import type { ActiveStatus } from './status'

export type TeacherRole = 'TEACHER' | 'ADMIN'

export interface Teacher {
  id: number
  employeeNo: string
  password?: string
  role: TeacherRole
  name: string
  department?: string
  title?: string
  maxWeeklyHours: number
  status: ActiveStatus
  createdAt?: string
  updatedAt?: string
  displayName?: string
}
