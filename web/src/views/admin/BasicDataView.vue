<script setup>
import { ref, onMounted, computed, watch } from 'vue'
import request from '@/api/request.js'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ActiveStatus } from '@/constants/status.js'

const activeTab = ref('teachingTask')
watch(activeTab, (newTab, oldTab) => {
  console.log('从 ${oldTab} 切到了 ${newTab}')
})

// TeachingTask
const teachingTasks = ref([])
const teachingTaskDialog = ref(false)
const teachingTaskFormRef = ref()
const teachingTaskForm = ref({
  id: null,
  courseId: '',
  primaryTeacherId: '',
  assistantTeacherId: '',
  classroomId: '',
  totalHours: 32,
  notes: '',
  status: ActiveStatus.ACTIVE,
  classGroupIds: [],
})
const teachingTaskRules = {
  courseId: [{ required: true, message: '请选择课程', trigger: 'change' }],
  primaryTeacherId: [{ required: true, message: '请选择主讲教师', trigger: 'change' }],
  totalHours: [{ required: true, message: '请输入总课时', trigger: 'blur' }],
  classGroupIds: [{ required: true, message: '请选择班级', trigger: 'change' }],
}

async function loadTeachingTasks() {
  teachingTasks.value = await request.get('/api/teaching-tasks')
}
function openTeachingTaskDialog(row) {
  if (row) {
    teachingTaskForm.value = {
      id: row.id,
      courseId: row.courseId || '',
      primaryTeacherId: row.primaryTeacherId || '',
      assistantTeacherId: row.assistantTeacherId || '',
      classroomId: row.classroomId || '',
      totalHours: row.totalHours || 32,
      notes: row.notes || '',
      status: row.status || 'ACTIVE',
      classGroupIds: row.classGroups ? row.classGroups.map((cg) => cg.id) : [],
    }
  } else {
    teachingTaskForm.value = {
      id: null,
      courseId: '',
      primaryTeacherId: '',
      assistantTeacherId: '',
      classroomId: '',
      totalHours: 32,
      notes: '',
      status: ActiveStatus.ACTIVE,
      classGroupIds: [],
    }
  }
  teachingTaskDialog.value = true
}
function optionalId(value) {
  return value === '' || value === undefined ? null : value
}

async function saveTeachingTask() {
  const valid = await teachingTaskFormRef.value?.validate().catch(() => false)
  if (!valid) return
  const payload = { ...teachingTaskForm.value }
  payload.classroomId = optionalId(payload.classroomId)
  payload.assistantTeacherId = optionalId(payload.assistantTeacherId)
  if (payload.id) {
    await request.put(`/api/teaching-tasks/${payload.id}`, payload)
  } else {
    await request.post('/api/teaching-tasks', payload)
  }
  ElMessage.success('保存成功')
  teachingTaskDialog.value = false
  loadTeachingTasks()
}
async function deleteTeachingTask(id) {
  await ElMessageBox.confirm('确认删除该教学任务？', '提示', {
    type: 'warning',
  })
  await request.delete(`/api/teaching-tasks/${id}`)
  ElMessage.success('删除成功')
  loadTeachingTasks()
}

// Teacher
const teachers = ref([])
const teacherDialog = ref(false)
const teacherFormRef = ref()
const teacherForm = ref({
  id: null,
  employeeNo: '',
  name: '',
  department: '',
  title: '',
  maxWeeklyHours: 8,
  status: ActiveStatus.ACTIVE,
  password: '123456',
  role: 'TEACHER',
})
const teacherRules = {
  employeeNo: [{ required: true, message: '请输入工号', trigger: 'blur' }],
  name: [{ required: true, message: '请输入姓名', trigger: 'blur' }],
  department: [{ required: true, message: '请输入部门', trigger: 'blur' }],
}

async function loadTeachers() {
  teachers.value = await request.get('/api/teachers')
}
function openTeacherDialog(row) {
  if (row) {
    teacherForm.value = { ...row, password: '' }
  } else {
    teacherForm.value = {
      id: null,
      employeeNo: '',
      name: '',
      department: '',
      title: '',
      maxWeeklyHours: 8,
      status: ActiveStatus.ACTIVE,
      password: '123456',
      role: 'TEACHER',
    }
  }
  teacherDialog.value = true
}
async function saveTeacher() {
  const valid = await teacherFormRef.value?.validate().catch(() => false)
  if (!valid) return
  if (teacherForm.value.id) {
    await request.put(`/api/teachers/${teacherForm.value.id}`, teacherForm.value)
  } else {
    await request.post('/api/teachers', teacherForm.value)
  }
  ElMessage.success('保存成功')
  teacherDialog.value = false
  loadTeachers()
}
async function deleteTeacher(id) {
  await ElMessageBox.confirm('确认删除该教师？', '提示', { type: 'warning' })
  await request.delete(`/api/teachers/${id}`)
  ElMessage.success('删除成功')
  loadTeachers()
}

