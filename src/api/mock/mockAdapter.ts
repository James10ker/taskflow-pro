import type { AxiosAdapter, AxiosRequestConfig, AxiosResponse, InternalAxiosRequestConfig } from 'axios'

import type { ApiError } from '@/types/api'
import type { User } from '@/types/auth'
import type { ActivityEvent } from '@/types/activity'
import type { Project } from '@/types/projects'
import type { Task, TaskComment, TaskStatus } from '@/types/tasks'
import { createId } from '@/utils/id'

import type { DbState } from './mockDb'

type Db = { state: DbState; save: () => void }
type CurrentUserProvider = () => User | null

type JsonBody = Record<string, unknown> | null

export function createMockAdapter(db: Db, currentUserProvider: CurrentUserProvider): AxiosAdapter {
  return async (config: InternalAxiosRequestConfig) => {
    await sleep(220)

    const method = (config.method ?? 'get').toLowerCase()
    const url = normalizeUrl(config.url)

    try {
      const authUser = getAuthUser(db.state, config, currentUserProvider)

      if (!authUser) return fail(config, 401, { code: 'UNAUTHORIZED', message: 'Not signed in.' })

      if (method === 'get' && url === '/users') {
        return ok(config, db.state.users)
      }

      if (method === 'get' && url === '/projects') {
        return ok(config, db.state.projects.filter((p) => p.memberIds.includes(authUser.id)))
      }

      if (method === 'post' && url === '/projects') {
        const body = readBody(config)
        const name = String(body?.name ?? '').trim()
        const description = String(body?.description ?? '').trim()

        if (!name) {
          return fail(config, 422, {
            code: 'VALIDATION_ERROR',
            message: 'Invalid project data.',
            details: { name: 'Project name is required.' },
          })
        }

        const now = new Date().toISOString()
        const project: Project = {
          id: createId('prj'),
          name,
          description,
          status: 'active',
          ownerId: authUser.id,
          memberIds: [authUser.id],
          createdAt: now,
          updatedAt: now,
        }

        db.state.projects.unshift(project)
        logActivity(db.state, {
          projectId: project.id,
          action: 'project_created',
          description: `Project created: ${project.name}`,
          actorId: authUser.id,
          actorRole: authUser.role,
        })
        db.save()
        return ok(config, project)
      }

      const projectIdMatch = url.match(/^\/projects\/([^/]+)$/)
      if (projectIdMatch) {
        const projectId = projectIdMatch[1]
        const project = db.state.projects.find((p) => p.id === projectId)
        if (!project) return fail(config, 404, { code: 'NOT_FOUND', message: 'Project not found.' })
        if (!project.memberIds.includes(authUser.id)) return fail(config, 403, { code: 'FORBIDDEN', message: 'No access to this project.' })

        if (method === 'get') return ok(config, project)

        if (method === 'put') {
          const body = readBody(config)
          const nextName = String(body?.name ?? project.name).trim()
          const nextDesc = String(body?.description ?? project.description).trim()
          const nextStatus = (body?.status as Project['status']) ?? project.status
          const nextMembers = Array.isArray(body?.memberIds) ? (body?.memberIds as string[]) : project.memberIds

          project.name = nextName
          project.description = nextDesc
          project.status = nextStatus
          project.memberIds = unique([project.ownerId, ...nextMembers])
          project.updatedAt = new Date().toISOString()

          db.save()
          return ok(config, project)
        }

        if (method === 'delete') {
          db.state.projects = db.state.projects.filter((p) => p.id !== projectId)
          db.state.tasks = db.state.tasks.filter((t) => t.projectId !== projectId)
          db.state.comments = db.state.comments.filter((c) => db.state.tasks.some((t) => t.id === c.taskId))
          db.save()
          return ok(config, { success: true })
        }
      }

      const activityMatch = url.match(/^\/projects\/([^/]+)\/activity$/)
      if (activityMatch) {
        const projectId = activityMatch[1]
        const project = db.state.projects.find((p) => p.id === projectId)
        if (!project) return fail(config, 404, { code: 'NOT_FOUND', message: 'Project not found.' })
        if (!project.memberIds.includes(authUser.id)) return fail(config, 403, { code: 'FORBIDDEN', message: 'No access to this project.' })

        if (method === 'get') {
          return ok(config, db.state.activity.filter((e) => e.projectId === projectId).slice().reverse())
        }
      }

      const tasksMatch = url.match(/^\/projects\/([^/]+)\/tasks$/)
      if (tasksMatch) {
        const projectId = tasksMatch[1]
        const project = db.state.projects.find((p) => p.id === projectId)
        if (!project) return fail(config, 404, { code: 'NOT_FOUND', message: 'Project not found.' })
        if (!project.memberIds.includes(authUser.id)) return fail(config, 403, { code: 'FORBIDDEN', message: 'No access to this project.' })

        if (method === 'get') {
          return ok(config, db.state.tasks.filter((t) => t.projectId === projectId))
        }

        if (method === 'post') {
          const body = readBody(config)
          const title = String(body?.title ?? '').trim()
          const description = String(body?.description ?? '').trim()
          const priority = (body?.priority as Task['priority']) ?? 'medium'
          const dueDate = body?.dueDate ? String(body.dueDate) : undefined
          const assigneeId = body?.assigneeId ? String(body.assigneeId) : undefined

          if (!title) {
            return fail(config, 422, {
              code: 'VALIDATION_ERROR',
              message: 'Invalid task data.',
              details: { title: 'Task title is required.' },
            })
          }

          if (assigneeId && !project.memberIds.includes(assigneeId)) {
            return fail(config, 422, {
              code: 'VALIDATION_ERROR',
              message: 'Invalid task data.',
              details: { assigneeId: 'Assignee must be a project member.' },
            })
          }

          const now = new Date().toISOString()
          const task: Task = {
            id: createId('tsk'),
            projectId,
            title,
            description,
            status: 'todo',
            priority,
            dueDate,
            assigneeId,
            createdAt: now,
            updatedAt: now,
          }

          db.state.tasks.unshift(task)
          logActivity(db.state, {
            projectId,
            action: 'task_created',
            description: `Task created: ${task.title}`,
            actorId: authUser.id,
            actorRole: authUser.role,
          })

          if (task.assigneeId) {
            const assignee = db.state.users.find((u) => u.id === task.assigneeId)
            const assigneeName = assignee?.name ?? 'Unknown'
            logActivity(db.state, {
              projectId,
              action: 'task_assigned',
              description: `Task assigned: ${task.title} → ${assigneeName}`,
              actorId: authUser.id,
              actorRole: authUser.role,
            })
          }
          db.save()
          return ok(config, task)
        }
      }

      const commentsMatch = url.match(/^\/tasks\/([^/]+)\/comments$/)
      if (commentsMatch) {
        const taskId = commentsMatch[1]
        const task = db.state.tasks.find((t) => t.id === taskId)
        if (!task) return fail(config, 404, { code: 'NOT_FOUND', message: 'Task not found.' })

        const project = db.state.projects.find((p) => p.id === task.projectId)
        if (!project) return fail(config, 404, { code: 'NOT_FOUND', message: 'Project not found.' })
        if (!project.memberIds.includes(authUser.id)) return fail(config, 403, { code: 'FORBIDDEN', message: 'No access to this project.' })

        if (method === 'get') {
          return ok(config, db.state.comments.filter((c) => c.taskId === taskId))
        }

        if (method === 'post') {
          const body = readBody(config)
          const message = String(body?.message ?? '').trim()
          if (!message) {
            return fail(config, 422, {
              code: 'VALIDATION_ERROR',
              message: 'Invalid comment.',
              details: { message: 'Comment cannot be empty.' },
            })
          }

          const comment: TaskComment = {
            id: createId('cmt'),
            taskId,
            authorId: authUser.id,
            message,
            createdAt: new Date().toISOString(),
          }

          db.state.comments.push(comment)
          db.save()
          return ok(config, comment)
        }
      }

      const taskMatch = url.match(/^\/tasks\/([^/]+)$/)
      if (taskMatch) {
        const taskId = taskMatch[1]
        const task = db.state.tasks.find((t) => t.id === taskId)
        if (!task) return fail(config, 404, { code: 'NOT_FOUND', message: 'Task not found.' })

        const project = db.state.projects.find((p) => p.id === task.projectId)
        if (!project) return fail(config, 404, { code: 'NOT_FOUND', message: 'Project not found.' })
        if (!project.memberIds.includes(authUser.id)) return fail(config, 403, { code: 'FORBIDDEN', message: 'No access to this project.' })

        if (method === 'patch') {
          const body = readBody(config)

          const nextStatus = (body?.status as TaskStatus | undefined) ?? task.status
          const nextTitle = body?.title !== undefined ? String(body.title).trim() : task.title
          const nextDesc = body?.description !== undefined ? String(body.description).trim() : task.description
          const nextPriority = (body?.priority as Task['priority'] | undefined) ?? task.priority
          const nextDueDate = body?.dueDate !== undefined ? (body?.dueDate ? String(body.dueDate) : undefined) : task.dueDate
          const nextAssigneeId = body?.assigneeId !== undefined ? (body?.assigneeId ? String(body.assigneeId) : undefined) : task.assigneeId

          const prevStatus = task.status
          const prevAssigneeId = task.assigneeId

          if (!nextTitle) {
            return fail(config, 422, {
              code: 'VALIDATION_ERROR',
              message: 'Invalid task data.',
              details: { title: 'Task title is required.' },
            })
          }

          if (nextAssigneeId && !project.memberIds.includes(nextAssigneeId)) {
            return fail(config, 422, {
              code: 'VALIDATION_ERROR',
              message: 'Invalid task data.',
              details: { assigneeId: 'Assignee must be a project member.' },
            })
          }

          task.status = nextStatus
          task.title = nextTitle
          task.description = nextDesc
          task.priority = nextPriority
          task.dueDate = nextDueDate
          task.assigneeId = nextAssigneeId
          task.updatedAt = new Date().toISOString()

          if (prevStatus !== nextStatus) {
            logActivity(db.state, {
              projectId: task.projectId,
              action: 'task_moved',
              description: `Task moved: ${task.title} → ${statusLabel(nextStatus)}`,
              actorId: authUser.id,
              actorRole: authUser.role,
            })
          }

          if (prevAssigneeId !== nextAssigneeId && nextAssigneeId) {
            const assignee = db.state.users.find((u) => u.id === nextAssigneeId)
            const assigneeName = assignee?.name ?? 'Unknown'
            logActivity(db.state, {
              projectId: task.projectId,
              action: 'task_assigned',
              description: `Task assigned: ${task.title} → ${assigneeName}`,
              actorId: authUser.id,
              actorRole: authUser.role,
            })
          }

          db.save()
          return ok(config, task)
        }

        if (method === 'delete') {
          db.state.tasks = db.state.tasks.filter((t) => t.id !== taskId)
          db.state.comments = db.state.comments.filter((c) => c.taskId !== taskId)
          db.save()
          return ok(config, { success: true })
        }
      }

      return fail(config, 404, { code: 'NOT_FOUND', message: 'Endpoint not found.' })
    } catch (err) {
      if (err instanceof ApiErrorImpl) {
        return fail(config, statusFromCode(err.code), { code: err.code, message: err.message })
      }

      return fail(config, 500, { code: 'INTERNAL_ERROR', message: 'Mock server error.' })
    }
  }
}

