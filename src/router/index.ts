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

import DashboardView from '@/modules/dashboard/views/DashboardView.vue'
import ProjectsView from '@/modules/projects/views/ProjectsView.vue'
import ProjectDetailsView from '@/modules/projects/views/ProjectDetailsView.vue'
import KanbanView from '@/modules/tasks/views/KanbanView.vue'
import UsersView from '@/modules/users/views/UsersView.vue'
import NotFoundView from '@/modules/system/views/NotFoundView.vue'

import type { UserRole } from '@/types/auth'

declare module 'vue-router' {
  interface RouteMeta {
    requiresAuth?: boolean
    roles?: UserRole[]
  }
}

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    redirect: '/app/dashboard',
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
      { path: 'dashboard', name: 'dashboard', component: DashboardView },
      { path: 'projects', name: 'projects', component: ProjectsView },
      { path: 'projects/:id', name: 'project', component: ProjectDetailsView },
      { path: 'projects/:id/board', name: 'kanban', component: KanbanView },
      { path: 'users', name: 'users', component: UsersView, meta: { roles: ['admin'] } },
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

    if (to.path === '/auth/login' && auth.isAuthenticated) return { name: 'dashboard' }

    if (to.meta.requiresAuth && !auth.isAuthenticated) {
      return { name: 'login' }
    }

    const roles = to.meta.roles
    if (roles?.length && auth.user && !roles.includes(auth.user.role)) {
      return { name: 'dashboard' }
    }

    return true
  })

  app.use(router)
  return router
}
