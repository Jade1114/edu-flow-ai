<script setup>
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth.js'
import {
    DataLine,
    Collection,
    MagicStick,
    Calendar,
    Edit,
    SwitchButton,
    Cpu,
    Operation,
    UserFilled,
} from '@element-plus/icons-vue'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const menus = [
    { path: '/admin/dashboard', label: '首页', icon: DataLine },
    { path: '/admin/basic-data', label: '基础数据', icon: Collection },
    { path: '/admin/allocation', label: '分课任务', icon: MagicStick },
    { path: '/admin/model-training', label: '模型训练', icon: Cpu },
    { path: '/admin/teacher-profiles', label: '教师画像', icon: UserFilled },
    { path: '/admin/timetable', label: '课表查询', icon: Calendar },
    { path: '/admin/adjustment', label: '调课处理', icon: Edit },
    { path: '/admin/constraint-editor', label: '约束干预', icon: Operation },
]

function handleLogout() {
    auth.logout()
    router.push('/login')
}
</script>

<template>
    <el-container class="admin-layout">
        <el-aside width="200px" class="sidebar">
            <div class="logo">教务管理系统</div>
            <el-menu
                :default-active="route.path"
                router
                class="sidebar-menu"
                background-color="#304156"
                text-color="#bfcbd9"
                active-text-color="#409EFF"
            >
                <el-menu-item v-for="menu in menus" :key="menu.path" :index="menu.path">
                    <el-icon><component :is="menu.icon" /></el-icon>
                    <span>{{ menu.label }}</span>
                </el-menu-item>
            </el-menu>
        </el-aside>
        <el-container>
            <el-header class="header">
                <span class="breadcrumb">教务管理员端</span>
                <div class="header-right">
                    <span class="username">{{ auth.displayName }}</span>
                    <el-tag type="success" size="small">
                        {{ auth.user?.role === 'ADMIN' ? '管理员' : '教师' }}
                    </el-tag>
                    <el-button
                        type="danger"
                        size="small"
                        :icon="SwitchButton"
                        @click="handleLogout"
                    >
                        退出
                    </el-button>
                </div>
            </el-header>
            <el-main class="main">
                <router-view />
            </el-main>
        </el-container>
    </el-container>
</template>

<style scoped>
.admin-layout {
    height: 100vh;
}
.sidebar {
    background: #304156;
}
.logo {
    height: 60px;
    line-height: 60px;
    text-align: center;
    color: #fff;
    font-size: 18px;
    font-weight: bold;
    border-bottom: 1px solid #1f2d3d;
}
.sidebar-menu {
    border-right: none;
}
.header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    background: #fff;
    box-shadow: 0 1px 4px rgba(0, 0, 0, 0.08);
}
.breadcrumb {
    font-size: 16px;
    font-weight: 500;
}
.header-right {
    display: flex;
    align-items: center;
    gap: 16px;
}
.username {
    color: #606266;
}
.main {
    background: #f5f7fa;
    padding: 20px;
}
</style>