function normalizeUrl(url: string | undefined) {
  if (!url) return ''
  const u = url.split('?')[0]
  return u.startsWith('/') ? u : `/${u}`
}

function ok<T>(config: InternalAxiosRequestConfig, data: T): AxiosResponse<T> {
  return {
    data,
    status: 200,
    statusText: 'OK',
    headers: {},
    config,
  }
}

function fail(config: InternalAxiosRequestConfig, status: number, data: ApiError): AxiosResponse<ApiError> {
  return {
    data,
    status,
    statusText: 'Error',
    headers: {},
    config,
  }
}

function readBody(config: AxiosRequestConfig): JsonBody {
  const raw = config.data
  if (!raw) return null

  if (typeof raw === 'string') {
    try {
      return JSON.parse(raw) as JsonBody
    } catch {
      return null
    }
  }

  if (typeof raw === 'object') return raw as JsonBody

  return null
}

function logActivity(state: DbState, input: Omit<ActivityEvent, 'id' | 'createdAt'>) {
  const event: ActivityEvent = {
    id: createId('act'),
    createdAt: new Date().toISOString(),
    ...input,
  }

  state.activity.push(event)
}

function statusLabel(status: TaskStatus) {
  if (status === 'todo') return 'To do'
  if (status === 'in_progress') return 'In progress'
  return 'Done'
}

