<template>
  <div class="flex flex-col gap-6">
    <div class="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
      <div>
        <div class="text-sm font-semibold">Projects</div>
        <div class="mt-1 text-sm text-slate-600 dark:text-slate-300">
          Projects shown here come from the authenticated backend API.
        </div>
      </div>

      <BaseButton v-if="perms.can('projects:create')" @click="openCreate"
        >Create project</BaseButton
      >
    </div>

    <div class="flex flex-col gap-3 sm:flex-row">
      <BaseInput v-model="searchInput" label="Search" placeholder="Search by project name" />
      <BaseSelect v-model="statusFilter" label="Status" :options="statusOptions" />
    </div>

    <div
      v-if="projects.loading"
      class="rounded-2xl border border-slate-200 bg-white p-6 shadow-card dark:border-slate-800 dark:bg-slate-900"
    >
      <div class="text-sm font-semibold">Loading projects…</div>
      <div class="mt-1 text-sm text-slate-600 dark:text-slate-300">
        Fetching your latest workspace data.
      </div>
    </div>

    <div
      v-else-if="projects.error"
      class="rounded-2xl border border-rose-200 bg-rose-50 p-6 text-rose-700 dark:border-rose-900/60 dark:bg-rose-950/40 dark:text-rose-200"
    >
      <div class="text-sm font-semibold">Couldn’t load projects</div>
      <div class="mt-1 text-sm">Please try again.</div>
      <div class="mt-4">
        <BaseButton variant="secondary" @click="projects.fetchAll">Try again</BaseButton>
      </div>
    </div>

    <div v-else class="grid gap-4 lg:grid-cols-2">
      <ProjectCard v-for="p in filteredProjects" :key="p.id" :project="p" />

      <div
        v-if="!filteredProjects.length"
        class="rounded-2xl border border-dashed border-slate-300 bg-white p-8 text-center text-slate-600 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-300"
      >
        <div class="text-sm font-semibold text-slate-900 dark:text-slate-50">No projects yet</div>
        <div class="mt-1 text-sm">Create your first project to start organizing the workspace.</div>
        <div class="mt-5">
          <BaseButton v-if="perms.can('projects:create')" @click="openCreate"
            >Create project</BaseButton
          >
        </div>
      </div>
    </div>

    <ProjectFormModal
      :open="formOpen"
      :mode="formMode"
      :project="selectedProject"
      @close="formOpen = false"
      @saved="onSaved"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'

import BaseButton from '@/components/BaseButton.vue'
import BaseInput from '@/components/BaseInput.vue'
import BaseSelect from '@/components/BaseSelect.vue'
import ProjectCard from '@/modules/projects/components/ProjectCard.vue'
import ProjectFormModal from '@/modules/projects/components/ProjectFormModal.vue'

import { useProjectsStore } from '@/modules/projects/store'
import { usePermissions } from '@/modules/auth/permissions'

import { debounce } from '@/utils/debounce'

const router = useRouter()
const projects = useProjectsStore()
const perms = usePermissions()

const searchInput = ref('')
const search = ref('')
const statusFilter = ref<'all' | 'active' | 'paused' | 'completed'>('all')

const statusOptions = computed(() => [
  { value: 'all', label: 'All' },
  { value: 'active', label: 'Active' },
  { value: 'paused', label: 'Paused' },
  { value: 'completed', label: 'Completed' },
])

const applySearch = debounce((value: string) => {
  search.value = value
}, 250)

watch(searchInput, (value) => {
  applySearch(value)
})

const filteredProjects = computed(() => {
  const q = search.value.trim().toLowerCase()
  return projects.items.filter((p) => {
    const matchesQuery = !q || p.name.toLowerCase().includes(q)
    const matchesStatus = statusFilter.value === 'all' ? true : p.status === statusFilter.value
    return matchesQuery && matchesStatus
  })
})

const formOpen = ref(false)
const formMode = ref<'create' | 'edit'>('create')
const selectedProjectId = ref<string | null>(null)

const selectedProject = computed(() =>
  selectedProjectId.value ? projects.byId[selectedProjectId.value] : null,
)

onMounted(async () => {
  await projects.fetchAll()
})

function openCreate() {
  formMode.value = 'create'
  selectedProjectId.value = null
  formOpen.value = true
}

function onSaved(id: string) {
  router.push({ name: 'project', params: { id } })
}
</script>
