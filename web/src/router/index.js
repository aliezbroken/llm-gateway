import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import AdminLayout from '../layouts/AdminLayout.vue'

const routes = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('../views/Login.vue'),
    meta: { public: true }
  },
  {
    path: '/',
    component: AdminLayout,
    redirect: '/dashboard',
    children: [
      { path: 'dashboard', name: 'Dashboard', component: () => import('../views/Dashboard.vue') },
      { path: 'logs', name: 'Logs', component: () => import('../views/Logs.vue') },
      { path: 'tokens', name: 'Tokens', component: () => import('../views/Tokens.vue') },
      { path: 'users', name: 'Users', component: () => import('../views/Users.vue'), meta: { roles: ['admin'] } },
      { path: 'settings', name: 'Settings', component: () => import('../views/Settings.vue'), meta: { roles: ['admin'] } }
    ]
  },
  { path: '/:pathMatch(.*)*', redirect: '/dashboard' }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

router.beforeEach((to) => {
  const auth = useAuthStore()
  if (!to.meta.public && !auth.token) {
    return { path: '/login' }
  }
  if (to.meta.roles && !to.meta.roles.includes(auth.user?.role)) {
    return { path: '/dashboard' }
  }
  if (to.path === '/login' && auth.token) {
    return { path: '/dashboard' }
  }
  return true
})

export default router
