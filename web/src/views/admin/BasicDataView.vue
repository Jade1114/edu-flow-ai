<script setup lang="ts">
import { ref, onMounted, computed, watch } from 'vue'
import request from '@/api/request'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ActiveStatus } from '@/constants/status.js'
import ActiveStatusTag from '@/components/ActiveStatusTag.vue'
import ConfirmDeleteButton from '@/components/ConfirmDeleteButton.vue'
import TeacherPanel from '@/components/TeacherPanel.vue'
import { useRoute, useRouter } from 'vue-router'
import type { Teacher } from '@/types/teacher'

interface Course {
    id: number | null
    name: string
    code: string
    credits: number
    courseType: string
    requiredHours: number
    description?: string
    status: string
}

interface ClassGroup {
    id: number | null
    name: string
    major: string
    grade: string
    studentCount: number
    description?: string
}

interface Classroom {
    id: number | null
    name: string
    building: string
    capacity: number
    classroomType: string
    status: string
}

interface TeachingTask {
    id: number | null
    courseId: string
    primaryTeacherId: string
    assistantTeacherId?: string
    classroomId?: string
    totalHours: number
    notes?: string
    status: string
    classGroupIds: number[]
    classGroups?: { id: number; name: string }[]
}

const route = useRoute()
const router = useRouter()

const loadedTabs = ref(new Set())

const validTabs = ['teachingTask', 'teacher', 'course', 'classGroup', 'classroom']
const initialTab = validTabs.includes(route.query.tab as string)
    ? (route.query.tab as string)
    : 'teachingTask'
const activeTab = ref(initialTab)

watch(activeTab, (newTab) => {
    loadTabData(newTab)
    router.replace({
        query: {
            ...route.query,
            tab: newTab,
        },
    })
})

async function loadTabData(tab: string) {
    if (tab === 'teachingTask') {
        // Teaching task form needs courses, teachers, classGroups, classrooms (all for dropdowns)
        await Promise.all([
            !loadedTabs.value.has('course') && loadCourses(true),
            !loadedTabs.value.has('teacher') && loadTeachers(true),
            !loadedTabs.value.has('classGroup') && loadClassGroups(true),
            !loadedTabs.value.has('classroom') && loadClassrooms(),
            loadTeachingTasks(),
        ])
        loadedTabs.value.add('teachingTask')
        loadedTabs.value.add('course')
        loadedTabs.value.add('teacher')
        loadedTabs.value.add('classGroup')
        loadedTabs.value.add('classroom')
        return
    }
    if (loadedTabs.value.has(tab)) return
    if (tab === 'teacher') await loadTeachers()
    if (tab === 'course') await loadCourses()
    if (tab === 'classGroup') await loadClassGroups()
    if (tab === 'classroom') await loadClassrooms()
    loadedTabs.value.add(tab)
}

// Loading states
const loadingTeachingTasks = ref(false)
const loadingCourses = ref(false)
const loadingClassGroups = ref(false)

// Pagination
// Pagination (SQL pagination via API)
const teachingTaskPage = ref(1)
const teachingTaskPageSize = ref(20)
const teachingTaskTotal = ref(0)
const coursePage = ref(1)
const coursePageSize = ref(20)
const courseTotal = ref(0)
const classGroupPage = ref(1)
const classGroupPageSize = ref(20)
const classGroupTotal = ref(0)

