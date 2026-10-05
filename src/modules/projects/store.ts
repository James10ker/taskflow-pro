import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import type { ApiError } from '@/types/api'
import type { Project } from '@/types/projects'

import { assertPermission } from '@/modules/auth/permissions'

import * as projectsService from './service'

type ProjectId = string

export const useProjectsStore = defineStore('projects', () => {
  const items = ref<Project[]>([])
  const byId = computed<Record<ProjectId, Project>>(() => {
    const map: Record<string, Project> = {}
    for (const p of items.value) map[p.id] = p
    return map
  })

  const loading = ref(false)
  const error = ref<ApiError | null>(null)

  async function fetchAll() {
    loading.value = true
    error.value = null

    try {
      items.value = await projectsService.listProjects()
    } catch (err) {
      items.value = []
      error.value = err as ApiError
    } finally {
      loading.value = false
    }
  }

  async function fetchById(id: string) {
    error.value = null

    try {
      const project = await projectsService.getProject(id)
      const idx = items.value.findIndex((p) => p.id === id)
      if (idx >= 0) items.value[idx] = project
      else items.value.unshift(project)
      return project
    } catch (err) {
      items.value = items.value.filter((project) => project.id !== id)
      error.value = err as ApiError
      return null
    }
  }

  async function create(name: string, description: string) {
    loading.value = true
    error.value = null

    try {
      assertPermission('projects:create')
      const project = await projectsService.createProject({ name, description })
      items.value.unshift(project)
      return project
    } catch (err) {
      error.value = err as ApiError
      return null
    } finally {
      loading.value = false
    }
  }

  async function update(id: string, patch: projectsService.UpdateProjectPayload) {
    loading.value = true
    error.value = null

    try {
      const project = await projectsService.updateProject(id, patch)
      const idx = items.value.findIndex((p) => p.id === id)
      if (idx >= 0) items.value[idx] = project
      else items.value.unshift(project)
      return project
    } catch (err) {
      error.value = err as ApiError
      return null
    } finally {
      loading.value = false
    }
  }

  async function remove(id: string) {
    loading.value = true
    error.value = null

    try {
      await projectsService.deleteProject(id)
      items.value = items.value.filter((p) => p.id !== id)
      return true
    } catch (err) {
      error.value = err as ApiError
      return false
    } finally {
      loading.value = false
    }
  }

  return {
    items,
    byId,
    loading,
    error,
    fetchAll,
    fetchById,
    create,
    update,
    remove,
  }
})
