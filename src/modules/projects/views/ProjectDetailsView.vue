<template>
  <div
    v-if="loading"
    class="rounded-2xl border border-slate-200 bg-white p-6 shadow-card dark:border-slate-800 dark:bg-slate-900"
  >
    <div class="text-sm font-semibold">Loading project…</div>
    <div class="mt-1 text-sm text-slate-600 dark:text-slate-300">
      Fetching the project from the backend API.
    </div>
  </div>

  <div
    v-else-if="!project"
    class="rounded-2xl border border-rose-200 bg-rose-50 p-6 text-rose-700 dark:border-rose-900/60 dark:bg-rose-950/40 dark:text-rose-200"
  >
    <div class="text-sm font-semibold">Project unavailable</div>
    <div class="mt-1 text-sm">
      {{
        projects.error?.message ||
        'The project might have been removed or you no longer have access.'
      }}
    </div>
    <div class="mt-4">
      <BaseButton variant="secondary" @click="router.push({ name: 'projects' })"
        >Back to projects</BaseButton
      >
    </div>
  </div>

  <div v-else class="flex flex-col gap-6">
    <div
      class="rounded-2xl border border-slate-200 bg-white p-6 shadow-card dark:border-slate-800 dark:bg-slate-900"
    >
      <div class="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
        <div>
          <div class="text-lg font-semibold">{{ project.name }}</div>
          <div class="mt-1 text-sm text-slate-600 dark:text-slate-300">
            {{ project.description || 'No description yet.' }}
          </div>

          <div
            class="mt-4 flex flex-wrap items-center gap-2 text-xs text-slate-600 dark:text-slate-300"
          >
            <span
              class="rounded-full bg-slate-100 px-2 py-1 font-semibold text-slate-800 dark:bg-slate-800 dark:text-slate-100"
            >
              {{ statusLabel }}
            </span>
            <span>{{ isOwner ? 'You are the project owner' : 'You have member access' }}</span>
            <span>Updated {{ updatedLabel }}</span>
          </div>
        </div>

        <div v-if="isOwner" class="flex flex-col gap-2 sm:flex-row">
          <BaseButton variant="secondary" @click="openEdit">Edit</BaseButton>
          <BaseButton variant="danger" :loading="projects.loading" @click="onDelete"
            >Delete</BaseButton
          >
        </div>
      </div>
    </div>

    <div
      class="rounded-2xl border border-amber-200 bg-amber-50 p-6 dark:border-amber-900/60 dark:bg-amber-950/30"
    >
      <div class="text-sm font-semibold text-amber-950 dark:text-amber-100">
        Project extensions are not available yet
      </div>
      <div class="mt-2 text-sm text-amber-800 dark:text-amber-200">
        Task boards, activity history, and member management have not been migrated to the real
        backend. This page does not load their legacy mock data.
      </div>
    </div>

    <ProjectFormModal
      :open="formOpen"
      mode="edit"
      :project="project"
      @close="formOpen = false"
      @saved="onSaved"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import BaseButton from '@/components/BaseButton.vue'
import { useAuthStore } from '@/modules/auth/store'
import ProjectFormModal from '@/modules/projects/components/ProjectFormModal.vue'
import { useProjectsStore } from '@/modules/projects/store'

const router = useRouter()
const route = useRoute()

const auth = useAuthStore()
const projects = useProjectsStore()

const formOpen = ref(false)
const loading = ref(true)

const projectId = computed(() => String(route.params.id))
const project = computed(() => projects.byId[projectId.value])
const isOwner = computed(() => Boolean(project.value && auth.user?.id === project.value.ownerId))

const statusLabel = computed(() => {
  if (!project.value) return ''
  if (project.value.status === 'paused') return 'Paused'
  if (project.value.status === 'completed') return 'Completed'
  return 'Active'
})

const updatedLabel = computed(() => {
  if (!project.value) return ''
  const date = new Date(project.value.updatedAt)
  return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
})

onMounted(loadProject)
watch(projectId, loadProject)

async function loadProject() {
  loading.value = true
  try {
    await projects.fetchById(projectId.value)
  } finally {
    loading.value = false
  }
}

function openEdit() {
  formOpen.value = true
}

async function onDelete() {
  if (!project.value) return
  const confirmed = window.confirm(
    'Delete this project and its associated records? This action cannot be undone.',
  )
  if (!confirmed) return

  const removed = await projects.remove(project.value.id)
  if (removed) await router.push({ name: 'projects' })
}

async function onSaved() {
  await projects.fetchById(projectId.value)
}
</script>