function getAuthUser(state: DbState, config: AxiosRequestConfig, currentUserProvider: CurrentUserProvider): User | null {
  const raw = String((config.headers as Record<string, unknown> | undefined)?.Authorization ?? '')
  const token = raw.startsWith('Bearer ') ? raw.slice('Bearer '.length).trim() : ''
  if (!token) return null

  // W1 bridge only: map the server-authenticated session to the old seeded
  // user's mock ID so projects/tasks can remain in localStorage for now.
  const currentUser = currentUserProvider()
  if (!currentUser) return null

  const mockUser = state.users.find((user) => user.email.toLowerCase() === currentUser.email.toLowerCase())
  if (!mockUser) return null
  return { ...mockUser, role: currentUser.role }
}

class ApiErrorImpl extends Error {
  public readonly code: ApiError['code']

  public constructor(code: ApiError['code'], message: string) {
    super(message)
    this.code = code
  }
}

function statusFromCode(code: ApiError['code']) {
  if (code === 'UNAUTHORIZED') return 401
  if (code === 'FORBIDDEN') return 403
  if (code === 'NOT_FOUND') return 404
  if (code === 'CONFLICT') return 409
  if (code === 'VALIDATION_ERROR') return 422
  return 500
}

function unique(ids: string[]) {
  return Array.from(new Set(ids))
}

function sleep(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}