// For SQL pagination, data from API is already paginated
const paginatedTeachingTasks = computed(() => teachingTasks.value)
const paginatedCourses = computed(() => courses.value)
const paginatedClassGroups = computed(() => classGroups.value)
// TeachingTask
const teachingTasks = ref<TeachingTask[]>([])
const teachingTaskDialog = ref(false)
const teachingTaskFormRef = ref()
const teachingTaskForm = ref({
    id: null,
    courseId: '',
    primaryTeacherId: '',
    assistantTeacherId: '',
    classroomId: '',
    totalHours: 32,
    theoryHours: 32,
    labHours: 0,
    courseType: '理论课',
    requiredRoomType: '',
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

const courseTypeOptions = [
    { value: '理论课', label: '理论课', room: '普通教室' },
    { value: '上机实践', label: '上机实践', room: '机房' },
    { value: '理论+上机', label: '理论+上机', room: '普通教室/机房' },
    { value: '体育', label: '体育', room: '操场' },
]

function onCourseChanged(courseId: any) {
    const course = courses.value.find((c: any) => c.id === courseId)
    if (course && course.courseType) {
        teachingTaskForm.value.courseType = course.courseType
        const opt = courseTypeOptions.find(o => o.value === course.courseType)
        if (opt) teachingTaskForm.value.requiredRoomType = opt.room
        if (course.courseType === '理论+上机') {
            teachingTaskForm.value.theoryHours = Math.round(course.requiredHours * 0.6 / 2) * 2
            teachingTaskForm.value.labHours = course.requiredHours - teachingTaskForm.value.theoryHours
        } else {
            teachingTaskForm.value.totalHours = course.requiredHours || 32
        }
    }
}

function onCourseTypeChanged(type: string) {
    teachingTaskForm.value.courseType = type
    const opt = courseTypeOptions.find(o => o.value === type)
    if (opt) teachingTaskForm.value.requiredRoomType = opt.room
}

async function loadTeachingTasks() {
    loadingTeachingTasks.value = true
    try {
        const res = await request.get('/api/teaching-tasks', {
            params: { page: teachingTaskPage.value - 1, size: teachingTaskPageSize.value }
        })
        teachingTasks.value = res.content || []
        teachingTaskTotal.value = res.total || 0
    } finally {
        loadingTeachingTasks.value = false
    }
}
function openTeachingTaskDialog(row: any) {
    if (row) {
        const course = courses.value.find((c: any) => c.id === row.courseId)
        const ct = course?.courseType || '理论课'
        teachingTaskForm.value = {
            id: row.id,
            courseId: row.courseId || '',
            primaryTeacherId: row.primaryTeacherId || '',
            assistantTeacherId: row.assistantTeacherId || '',
            classroomId: row.classroomId || '',
            totalHours: row.totalHours || 32,
            theoryHours: row.totalHours || 32,
            labHours: 0,
            courseType: ct,
            requiredRoomType: row.requiredRoomType || '',
            notes: row.notes || '',
            status: row.status || 'ACTIVE',
            classGroupIds: row.classGroups ? row.classGroups.map((cg: any) => cg.id) : [],
        }
    } else {
        teachingTaskForm.value = {
            id: null,
            courseId: '',
            primaryTeacherId: '',
            assistantTeacherId: '',
            classroomId: '',
            totalHours: 32,
            theoryHours: 32,
            labHours: 0,
            courseType: '理论课',
            requiredRoomType: '',
            notes: '',
            status: ActiveStatus.ACTIVE,
            classGroupIds: [],
        }
    }
    teachingTaskDialog.value = true
}
function optionalId(value: any) {
    return value === '' || value === undefined ? null : value
}

async function saveTeachingTask() {
    const valid = await teachingTaskFormRef.value?.validate().catch(() => false)
    if (!valid) return
    
    const form = teachingTaskForm.value
    const base = {
        courseId: form.courseId,
        primaryTeacherId: form.primaryTeacherId,
        assistantTeacherId: optionalId(form.assistantTeacherId),
        classroomId: optionalId(form.classroomId),
        status: form.status,
        classGroupIds: form.classGroupIds,
        notes: form.notes,
    }
    
    if (form.id) {
        // Edit: save as-is
        const payload = { ...form, classroomId: optionalId(form.classroomId), assistantTeacherId: optionalId(form.assistantTeacherId) }
        await request.put(`/api/teaching-tasks/${form.id}`, payload)
        ElMessage.success('保存成功')
    } else if (form.courseType === '理论+上机') {
        // Split: create 2 linked tasks
        const pairId = Date.now().toString(36)
        await request.post('/api/teaching-tasks', {
            ...base,
            totalHours: form.theoryHours,
            requiredRoomType: '普通教室',
            notes: `pair:${pairId} | 理论${form.theoryHours}+上机${form.labHours} | ${form.notes}`,
        })
        await request.post('/api/teaching-tasks', {
            ...base,
            totalHours: form.labHours,
            requiredRoomType: '机房',
            notes: `pair:${pairId} | 理论${form.theoryHours}+上机${form.labHours} | ${form.notes}`,
        })
        ElMessage.success(`已创建 2 条任务（理论${form.theoryHours}+上机${form.labHours}）`)
    } else {
        // Single: theory / lab / sports
        const roomMap: Record<string, string> = { '理论课': '普通教室', '上机实践': '机房', '体育': '操场' }
        await request.post('/api/teaching-tasks', {
            ...base,
            totalHours: form.totalHours,
            requiredRoomType: roomMap[form.courseType] || '',
            notes: `${form.courseType} | ${form.notes}`,
        })
        ElMessage.success('保存成功')
    }
    
    teachingTaskDialog.value = false
    loadTeachingTasks()
}
async function deleteTeachingTask(id: any) {
    await ElMessageBox.confirm('确认删除该教学任务？', '提示', {
        type: 'warning',
    })
    await request.delete(`/api/teaching-tasks/${id}`)
    ElMessage.success('删除成功')
    loadTeachingTasks()
}

// Teacher
const teachers = ref<Teacher[]>([])
const teacherDialog = ref(false)
const teacherFormRef = ref()
const teacherSearch = ref((route.query.teacherSearch as string) || '')
const teacherPage = ref(Number(route.query.teacherPage) || 1)
const teacherPageSize = ref(Number(route.query.teacherPageSize) || 10)
const loadingTeachers = ref(false)
const deletingTeacherId = ref(null)
const savingTeacher = ref(false)
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
    maxWeeklyHours: [
        { required: true, message: '请输入最大周课时', trigger: 'blur' },
        {
            type: 'number',
            min: 1,
            max: 40,
            message: '最大周课时必须在 1 到 40 之间',
            trigger: 'change',
        },
    ],
}

const filteredTeachers = computed(() => {
    const keyword = teacherSearch.value.trim().toLowerCase()
    if (!keyword) return teachers.value
    return teachers.value.filter(
        (teacher) =>
            teacher.employeeNo.toLowerCase().includes(keyword) ||
            teacher.name.toLowerCase().includes(keyword) ||
            (teacher.department?.toLowerCase().includes(keyword) ?? false),
    )
})

const pagedTeachers = computed(() => {
    const start = (teacherPage.value - 1) * teacherPageSize.value
    const end = start + teacherPageSize.value
    return filteredTeachers.value.slice(start, end)
})

watch(teacherSearch, () => {
    teacherPage.value = 1
})

watch(teacherPageSize, () => {
    teacherPage.value = 1
})

watch([teacherSearch, teacherPage, teacherPageSize], () => {
    syncTeacherQuery()
})

function syncTeacherQuery() {
    router.replace({
        query: {
            ...route.query,
            tab: 'teacher',
            teacherSearch: teacherSearch.value || undefined,
            teacherPage: teacherPage.value,
            teacherPageSize: teacherPageSize.value,
        },
    })
}

async function loadTeachers(all = false) {
    loadingTeachers.value = true
    try {
        const params: any = all ? { page: -1 } : { page: 0, size: 50 }
        const res = await request.get('/api/teachers', { params })
        teachers.value = res.content || (Array.isArray(res) ? res : [])
    } finally {
        loadingTeachers.value = false
    }
}
function openTeacherDialog(row: any) {
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
    savingTeacher.value = true

    try {
        if (teacherForm.value.id) {
            await request.put(`/api/teachers/${teacherForm.value.id}`, teacherForm.value)
        } else {
            await request.post('/api/teachers', teacherForm.value)
        }
        ElMessage.success('保存成功')
        teacherDialog.value = false
        await loadTeachers()
    } finally {
        savingTeacher.value = false
    }
}
async function deleteTeacher(id: any) {
    await ElMessageBox.confirm('确认删除该教师？', '提示', { type: 'warning' })
    deletingTeacherId.value = id
    try {
        await request.delete(`/api/teachers/${id}`)
        ElMessage.success('删除成功')
        await loadTeachers()
    } finally {
        deletingTeacherId.value = null
    }
}

// Course
const courses = ref<Course[]>([])
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

async function loadCourses(all = false) {
    loadingCourses.value = true
    try {
        const params: any = all ? { page: -1 } : { page: coursePage.value - 1, size: coursePageSize.value }
        const res = await request.get('/api/courses', { params })
        courses.value = res.content || (Array.isArray(res) ? res : [])
        if (!all && res.total != null) courseTotal.value = res.total
    } finally {
        loadingCourses.value = false
    }
}
function openCourseDialog(row: any) {
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
async function deleteCourse(id: any) {
    await ElMessageBox.confirm('确认删除该课程？', '提示', { type: 'warning' })
    await request.delete(`/api/courses/${id}`)
    ElMessage.success('删除成功')
    loadCourses()
}

// ClassGroup
const classGroups = ref<ClassGroup[]>([])
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

async function loadClassGroups(all = false) {
    loadingClassGroups.value = true
    try {
        const params: any = all ? { page: -1 } : { page: classGroupPage.value - 1, size: classGroupPageSize.value }
        const res = await request.get('/api/class-groups', { params })
        classGroups.value = res.content || (Array.isArray(res) ? res : [])
        if (!all && res.total != null) classGroupTotal.value = res.total
    } finally {
        loadingClassGroups.value = false
    }
}
function openClassGroupDialog(row: any) {
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
async function deleteClassGroup(id: any) {
    await ElMessageBox.confirm('确认删除该班级？', '提示', { type: 'warning' })
    await request.delete(`/api/class-groups/${id}`)
    ElMessage.success('删除成功')
    loadClassGroups()
}

// Classroom
const classroomPage = ref(1)
const classroomPageSize = ref(10)

const savingClassroom = ref(false)
const loadingClassrooms = ref(false)
const deletingClassroomId = ref(null)
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
const pagedClassrooms = computed(() => {
    const start = (classroomPage.value - 1) * classroomPageSize.value
    const end = start + classroomPageSize.value
    return filteredClassrooms.value.slice(start, end)
})
const classrooms = ref<Classroom[]>([])
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
    capacity: [
        { required: true, message: '请输入教室容量', trigger: 'blur' },
        {
            type: 'number',
            min: 1,
            max: 300,
            message: '教室容量需在 1 到 300 之间',
            trigger: 'change',
        },
    ],
}

watch(classroomSearch, () => {
    classroomPage.value = 1
})
watch(classroomPageSize, () => {
    classroomPage.value = 1
})

async function loadClassrooms() {
    loadingClassrooms.value = true
    try {
        classrooms.value = await request.get<Classroom[]>('/api/classrooms')
    } finally {
        loadingClassrooms.value = false
    }
}
function openClassroomDialog(row: any) {
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
    savingClassroom.value = true

    try {
        if (classroomForm.value.id) {
            await request.put(`/api/classrooms/${classroomForm.value.id}`, classroomForm.value)
        } else {
            await request.post('/api/classrooms', classroomForm.value)
        }
        ElMessage.success('保存成功')
        classroomDialog.value = false
        await loadClassrooms()
    } finally {
        savingClassroom.value = false
    }
}
async function deleteClassroom(id: any) {
    await ElMessageBox.confirm('确认删除该教室？', '提示', { type: 'warning' })
    deletingClassroomId.value = id

    try {
        await request.delete(`/api/classrooms/${id}`)
        ElMessage.success('删除成功')
        await loadClassrooms()
    } finally {
        deletingClassroomId.value = null
    }
}

watch(
    () => route.query,
    () => {
        const nextSearch = (route.query.teacherSearch as string) || ''
        const nextPage = Number(route.query.teacherPage) || 1
        const nextPageSize = Number(route.query.teacherPageSize) || 10

        if (teacherSearch.value !== nextSearch) {
            teacherSearch.value = nextSearch
        }

        if (teacherPage.value !== nextPage) {
            teacherPage.value = nextPage
        }

        if (teacherPageSize.value !== nextPageSize) {
            teacherPageSize.value = nextPageSize
        }
    },
)

onMounted(() => {
    loadTabData(activeTab.value)
})
</script>

<template>
    <div>
        <h2>基础数据管理</h2>
        <el-tabs v-model="activeTab" style="margin-top: 16px">
            <!-- TeachingTask -->
            <el-tab-pane label="教学任务" name="teachingTask">
                <div style="margin-bottom: 12px">
                    <el-button type="primary" @click="openTeachingTaskDialog(undefined)"
                        >新增教学任务
                    </el-button>
                </div>
                <el-table :data="paginatedTeachingTasks" v-loading="loadingTeachingTasks" border size="small">
                    <el-table-column prop="id" label="ID" width="60" />
                    <el-table-column prop="course.name" label="课程" show-overflow-tooltip />
                    <el-table-column prop="primaryTeacher.name" label="主讲教师" show-overflow-tooltip />
                    <el-table-column prop="assistantTeacher.name" label="协作教师" show-overflow-tooltip />
                    <el-table-column label="类型" width="100">
                        <template #default="{ row }">
                            <el-tag v-if="row.requiredRoomType === '机房'" type="success" size="small">上机</el-tag>
                            <el-tag v-else-if="row.requiredRoomType === '普通教室'" type="primary" size="small">理论</el-tag>
                            <el-tag v-else-if="row.requiredRoomType === '操场'" type="warning" size="small">体育</el-tag>
                            <el-tag v-else-if="row.notes?.includes('理论+上机')" type="warning" size="small">混合</el-tag>
                            <span v-else style="color: #909399; font-size: 12px">-</span>
                        </template>
                    </el-table-column>
                    <el-table-column prop="totalHours" label="总课时" width="80" />
                    <el-table-column label="教室" show-overflow-tooltip width="130">
                        <template #default="{ row }">
                            {{
                                row.classroom
                                    ? `${row.classroom.name}(${row.classroom.capacity}座)`
                                    : '-'
                            }}
                        </template>
                    </el-table-column>
                    <el-table-column label="班级" show-overflow-tooltip>
                        <template #default="{ row }">
                            {{ row.classGroups?.map((cg: any) => cg.name).join(', ') || '-' }}
                        </template>
                    </el-table-column>
                    <el-table-column label="状态" width="80">
                        <template #default="{ row }">
                            <ActiveStatusTag :status="row.status" />
                        </template>
                    </el-table-column>
                    <el-table-column label="操作" width="140">
                        <template #default="{ row }">
                            <el-button type="primary" size="small" @click="openTeachingTaskDialog(row)">编辑</el-button>
                            <el-button type="danger" size="small" @click="deleteTeachingTask(row.id)">删除</el-button>
                        </template>
                    </el-table-column>
                </el-table>
                <el-pagination
                    v-if="teachingTaskTotal > teachingTaskPageSize"
                    v-model:current-page="teachingTaskPage"
                    v-model:page-size="teachingTaskPageSize"
                    :total="teachingTaskTotal"
                    :page-sizes="[10, 20, 50, 100]"
                    layout="total, sizes, prev, pager, next"
                    style="margin-top: 12px; justify-content: flex-end"
                    @current-change="loadTeachingTasks"
                    @size-change="() => { teachingTaskPage = 1; loadTeachingTasks() }"
                />
            </el-tab-pane>

            <KeepAlive>
                <TeacherPanel v-if="activeTab === 'teacher'" />
            </KeepAlive>

            <!-- Course -->
            <el-tab-pane label="课程管理" name="course">
                <div style="margin-bottom: 12px">
                    <el-button type="primary" @click="openCourseDialog(undefined)"
                        >新增课程</el-button
                    >
                </div>
                <el-table :data="paginatedCourses" v-loading="loadingCourses" border size="small">
                    <el-table-column prop="name" label="课程名称" show-overflow-tooltip />
                    <el-table-column prop="code" label="课程代码" width="100" />
                    <el-table-column prop="credits" label="学分" width="70" />
                    <el-table-column prop="courseType" label="课程类型" width="120" />
                    <el-table-column prop="requiredHours" label="学时" width="70" />
                    <el-table-column prop="description" label="描述" show-overflow-tooltip />
                    <el-table-column label="状态" width="80">
                        <template #default="{ row }">
                            <ActiveStatusTag :status="row.status" />
                        </template>
                    </el-table-column>
                    <el-table-column label="操作" width="140">
                        <template #default="{ row }">
                            <el-button type="primary" size="small" @click="openCourseDialog(row)">编辑</el-button>
                            <el-button type="danger" size="small" @click="deleteCourse(row.id)">删除</el-button>
                        </template>
                    </el-table-column>
                </el-table>
                <el-pagination
                    v-if="courseTotal > coursePageSize"
                    v-model:current-page="coursePage"
                    v-model:page-size="coursePageSize"
                    :total="courseTotal"
                    :page-sizes="[10, 20, 50, 100]"
                    layout="total, sizes, prev, pager, next"
                    style="margin-top: 12px; justify-content: flex-end"
                    @current-change="loadCourses"
                    @size-change="() => { coursePage = 1; loadCourses() }"
                />
            </el-tab-pane>

            <!-- ClassGroup -->
            <el-tab-pane label="班级管理" name="classGroup">
                <div style="margin-bottom: 12px">
                    <el-button type="primary" @click="openClassGroupDialog(undefined)"
                        >新增班级</el-button
                    >
                </div>
                <el-table :data="paginatedClassGroups" v-loading="loadingClassGroups" border size="small">
                    <el-table-column prop="name" label="班级名称" show-overflow-tooltip />
                    <el-table-column prop="major" label="专业" show-overflow-tooltip />
                    <el-table-column prop="grade" label="年级" width="80" />
                    <el-table-column prop="studentCount" label="人数" width="80" />
                    <el-table-column label="操作" width="140">
                        <template #default="{ row }">
                            <el-button type="primary" size="small" @click="openClassGroupDialog(row)">编辑</el-button>
                            <el-button type="danger" size="small" @click="deleteClassGroup(row.id)">删除</el-button>
                        </template>
                    </el-table-column>
                </el-table>
                <el-pagination
                    v-if="classGroupTotal > classGroupPageSize"
                    v-model:current-page="classGroupPage"
                    v-model:page-size="classGroupPageSize"
                    :total="classGroupTotal"
                    :page-sizes="[10, 20, 50, 100]"
                    layout="total, sizes, prev, pager, next"
                    style="margin-top: 12px; justify-content: flex-end"
                    @current-change="loadClassGroups"
                    @size-change="() => { classGroupPage = 1; loadClassGroups() }"
                />
            </el-tab-pane>

            <!-- Classroom -->
            <el-tab-pane label="教室管理" name="classroom">
                <div style="margin-bottom: 12px">
                    <el-button type="primary" @click="openClassroomDialog(undefined)"
                        >新增教室</el-button
                    >
                    <el-input
                        v-model="classroomSearch"
                        placeholder="搜索教室名称,类型或者教学楼"
                        clearable
                        style="width: 240px; margin-left: 12px"
                    />
                </div>
                <el-table :data="pagedClassrooms" v-loading="loadingClassrooms" border size="small">
                    <template #empty>
                        <el-empty description="暂无教室数据" />
                    </template>
                    <el-table-column prop="name" label="教室名称" />
                    <el-table-column prop="building" label="教学楼" />
                    <el-table-column prop="capacity" label="容量" width="80" />
                    <el-table-column prop="classroomType" label="类型" width="120" />
                    <el-table-column prop="status" label="状态" width="80">
                        <template #default="{ row }">
                            <ActiveStatusTag :status="row.status" />
                        </template>
                    </el-table-column>
                    <el-table-column label="操作" width="140">
                        <template #default="{ row }">
                            <el-button
                                type="primary"
                                size="small"
                                :disabled="deletingClassroomId === row.id"
                                @click="openClassroomDialog(row)"
                                >编辑</el-button
                            >
                            <ConfirmDeleteButton
                                :loading="deletingClassroomId === row.id"
                                :disabled="deletingClassroomId === row.id"
                                @confirm="deleteClassroom(row.id)"
                                >删除教室</ConfirmDeleteButton
                            >
                        </template>
                    </el-table-column>
                </el-table>
                <el-pagination
                    v-model:current-page="classroomPage"
                    v-model:page-size="classroomPageSize"
                    :total="filteredClassrooms.length"
                    :page-sizes="[5, 10, 20, 50]"
                    layout="total, sizes, prev, pager, next"
                    style="margin-top: 12px; justify-content: flex-end"
                />
            </el-tab-pane>
        </el-tabs>

        <!-- Teacher Dialog -->
        <el-dialog
            v-model="teacherDialog"
            :title="teacherForm.id ? '编辑教师' : '新增教师'"
            width="480px"
        >
            <el-form
                ref="teacherFormRef"
                :model="teacherForm"
                :rules="teacherRules"
                label-width="100px"
            >
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
                <el-form-item label="最大周课时" prop="maxWeeklyHours">
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
                <el-button type="primary" :loading="savingTeacher" @click="saveTeacher"
                    >保存</el-button
                >
            </template>
        </el-dialog>

        <!-- Course Dialog -->
        <el-dialog
            v-model="courseDialog"
            :title="courseForm.id ? '编辑课程' : '新增课程'"
            width="480px"
        >
            <el-form
                ref="courseFormRef"
                :model="courseForm"
                :rules="courseRules"
                label-width="100px"
            >
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
                <el-form-item label="容量" prop="capacity">
                    <el-input-number v-model="classroomForm.capacity" :min="1" :max="300" />
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
                <el-button type="primary" :loading="savingClassroom" @click="saveClassroom"
                    >保存</el-button
                >
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
                        @change="onCourseChanged"
                    >
                        <el-option v-for="c in courses" :key="c.id" :label="`${c.name} (${c.code || ''})`" :value="c.id" />
                    </el-select>
                </el-form-item>
                <el-form-item label="课程类型">
                    <el-select
                        v-model="teachingTaskForm.courseType"
                        @change="onCourseTypeChanged"
                        style="width: 100%"
                    >
                        <el-option v-for="opt in courseTypeOptions" :key="opt.value" :label="opt.label" :value="opt.value" />
                    </el-select>
                </el-form-item>
                <el-form-item label="所需教室">
                    <el-input :model-value="teachingTaskForm.requiredRoomType" disabled style="width: 100%" />
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
                        clearable placeholder="可选"
                        style="width: 100%"
                    >
                        <el-option v-for="t in teachers" :key="t.id" :label="t.name" :value="t.id" />
                    </el-select>
                </el-form-item>

                <!-- 理论+上机 拆分开关 -->
                <template v-if="teachingTaskForm.courseType === '理论+上机'">
                    <el-divider content-position="left" style="margin: 12px 0">
                        <el-tag type="warning" size="small">理论+上机 → 拆分为 2 条任务</el-tag>
                    </el-divider>
                    <el-form-item label="📖 理论学时" prop="theoryHours">
                        <el-input-number v-model="teachingTaskForm.theoryHours" :min="2" :step="2" />
                        <span style="color: #909399; font-size: 12px; margin-left: 8px">教室类型：普通教室</span>
                    </el-form-item>
                    <el-form-item label="💻 上机学时" prop="labHours">
                        <el-input-number v-model="teachingTaskForm.labHours" :min="0" :step="2" />
                        <span style="color: #909399; font-size: 12px; margin-left: 8px">教室类型：机房</span>
                    </el-form-item>
                    <el-form-item label="总学时">
                        <span style="font-weight: 600">{{ teachingTaskForm.theoryHours + teachingTaskForm.labHours }}</span>
                        <span style="color: #909399; font-size: 12px; margin-left: 8px">（理论{{ teachingTaskForm.theoryHours }} + 上机{{ teachingTaskForm.labHours }}）</span>
                    </el-form-item>
                </template>
                <template v-else>
                    <el-form-item label="总课时" prop="totalHours">
                        <el-input-number v-model="teachingTaskForm.totalHours" :min="2" :step="2" />
                        <span style="color: #909399; font-size: 12px; margin-left: 8px">必须是2的倍数</span>
                    </el-form-item>
                </template>

                <el-form-item label="推荐教室">
                    <el-select
                        v-model="teachingTaskForm.classroomId"
                        placeholder="可选，不选则由排课自动分配"
                        clearable :value-on-clear="null"
                        style="width: 100%"
                    >
                        <el-option v-for="cr in classrooms" :key="cr.id"
                            :label="`${cr.name}(${cr.building || '?'}, ${cr.capacity}座)`"
                            :value="cr.id" />
                    </el-select>
                </el-form-item>
                <el-form-item label="班级" prop="classGroupIds">
                    <el-select
                        v-model="teachingTaskForm.classGroupIds"
                        multiple placeholder="至少选择1个班级"
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
