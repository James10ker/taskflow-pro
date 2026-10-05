<template>
  <div class="min-h-screen bg-slate-50 text-slate-900 dark:bg-slate-950 dark:text-slate-50">
    <div class="flex">
      <aside class="hidden h-screen w-72 flex-col border-r border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900 lg:flex">
        <div class="px-6 py-5">
          <div class="text-sm font-semibold tracking-tight">TaskFlow Pro</div>
          <div class="mt-1 text-xs text-slate-600 dark:text-slate-300">Project management workspace</div>
        </div>

        <nav class="flex-1 px-3">
          <RouterLink
            v-for="item in navItems"
            :key="item.to"
            :to="item.to"
            class="mb-1 flex items-center justify-between rounded-xl px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-100 hover:text-slate-900 dark:text-slate-200 dark:hover:bg-slate-800"
            active-class="bg-slate-100 text-slate-900 dark:bg-slate-800"
          >
            <span>{{ item.label }}</span>
          </RouterLink>
        </nav>

        <div class="border-t border-slate-200 px-6 py-4 dark:border-slate-800">
          <div class="text-xs text-slate-500 dark:text-slate-400">Signed in as</div>
          <div class="mt-1 text-sm font-medium">{{ auth.user?.name }}</div>
          <div class="mt-3 flex gap-2">
            <button
              type="button"
              class="flex-1 rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-medium text-slate-800 hover:bg-slate-50 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-100 dark:hover:bg-slate-800"
              @click="theme.toggle()"
            >
              {{ theme.mode === 'dark' ? 'Light' : 'Dark' }}
            </button>
            <button
              type="button"
              class="flex-1 rounded-lg bg-slate-900 px-3 py-2 text-xs font-semibold text-white hover:bg-slate-800 dark:bg-slate-100 dark:text-slate-900 dark:hover:bg-white"
              @click="onLogout"
            >
              Logout
            </button>
          </div>
        </div>
      </aside>

      <div class="flex min-h-screen flex-1 flex-col">
        <header class="border-b border-slate-200 bg-white px-4 py-4 dark:border-slate-800 dark:bg-slate-900 lg:px-8">
          <div class="flex items-center justify-between">
            <div>
              <div class="text-sm font-semibold">{{ pageTitle }}</div>
              <div class="text-xs text-slate-600 dark:text-slate-300">{{ pageSubtitle }}</div>
            </div>
            <RouterLink
              to="/app/projects"
              class="rounded-lg bg-slate-900 px-3 py-2 text-sm font-semibold text-white hover:bg-slate-800 dark:bg-slate-100 dark:text-slate-900 dark:hover:bg-white"
            >
              Projects
            </RouterLink>
          </div>
        </header>

        <main class="flex-1 px-4 py-6 lg:px-8">
          <RouterView />
        </main>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { useAuthStore } from '@/modules/auth/store'
import { useThemeStore } from '@/store/theme'

const auth = useAuthStore()
const theme = useThemeStore()
const router = useRouter()
const route = useRoute()

const navItems = computed(() => {
  return [{ to: '/app/projects', label: 'Projects' }]
})

const pageTitle = computed(() => {
  if (route.name === 'projects') return 'Projects'
  if (route.name === 'project') return 'Project overview'
  return 'Workspace'
})

const pageSubtitle = computed(() => {
  if (route.name === 'projects') return 'Create and manage projects through the real API.'
  if (route.name === 'project') return 'Project details and owner actions.'
  return ''
})

function onLogout() {
  auth.logout()
  router.push({ name: 'login' })
}
</script>
