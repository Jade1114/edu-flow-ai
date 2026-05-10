<script setup>
import { ref, onMounted } from 'vue'
import request from '@/api/request.js'
import { ElMessage, ElMessageBox } from 'element-plus'

const activeTab = ref('teacher')

// Teacher
const teachers = ref([])
const teacherDialog = ref(false)
const teacherFormRef = ref()
const teacherForm = ref({ id: null, employeeNo: '', name: '', department: '', title: '', maxWeeklyHours: 8, status: 'ACTIVE', password: '123456', role: 'TEACHER' })
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
    teacherForm.value = { id: null, employeeNo: '', name: '', department: '', title: '', maxWeeklyHours: 8, status: 'ACTIVE', password: '123456', role: 'TEACHER' }
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
const courseForm = ref({ id: null, name: '', courseType: '', requiredHours: 32, requiredSkill: '', description: '', status: 'ACTIVE' })
const courseRules = { name: [{ required: true, message: '请输入课程名称', trigger: 'blur' }] }

async function loadCourses() {
  courses.value = await request.get('/api/courses')
}
function openCourseDialog(row) {
  courseForm.value = row ? { ...row } : { id: null, name: '', courseType: '', requiredHours: 32, requiredSkill: '', description: '', status: 'ACTIVE' }
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
const classGroupForm = ref({ id: null, name: '', major: '', grade: '', studentCount: 0, description: '' })
const classGroupRules = { name: [{ required: true, message: '请输入班级名称', trigger: 'blur' }] }

async function loadClassGroups() {
  classGroups.value = await request.get('/api/class-groups')
}
function openClassGroupDialog(row) {
  classGroupForm.value = row ? { ...row } : { id: null, name: '', major: '', grade: '', studentCount: 0, description: '' }
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
const classrooms = ref([])
const classroomDialog = ref(false)
const classroomFormRef = ref()
const classroomForm = ref({ id: null, name: '', building: '', capacity: 60, classroomType: '普通教室', status: 'ACTIVE' })
const classroomRules = { name: [{ required: true, message: '请输入教室名称', trigger: 'blur' }] }

async function loadClassrooms() {
  classrooms.value = await request.get('/api/classrooms')
}
function openClassroomDialog(row) {
  classroomForm.value = row ? { ...row } : { id: null, name: '', building: '', capacity: 60, classroomType: '普通教室', status: 'ACTIVE' }
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
})
</script>

<template>
  <div>
    <h2>基础数据管理</h2>
    <el-tabs v-model="activeTab" style="margin-top: 16px">
      <!-- Teacher -->
      <el-tab-pane label="教师管理" name="teacher">
        <div style="margin-bottom: 12px">
          <el-button type="primary" @click="openTeacherDialog()">新增教师</el-button>
        </div>
        <el-table :data="teachers" border size="small">
          <el-table-column prop="employeeNo" label="工号" width="100" />
          <el-table-column prop="name" label="姓名" width="100" />
          <el-table-column prop="department" label="部门" />
          <el-table-column prop="title" label="职称" width="100" />
          <el-table-column prop="maxWeeklyHours" label="最大周课时" width="100" />
          <el-table-column prop="role" label="角色" width="100" />
          <el-table-column prop="status" label="状态" width="80" />
          <el-table-column label="操作" width="140">
            <template #default="{ row }">
              <el-button type="primary" size="small" @click="openTeacherDialog(row)">编辑</el-button>
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
          <el-table-column prop="requiredSkill" label="技能要求" show-overflow-tooltip />
          <el-table-column prop="status" label="状态" width="80" />
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
              <el-button type="primary" size="small" @click="openClassGroupDialog(row)">编辑</el-button>
              <el-button type="danger" size="small" @click="deleteClassGroup(row.id)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <!-- Classroom -->
      <el-tab-pane label="教室管理" name="classroom">
        <div style="margin-bottom: 12px">
          <el-button type="primary" @click="openClassroomDialog()">新增教室</el-button>
        </div>
        <el-table :data="classrooms" border size="small">
          <el-table-column prop="name" label="教室名称" />
          <el-table-column prop="building" label="教学楼" />
          <el-table-column prop="capacity" label="容量" width="80" />
          <el-table-column prop="classroomType" label="类型" width="120" />
          <el-table-column prop="status" label="状态" width="80" />
          <el-table-column label="操作" width="140">
            <template #default="{ row }">
              <el-button type="primary" size="small" @click="openClassroomDialog(row)">编辑</el-button>
              <el-button type="danger" size="small" @click="deleteClassroom(row.id)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>
    </el-tabs>

    <!-- Teacher Dialog -->
    <el-dialog v-model="teacherDialog" :title="teacherForm.id ? '编辑教师' : '新增教师'" width="480px">
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
            <el-option label="启用" value="ACTIVE" />
            <el-option label="停用" value="INACTIVE" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="teacherDialog = false">取消</el-button>
        <el-button type="primary" @click="saveTeacher">保存</el-button>
      </template>
    </el-dialog>

    <!-- Course Dialog -->
    <el-dialog v-model="courseDialog" :title="courseForm.id ? '编辑课程' : '新增课程'" width="480px">
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
        <el-form-item label="技能要求">
          <el-input v-model="courseForm.requiredSkill" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="courseForm.description" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="courseForm.status">
            <el-option label="启用" value="ACTIVE" />
            <el-option label="停用" value="INACTIVE" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="courseDialog = false">取消</el-button>
        <el-button type="primary" @click="saveCourse">保存</el-button>
      </template>
    </el-dialog>

    <!-- ClassGroup Dialog -->
    <el-dialog v-model="classGroupDialog" :title="classGroupForm.id ? '编辑班级' : '新增班级'" width="480px">
      <el-form ref="classGroupFormRef" :model="classGroupForm" :rules="classGroupRules" label-width="100px">
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
    <el-dialog v-model="classroomDialog" :title="classroomForm.id ? '编辑教室' : '新增教室'" width="480px">
      <el-form ref="classroomFormRef" :model="classroomForm" :rules="classroomRules" label-width="100px">
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
            <el-option label="启用" value="ACTIVE" />
            <el-option label="停用" value="INACTIVE" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="classroomDialog = false">取消</el-button>
        <el-button type="primary" @click="saveClassroom">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>
