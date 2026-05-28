<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import request from '@/api/request.js'
import ActiveStatusTag from '@/components/ActiveStatusTag.vue'
import type { Teacher } from '@/types/teacher'

const route = useRoute()
const router = useRouter()
const teacherId = computed(() => String(route.params.id))
const loading = ref(false)
const teacher = ref<Teacher | null>(null)

async function loadTeacher() {
    loading.value = true
    try {
        teacher.value = await request.get(`/api/teachers/${teacherId.value}`)
    } finally {
        loading.value = false
    }
}

function backToTeacherList() {
    const from = Array.isArray(route.query.from) ? route.query.from[0] : route.query.from
    if (from) {
        router.push(from)
        return
    }
    router.push({
        path: '/admin/basic-data',
        query: {
            tab: 'teacher',
        },
    })
}

watch(
    () => route.params.id,
    () => {
        loadTeacher()
    },
    { immediate: true },
)
</script>

<template>
    <div>
        <el-card v-loading="loading">
            <template #header>
                <div class="detail-header">
                    <span>教师详情</span>
                    <el-button size="small" @click="backToTeacherList">返回教师列表</el-button>
                </div>
            </template>

            <el-empty v-if="!loading && !teacher" description="暂无教师数据" />
            <el-descriptions v-else-if="teacher" :column="2" border>
                <el-descriptions-item label="ID">{{ teacher.id }}</el-descriptions-item>
                <el-descriptions-item label="工号">{{ teacher.employeeNo }}</el-descriptions-item>
                <el-descriptions-item label="姓名">{{ teacher.name }}</el-descriptions-item>
                <el-descriptions-item label="部门">{{
                    teacher.department || '-'
                }}</el-descriptions-item>
                <el-descriptions-item label="职称">{{ teacher.title || '-' }}</el-descriptions-item>
                <el-descriptions-item label="最大周课时">
                    {{ teacher.maxWeeklyHours }}
                </el-descriptions-item>
                <el-descriptions-item label="角色">
                    {{ teacher.role === 'ADMIN' ? '管理员' : '教师' }}
                </el-descriptions-item>
                <el-descriptions-item label="状态">
                    <ActiveStatusTag :status="teacher.status" />
                </el-descriptions-item>
            </el-descriptions>
        </el-card>
    </div>
</template>

<style scoped>
.detail-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
}
</style>
