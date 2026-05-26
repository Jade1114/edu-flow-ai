<script setup>
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth.js'
import { User, Lock } from '@element-plus/icons-vue'

const router = useRouter()
const auth = useAuthStore()
const loading = ref(false)

const form = reactive({
  employeeNo: '',
  password: '',
})

const rules = {
  employeeNo: [{ required: true, message: '请输入工号', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
}

const formRef = ref()

async function handleLogin() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return
  loading.value = true
  try {
    const data = await auth.login(form.employeeNo, form.password)
    if (data.role === 'ADMIN') {
      router.push('/admin')
    } else {
      router.push('/teacher')
    }
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="login-page">
    <el-card class="login-card" shadow="always">
      <template #header>
        <h2 class="login-title">Edu Flow AI</h2>
        <p class="login-subtitle">智能教务管理系统</p>
      </template>
      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        label-position="top"
        @keyup.enter="handleLogin"
      >
        <el-form-item label="工号" prop="employeeNo">
          <el-input v-model="form.employeeNo" :prefix-icon="User" placeholder="请输入工号" />
        </el-form-item>
        <el-form-item label="密码" prop="password">
          <el-input
            v-model="form.password"
            :prefix-icon="Lock"
            type="password"
            placeholder="请输入密码"
            show-password
          />
        </el-form-item>
        <el-button
          type="primary"
          size="large"
          style="width: 100%"
          :loading="loading"
          @click="handleLogin"
        >
          登录
        </el-button>
      </el-form>
      <div class="login-hint">
        <p>测试账号：</p>
        <p>教务管理员：ADMIN001 / 123456</p>
        <p>教师：T1001 / 123456</p>
      </div>
    </el-card>
  </div>
</template>

<style scoped>
.login-page {
  height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
}
.login-card {
  width: 420px;
}
.login-title {
  margin: 0;
  text-align: center;
  font-size: 24px;
  color: #303133;
}
.login-subtitle {
  margin: 8px 0 0;
  text-align: center;
  font-size: 14px;
  color: #909399;
}
.login-hint {
  margin-top: 20px;
  padding-top: 16px;
  border-top: 1px solid #ebeef5;
  font-size: 12px;
  color: #909399;
}
.login-hint p {
  margin: 4px 0;
}
</style>
