import type { App } from 'vue'
import {
  createRouter,
  createWebHistory,
  type RouteLocationNormalized,
  type RouteRecordRaw,
} from 'vue-router'

import { useAuthStore } from '@/modules/auth/store'

import AuthLayout from '@/layouts/AuthLayout.vue'
import DashboardLayout from '@/layouts/DashboardLayout.vue'

import LoginView from '@/modules/auth/views/LoginView.vue'

import ProjectsView from '@/modules/projects/views/ProjectsView.vue'
import ProjectDetailsView from '@/modules/projects/views/ProjectDetailsView.vue'
import NotFoundView from '@/modules/system/views/NotFoundView.vue'

declare module 'vue-router' {
  interface RouteMeta {
    requiresAuth?: boolean
  }
}

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    redirect: '/app/projects',
  },
  {
    path: '/auth',
    component: AuthLayout,
    children: [
      { path: 'login', name: 'login', component: LoginView },
      { path: 'register', redirect: { name: 'login' } },
    ],
  },
  {
    path: '/app',
    component: DashboardLayout,
    meta: { requiresAuth: true },
    children: [
      { path: '', redirect: { name: 'projects' } },
      { path: 'dashboard', redirect: { name: 'projects' } },
      { path: 'projects', name: 'projects', component: ProjectsView },
      { path: 'projects/:id', name: 'project', component: ProjectDetailsView },
      {
        path: 'projects/:id/board',
        redirect: (to) => ({ name: 'project', params: { id: to.params.id } }),
      },
      { path: 'users', redirect: { name: 'projects' } },
    ],
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'notFound',
    component: NotFoundView,
  },
]

export function installRouter(app: App) {
  const router = createRouter({
    history: createWebHistory(),
    routes,
  })

  router.beforeEach((to: RouteLocationNormalized) => {
    const auth = useAuthStore()

    if (to.path === '/auth/login' && auth.isAuthenticated) return { name: 'projects' }

    if (to.meta.requiresAuth && !auth.isAuthenticated) {
      return { name: 'login' }
    }

    return true
  })

  app.use(router)
  return router
}
