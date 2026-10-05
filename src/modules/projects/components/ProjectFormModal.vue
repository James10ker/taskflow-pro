<template>
  <BaseModal :open="open" :title="title" :subtitle="subtitle" @close="$emit('close')">
    <form id="projectForm" class="flex flex-col gap-4" @submit.prevent="onSubmit">
      <BaseInput
        v-model="name"
        label="Project name"
        placeholder="e.g. Q1 Release"
        :error="errors.name"
      />
      <BaseTextarea
        v-model="description"
        label="Description"
        placeholder="Explain goals, scope, and success criteria."
      />

      <BaseSelect v-if="mode === 'edit'" v-model="status" label="Status" :options="statusOptions" />
    </form>

    <template #footer>
      <div class="flex flex-col gap-2 sm:flex-row sm:justify-end">
        <BaseButton variant="secondary" type="button" @click="$emit('close')">Cancel</BaseButton>
        <BaseButton type="submit" form="projectForm" :loading="projects.loading">{{
          actionLabel
        }}</BaseButton>
      </div>
    </template>
  </BaseModal>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'

import BaseButton from '@/components/BaseButton.vue'
import BaseInput from '@/components/BaseInput.vue'
import BaseModal from '@/components/BaseModal.vue'
import BaseSelect from '@/components/BaseSelect.vue'
import BaseTextarea from '@/components/BaseTextarea.vue'

import type { Project } from '@/types/projects'
import { useProjectsStore } from '@/modules/projects/store'
import { useToastsStore } from '@/store/toasts'

type Mode = 'create' | 'edit'

const props = defineProps<{
  open: boolean
  mode: Mode
  project?: Project | null
}>()

const emit = defineEmits<{ (e: 'close'): void; (e: 'saved', id: string): void }>()

const projects = useProjectsStore()
const toasts = useToastsStore()

const name = ref('')
const description = ref('')
const status = ref<Project['status']>('active')

const errors = reactive<{ name?: string }>({})

watch(
  () => props.open,
  (open) => {
    if (!open) return

    if (props.mode === 'edit' && props.project) {
      name.value = props.project.name
      description.value = props.project.description
      status.value = props.project.status
    } else {
      name.value = ''
      description.value = ''
      status.value = 'active'
    }

    errors.name = undefined
  },
)

const title = computed(() => (props.mode === 'edit' ? 'Edit project' : 'Create project'))
const subtitle = computed(() =>
  props.mode === 'edit'
    ? 'Update this project’s basic details.'
    : 'Create a new project with yourself as its owner.',
)

const actionLabel = computed(() => (props.mode === 'edit' ? 'Save changes' : 'Create project'))

const statusOptions = computed(() => [
  { value: 'active', label: 'Active' },
  { value: 'paused', label: 'Paused' },
  { value: 'completed', label: 'Completed' },
])

function validate() {
  errors.name = undefined
  if (!name.value.trim()) errors.name = 'Project name is required.'
  else if (name.value.trim().length > 150)
    errors.name = 'Project name must be 150 characters or fewer.'
  return !errors.name
}

async function onSubmit() {
  if (!validate()) return

  if (props.mode === 'create') {
    const created = await projects.create(name.value, description.value)
    if (created) {
      toasts.success('Project created.')
      emit('saved', created.id)
      emit('close')
    }
    return
  }

  if (!props.project) return

  const updated = await projects.update(props.project.id, {
    name: name.value,
    description: description.value,
    status: status.value,
  })

  if (updated) {
    toasts.success('Project updated.')
    emit('saved', updated.id)
    emit('close')
  }
}
</script>
