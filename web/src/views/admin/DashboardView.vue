<script setup>
import { useAuthStore } from '@/stores/auth.js'
const auth = useAuthStore()
</script>

<template>
  <div>
    <h2>欢迎使用教务管理系统</h2>
    <el-card style="margin-top: 20px">
      <p>当前用户：{{ auth.displayName }}</p>
      <p>角色：{{ auth.isAdmin ? '教务管理员' : '教师' }}</p>
      <p style="margin-top: 16px; color: #909399">
        请从左侧菜单选择功能模块进行操作。
      </p>
    </el-card>
  </div>
</template>
