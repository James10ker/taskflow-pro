import type { Project } from '@/types/projects'
import { requestReal } from '@/api/http'

export type CreateProjectPayload = {
  name: string
  description: string
}

export type UpdateProjectPayload = {
  name: string
  description: string
  status: Project['status']
}

export async function listProjects() {
  return requestReal<Project[]>({
    url: '/projects',
    method: 'GET',
  })
}

export async function getProject(id: string) {
  return requestReal<Project>({
    url: `/projects/${id}`,
    method: 'GET',
  })
}

export async function createProject(payload: CreateProjectPayload) {
  return requestReal<Project>(
    {
      url: '/projects',
      method: 'POST',
      data: payload,
    },
    { retries: 0 },
  )
}

export async function updateProject(id: string, payload: UpdateProjectPayload) {
  return requestReal<Project>(
    {
      url: `/projects/${id}`,
      method: 'PUT',
      data: payload,
    },
    { retries: 0 },
  )
}

export async function deleteProject(id: string) {
  return requestReal<{ success: true }>(
    {
      url: `/projects/${id}`,
      method: 'DELETE',
    },
    { retries: 0 },
  )
}
