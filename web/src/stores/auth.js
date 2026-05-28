import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import request from '@/api/request.js'

export const useAuthStore = defineStore('auth', () => {
    const user = ref(JSON.parse(localStorage.getItem('edu-flow-user') || 'null'))
    const token = ref(localStorage.getItem('edu-flow-token') || '')

    const isLoggedIn = computed(() => !!token.value)
    const isAdmin = computed(() => user.value?.role === 'ADMIN')
    const isTeacher = computed(() => user.value?.role === 'TEACHER')
    const displayName = computed(() => user.value?.displayName || user.value?.name || '')

    async function login(employeeNo, password) {
        const data = await request.post('/api/auth/login', { employeeNo, password })
        user.value = data
        token.value = data.employeeNo || String(data.id)
        localStorage.setItem('edu-flow-user', JSON.stringify(data))
        localStorage.setItem('edu-flow-token', token.value)
        return data
    }

    function logout() {
        user.value = null
        token.value = ''
        localStorage.removeItem('edu-flow-user')
        localStorage.removeItem('edu-flow-token')
    }

    return { user, token, isLoggedIn, isAdmin, isTeacher, displayName, login, logout }
})
