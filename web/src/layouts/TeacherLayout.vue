<script setup>
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth.js'
import {
  Calendar,
  User,
  SwitchButton,
} from '@element-plus/icons-vue'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const menus = [
  { path: '/teacher/timetable', label: '我的课表', icon: Calendar },
  { path: '/teacher/profile', label: '个人信息', icon: User },
]

function handleLogout() {
  auth.logout()
  router.push('/login')
}
</script>

<template>
  <el-container class="teacher-layout">
    <el-aside width="200px" class="sidebar">
      <div class="logo">教师工作台</div>
      <el-menu
        :default-active="route.path"
        router
        class="sidebar-menu"
        background-color="#2d3a4b"
        text-color="#bfcbd9"
        active-text-color="#67C23A"
      >
        <el-menu-item v-for="menu in menus" :key="menu.path" :index="menu.path">
          <el-icon><component :is="menu.icon" /></el-icon>
          <span>{{ menu.label }}</span>
        </el-menu-item>
      </el-menu>
    </el-aside>
    <el-container>
      <el-header class="header">
        <span class="breadcrumb">教师端</span>
        <div class="header-right">
          <span class="username">{{ auth.displayName }}</span>
          <el-button type="danger" size="small" :icon="SwitchButton" @click="handleLogout">
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
.teacher-layout {
  height: 100vh;
}
.sidebar {
  background: #2d3a4b;
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