// Course
const courses = ref([])
const courseDialog = ref(false)
const courseFormRef = ref()
const courseForm = ref({
  id: null,
  name: '',
  courseType: '',
  requiredHours: 32,
  description: '',
  status: ActiveStatus.ACTIVE,
})
const courseRules = {
  name: [{ required: true, message: '请输入课程名称', trigger: 'blur' }],
}

async function loadCourses() {
  courses.value = await request.get('/api/courses')
}
function openCourseDialog(row) {
  courseForm.value = row
    ? { ...row }
    : {
        id: null,
        name: '',
        courseType: '',
        requiredHours: 32,
        description: '',
        status: ActiveStatus.ACTIVE,
      }
  courseDialog.value = true
}
async function saveCourse() {
  const valid = await courseFormRef.value?.validate().catch(() => false)
  if (!valid) return
  if (courseForm.value.id) {
    await request.put(`/api/courses/${courseForm.value.id}`, courseForm.value)
  } else {
    await request.post('/api/courses', courseForm.value)
  }
  ElMessage.success('保存成功')
  courseDialog.value = false
  loadCourses()
}
async function deleteCourse(id) {
  await ElMessageBox.confirm('确认删除该课程？', '提示', { type: 'warning' })
  await request.delete(`/api/courses/${id}`)
  ElMessage.success('删除成功')
  loadCourses()
}

// ClassGroup
const classGroups = ref([])
const classGroupDialog = ref(false)
const classGroupFormRef = ref()
const classGroupForm = ref({
  id: null,
  name: '',
  major: '',
  grade: '',
  studentCount: 0,
  description: '',
})
const classGroupRules = {
  name: [{ required: true, message: '请输入班级名称', trigger: 'blur' }],
}

async function loadClassGroups() {
  classGroups.value = await request.get('/api/class-groups')
}
function openClassGroupDialog(row) {
  classGroupForm.value = row
    ? { ...row }
    : {
        id: null,
        name: '',
        major: '',
        grade: '',
        studentCount: 0,
        description: '',
      }
  classGroupDialog.value = true
}
async function saveClassGroup() {
  const valid = await classGroupFormRef.value?.validate().catch(() => false)
  if (!valid) return
  if (classGroupForm.value.id) {
    await request.put(`/api/class-groups/${classGroupForm.value.id}`, classGroupForm.value)
  } else {
    await request.post('/api/class-groups', classGroupForm.value)
  }
  ElMessage.success('保存成功')
  classGroupDialog.value = false
  loadClassGroups()
}
async function deleteClassGroup(id) {
  await ElMessageBox.confirm('确认删除该班级？', '提示', { type: 'warning' })
  await request.delete(`/api/class-groups/${id}`)
  ElMessage.success('删除成功')
  loadClassGroups()
}

// Classroom
const loadingClassrooms = ref(false)
const classroomSearch = ref('')
const filteredClassrooms = computed(() => {
  const keyword = classroomSearch.value.trim().toLowerCase()
  if (!keyword) return classrooms.value
  return classrooms.value.filter(
    (c) =>
      c.name.toLowerCase().includes(keyword) ||
      c.building.toLowerCase().includes(keyword) ||
      c.classroomType.toLowerCase().includes(keyword),
  )
})
const classrooms = ref([])
const classroomDialog = ref(false)
const classroomFormRef = ref()
const classroomForm = ref({
  id: null,
  name: '',
  building: '',
  capacity: 60,
  classroomType: '普通教室',
  status: ActiveStatus.ACTIVE,
})
const classroomRules = {
  name: [{ required: true, message: '请输入教室名称', trigger: 'blur' }],
}

async function loadClassrooms() {
  loadingClassrooms.value = true
  try {
    classrooms.value = await request.get('/api/classrooms')
  } finally {
    loadingClassrooms.value = false
  }
}
function openClassroomDialog(row) {
  classroomForm.value = row
    ? { ...row }
    : {
        id: null,
        name: '',
        building: '',
        capacity: 60,
        classroomType: '普通教室',
        status: ActiveStatus.ACTIVE,
      }
  classroomDialog.value = true
}
async function saveClassroom() {
  const valid = await classroomFormRef.value?.validate().catch(() => false)
  if (!valid) return
  if (classroomForm.value.id) {
    await request.put(`/api/classrooms/${classroomForm.value.id}`, classroomForm.value)
  } else {
    await request.post('/api/classrooms', classroomForm.value)
  }
  ElMessage.success('保存成功')
  classroomDialog.value = false
  loadClassrooms()
}
async function deleteClassroom(id) {
  await ElMessageBox.confirm('确认删除该教室？', '提示', { type: 'warning' })
  await request.delete(`/api/classrooms/${id}`)
  ElMessage.success('删除成功')
  loadClassrooms()
}

