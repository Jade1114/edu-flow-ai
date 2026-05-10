import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth.js'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/login',
      name: 'Login',
      component: () => import('@/views/common/LoginView.vue'),
      meta: { public: true },
    },
    {
      path: '/',
      redirect: () => {
        const store = useAuthStore()
        if (store.isAdmin) return '/admin'
        if (store.isTeacher) return '/teacher'
        return '/login'
      },
    },
    {
      path: '/admin',
      component: () => import('@/layouts/AdminLayout.vue'),
      meta: { role: 'ADMIN' },
      children: [
        { path: '', redirect: '/admin/dashboard' },
        { path: 'dashboard', name: 'AdminDashboard', component: () => import('@/views/admin/DashboardView.vue') },
        { path: 'basic-data', name: 'AdminBasicData', component: () => import('@/views/admin/BasicDataView.vue') },
        { path: 'allocation', name: 'AdminAllocation', component: () => import('@/views/admin/AllocationView.vue') },
        { path: 'timetable', name: 'AdminTimetable', component: () => import('@/views/admin/TimetableView.vue') },
        { path: 'adjustment', name: 'AdminAdjustment', component: () => import('@/views/admin/AdjustmentView.vue') },
      ],
    },
    {
      path: '/teacher',
      component: () => import('@/layouts/TeacherLayout.vue'),
      meta: { role: 'TEACHER' },
      children: [
        { path: '', redirect: '/teacher/timetable' },
        { path: 'timetable', name: 'TeacherTimetable', component: () => import('@/views/teacher/TimetableView.vue') },
        { path: 'profile', name: 'TeacherProfile', component: () => import('@/views/teacher/ProfileView.vue') },
        { path: 'adjustment', name: 'TeacherAdjustment', component: () => import('@/views/teacher/AdjustmentView.vue') },
      ],
    },
    {
      path: '/debug',
      name: 'Debug',
      component: () => import('@/views/common/DebugView.vue'),
      meta: { public: true },
    },
  ],
})

router.beforeEach((to, from, next) => {
  const store = useAuthStore()
  if (to.meta.public) {
    next()
    return
  }
  if (!store.isLoggedIn) {
    next('/login')
    return
  }
  if (to.meta.role && to.meta.role !== store.user?.role) {
    next(store.isAdmin ? '/admin' : '/teacher')
    return
  }
  next()
})

export default router
