<template>
  <div class="min-h-screen bg-slate-50 px-4 py-8 dark:bg-slate-950">
    <div class="mx-auto flex w-full max-w-md flex-col gap-6">
      <header class="flex items-center justify-between">
        <div class="flex flex-col">
          <h1 class="text-lg font-semibold tracking-tight">TaskFlow Pro</h1>
          <p class="text-sm text-slate-600 dark:text-slate-300">Sign in to manage your project workspace.</p>
        </div>

        <button
          type="button"
          class="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-800 shadow-sm hover:bg-slate-50 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-100 dark:hover:bg-slate-800"
          @click="theme.toggle()"
        >
          {{ theme.mode === 'dark' ? 'Light' : 'Dark' }} mode
        </button>
      </header>

      <main class="rounded-2xl border border-slate-200 bg-white p-6 shadow-card dark:border-slate-800 dark:bg-slate-900">
        <RouterView />
      </main>

      <footer class="text-center text-xs text-slate-500 dark:text-slate-400">
        Demo credentials: admin@taskflow.pro / Admin123!
      </footer>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useThemeStore } from '@/store/theme'

const theme = useThemeStore()
</script>