onMounted(() => {
  loadTeachers()
  loadCourses()
  loadClassGroups()
  loadClassrooms()
  loadTeachingTasks()
})
</script>

<template>
  <div>
    <h2>基础数据管理</h2>
    <el-tabs v-model="activeTab" style="margin-top: 16px">
      <!-- TeachingTask -->
      <el-tab-pane label="教学任务" name="teachingTask">
        <div style="margin-bottom: 12px">
          <el-button type="primary" @click="openTeachingTaskDialog()">新增教学任务 </el-button>
        </div>
        <el-table :data="teachingTasks" border size="small">
          <el-table-column prop="id" label="ID" width="60" />
          <el-table-column prop="course.name" label="课程" />
          <el-table-column prop="primaryTeacher.name" label="主讲教师" />
          <el-table-column prop="assistantTeacher.name" label="协作教师" />
          <el-table-column prop="totalHours" label="总课时" width="80" />
          <el-table-column label="教室" show-overflow-tooltip>
            <template #default="{ row }">
              {{ row.classroom ? `${row.classroom.name}(${row.classroom.capacity}座)` : '-' }}
            </template>
          </el-table-column>
          <el-table-column label="班级" show-overflow-tooltip>
            <template #default="{ row }">
              {{ row.classGroups?.map((cg) => cg.name).join(', ') || '-' }}
            </template>
          </el-table-column>
          <el-table-column label="状态" width="80">
            <template #default="{ row }">
              <el-tag :type="row.status === 'ACTIVE' ? 'success' : 'info'">
                {{ row.status === 'ACTIVE' ? '启用' : '停用' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="140">
            <template #default="{ row }">
              <el-button type="primary" size="small" @click="openTeachingTaskDialog(row)"
                >编辑</el-button
              >
              <el-button type="danger" size="small" @click="deleteTeachingTask(row.id)"
                >删除</el-button
              >
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <!-- Teacher -->
      <el-tab-pane label="教师管理" name="teacher">
        <div style="margin-bottom: 12px; display: flex; gap: 8px; align-items: center">
          <el-button type="primary" @click="openTeacherDialog()">新增教师</el-button>
        </div>
        <el-table :data="teachers" border size="small">
          <el-table-column prop="employeeNo" label="工号" width="100" />
          <el-table-column prop="name" label="姓名" width="100" />
          <el-table-column prop="department" label="部门" />
          <el-table-column prop="title" label="职称" width="100" />
          <el-table-column prop="maxWeeklyHours" label="最大周课时" width="100" />
          <el-table-column prop="role" label="角色" width="100" />
          <el-table-column label="状态" width="80">
            <template #default="{ row }">
              <el-tag :type="row.status === 'ACTIVE' ? 'success' : 'info'">
                {{ row.status === 'ACTIVE' ? '启用' : '停用' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="160">
            <template #default="{ row }">
              <el-button type="primary" size="small" @click="openTeacherDialog(row)"
                >编辑</el-button
              >
              <el-button type="danger" size="small" @click="deleteTeacher(row.id)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <!-- Course -->
      <el-tab-pane label="课程管理" name="course">
        <div style="margin-bottom: 12px">
          <el-button type="primary" @click="openCourseDialog()">新增课程</el-button>
        </div>
        <el-table :data="courses" border size="small">
          <el-table-column prop="name" label="课程名称" />
          <el-table-column prop="courseType" label="课程类型" width="120" />
          <el-table-column prop="requiredHours" label="学时" width="80" />
          <el-table-column prop="description" label="描述" show-overflow-tooltip />
          <el-table-column label="状态" width="80">
            <template #default="{ row }">
              <el-tag :type="row.status === 'ACTIVE' ? 'success' : 'info'">
                {{ row.status === 'ACTIVE' ? '启用' : '停用' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="140">
            <template #default="{ row }">
              <el-button type="primary" size="small" @click="openCourseDialog(row)">编辑</el-button>
              <el-button type="danger" size="small" @click="deleteCourse(row.id)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <!-- ClassGroup -->
      <el-tab-pane label="班级管理" name="classGroup">
        <div style="margin-bottom: 12px">
          <el-button type="primary" @click="openClassGroupDialog()">新增班级</el-button>
        </div>
        <el-table :data="classGroups" border size="small">
          <el-table-column prop="name" label="班级名称" />
          <el-table-column prop="major" label="专业" />
          <el-table-column prop="grade" label="年级" width="100" />
          <el-table-column prop="studentCount" label="人数" width="80" />
          <el-table-column label="操作" width="140">
            <template #default="{ row }">
              <el-button type="primary" size="small" @click="openClassGroupDialog(row)"
                >编辑</el-button
              >
              <el-button type="danger" size="small" @click="deleteClassGroup(row.id)"
                >删除</el-button
              >
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <!-- Classroom -->
      <el-tab-pane label="教室管理" name="classroom">
        <div style="margin-bottom: 12px">
          <el-button type="primary" @click="openClassroomDialog()">新增教室</el-button>
          <el-input
            v-model="classroomSearch"
            placeholder="搜索教室名称,类型或者教学楼"
            clearable
            style="width: 240px; margin-left: 12px"
          />
        </div>
        <el-table :data="filteredClassrooms" v-loading="loadingClassrooms" border size="small">
          <template #empty>
            <el-empty description="暂无教室数据" />
          </template>
          <el-table-column prop="name" label="教室名称" />
          <el-table-column prop="building" label="教学楼" />
          <el-table-column prop="capacity" label="容量" width="80" />
          <el-table-column prop="classroomType" label="类型" width="120" />
          <el-table-column prop="status" label="状态" width="80">
            <template #default="{ row }">
              <el-tag :type="row.status === 'ACTIVE' ? 'success' : 'info'">
                {{ row.status === 'ACTIVE' ? '启用' : '停用' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="140">
            <template #default="{ row }">
              <el-button type="primary" size="small" @click="openClassroomDialog(row)"
                >编辑</el-button
              >
              <el-button type="danger" size="small" @click="deleteClassroom(row.id)"
                >删除</el-button
              >
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>
    </el-tabs>

    <!-- Teacher Dialog -->
    <el-dialog
      v-model="teacherDialog"
      :title="teacherForm.id ? '编辑教师' : '新增教师'"
      width="480px"
    >
      <el-form ref="teacherFormRef" :model="teacherForm" :rules="teacherRules" label-width="100px">
        <el-form-item label="工号" prop="employeeNo">
          <el-input v-model="teacherForm.employeeNo" :disabled="!!teacherForm.id" />
        </el-form-item>
        <el-form-item label="姓名" prop="name">
          <el-input v-model="teacherForm.name" />
        </el-form-item>
        <el-form-item label="部门" prop="department">
          <el-input v-model="teacherForm.department" />
        </el-form-item>
        <el-form-item label="职称">
          <el-input v-model="teacherForm.title" />
        </el-form-item>
        <el-form-item label="最大周课时">
          <el-input-number v-model="teacherForm.maxWeeklyHours" :min="1" :max="40" />
        </el-form-item>
        <el-form-item label="角色">
          <el-select v-model="teacherForm.role">
            <el-option label="教师" value="TEACHER" />
            <el-option label="管理员" value="ADMIN" />
          </el-select>
        </el-form-item>
        <el-form-item label="密码" v-if="!teacherForm.id">
          <el-input v-model="teacherForm.password" />
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="teacherForm.status">
            <el-option label="启用" :value="ActiveStatus.ACTIVE" />
            <el-option label="停用" :value="ActiveStatus.INACTIVE" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="teacherDialog = false">取消</el-button>
        <el-button type="primary" @click="saveTeacher">保存</el-button>
      </template>
    </el-dialog>

    <!-- Course Dialog -->
    <el-dialog
      v-model="courseDialog"
      :title="courseForm.id ? '编辑课程' : '新增课程'"
      width="480px"
    >
      <el-form ref="courseFormRef" :model="courseForm" :rules="courseRules" label-width="100px">
        <el-form-item label="课程名称" prop="name">
          <el-input v-model="courseForm.name" />
        </el-form-item>
        <el-form-item label="课程类型">
          <el-input v-model="courseForm.courseType" />
        </el-form-item>
        <el-form-item label="学时">
          <el-input-number v-model="courseForm.requiredHours" :min="1" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="courseForm.description" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="courseForm.status">
            <el-option label="启用" :value="ActiveStatus.ACTIVE" />
            <el-option label="停用" :value="ActiveStatus.INACTIVE" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="courseDialog = false">取消</el-button>
        <el-button type="primary" @click="saveCourse">保存</el-button>
      </template>
    </el-dialog>

    <!-- ClassGroup Dialog -->
    <el-dialog
      v-model="classGroupDialog"
      :title="classGroupForm.id ? '编辑班级' : '新增班级'"
      width="480px"
    >
      <el-form
        ref="classGroupFormRef"
        :model="classGroupForm"
        :rules="classGroupRules"
        label-width="100px"
      >
        <el-form-item label="班级名称" prop="name">
          <el-input v-model="classGroupForm.name" />
        </el-form-item>
        <el-form-item label="专业">
          <el-input v-model="classGroupForm.major" />
        </el-form-item>
        <el-form-item label="年级">
          <el-input v-model="classGroupForm.grade" />
        </el-form-item>
        <el-form-item label="人数">
          <el-input-number v-model="classGroupForm.studentCount" :min="0" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="classGroupForm.description" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="classGroupDialog = false">取消</el-button>
        <el-button type="primary" @click="saveClassGroup">保存</el-button>
      </template>
    </el-dialog>

    <!-- Classroom Dialog -->
    <el-dialog
      v-model="classroomDialog"
      :title="classroomForm.id ? '编辑教室' : '新增教室'"
      width="480px"
    >
      <el-form
        ref="classroomFormRef"
        :model="classroomForm"
        :rules="classroomRules"
        label-width="100px"
      >
        <el-form-item label="教室名称" prop="name">
          <el-input v-model="classroomForm.name" />
        </el-form-item>
        <el-form-item label="教学楼">
          <el-input v-model="classroomForm.building" />
        </el-form-item>
        <el-form-item label="容量">
          <el-input-number v-model="classroomForm.capacity" :min="1" />
        </el-form-item>
        <el-form-item label="类型">
          <el-input v-model="classroomForm.classroomType" />
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="classroomForm.status">
            <el-option label="启用" :value="ActiveStatus.ACTIVE" />
            <el-option label="停用" :value="ActiveStatus.INACTIVE" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="classroomDialog = false">取消</el-button>
        <el-button type="primary" @click="saveClassroom">保存</el-button>
      </template>
    </el-dialog>

    <!-- TeachingTask Dialog -->
    <el-dialog
      v-model="teachingTaskDialog"
      :title="teachingTaskForm.id ? '编辑教学任务' : '新增教学任务'"
      width="560px"
    >
      <el-form
        ref="teachingTaskFormRef"
        :model="teachingTaskForm"
        :rules="teachingTaskRules"
        label-width="100px"
      >
        <el-form-item label="课程" prop="courseId">
          <el-select
            v-model="teachingTaskForm.courseId"
            placeholder="请选择课程"
            style="width: 100%"
          >
            <el-option v-for="c in courses" :key="c.id" :label="c.name" :value="c.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="主讲教师" prop="primaryTeacherId">
          <el-select
            v-model="teachingTaskForm.primaryTeacherId"
            placeholder="请选择主讲教师"
            style="width: 100%"
          >
            <el-option v-for="t in teachers" :key="t.id" :label="t.name" :value="t.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="协作教师">
          <el-select
            v-model="teachingTaskForm.assistantTeacherId"
            clearable
            placeholder="可选"
            style="width: 100%"
          >
            <el-option v-for="t in teachers" :key="t.id" :label="t.name" :value="t.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="总课时" prop="totalHours">
          <el-input-number v-model="teachingTaskForm.totalHours" :min="2" :step="2" />
          <span style="color: #909399; font-size: 12px; margin-left: 8px">必须是2的倍数</span>
        </el-form-item>
        <el-form-item label="推荐教室">
          <el-select
            v-model="teachingTaskForm.classroomId"
            placeholder="可选，不选则由排课自动分配"
            clearable
            :value-on-clear="null"
            style="width: 100%"
          >
            <el-option
              v-for="cr in classrooms"
              :key="cr.id"
              :label="`${cr.name}(${cr.building}, ${cr.capacity}座, ${cr.classroomType})`"
              :value="cr.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="班级" prop="classGroupIds">
          <el-select
            v-model="teachingTaskForm.classGroupIds"
            multiple
            placeholder="至少选择1个班级"
            style="width: 100%"
          >
            <el-option v-for="cg in classGroups" :key="cg.id" :label="cg.name" :value="cg.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="teachingTaskForm.notes" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="teachingTaskForm.status">
            <el-option label="启用" :value="ActiveStatus.ACTIVE" />
            <el-option label="停用" :value="ActiveStatus.INACTIVE" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="teachingTaskDialog = false">取消</el-button>
        <el-button type="primary" @click="saveTeachingTask">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>
