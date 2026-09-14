import type { User } from '@/types/auth'
import type { ActivityEvent } from '@/types/activity'
import type { Project } from '@/types/projects'
import type { Task, TaskComment } from '@/types/tasks'
import { createId } from '@/utils/id'
import { readJson, writeJson } from '@/utils/storage'

export type DbState = {
  users: User[]
  projects: Project[]
  tasks: Task[]
  comments: TaskComment[]
  activity: ActivityEvent[]
}

const STORAGE_KEY = 'taskflow_pro_db_v1'

export function createDb() {
  const state = loadDb()
  // Rewrite legacy browser data once so upstream plaintext demo passwords
  // are removed after Auth moves to the real backend.
  writeJson(STORAGE_KEY, state)

  function save() {
    writeJson(STORAGE_KEY, state)
  }

  return {
    state,
    save,
  }
}

function loadDb(): DbState {
  const seeded = seedDb()
  const persisted = readJson<DbState | null>(STORAGE_KEY, null)
  if (!persisted) return seeded

  return {
    ...seeded,
    ...persisted,
    users: Array.isArray((persisted as Partial<DbState>).users)
      ? persisted.users.map(({ id, email, name, role, avatarColor }) => ({ id, email, name, role, avatarColor }))
      : seeded.users,
    activity: Array.isArray((persisted as Partial<DbState>).activity) ? persisted.activity : [],
  }
}

function seedDb(): DbState {
  const adminId = createId('usr')
  const memberId = createId('usr')

  const projectId = createId('prj')

  const now = new Date().toISOString()

  const users: User[] = [
    {
      id: adminId,
      email: 'admin@taskflow.pro',
      name: 'Amina Hassan',
      role: 'admin',
      avatarColor: '#7c3aed',
    },
    {
      id: memberId,
      email: 'member@taskflow.pro',
      name: 'Omar Saeed',
      role: 'member',
      avatarColor: '#0ea5e9',
    },
  ]

  const projects: Project[] = [
    {
      id: projectId,
      name: 'Mobile App Redesign',
      description: 'Plan and execute the Q1 redesign initiative with clear milestones and release scope.',
      status: 'active',
      ownerId: adminId,
      memberIds: [adminId, memberId],
      createdAt: now,
      updatedAt: now,
    },
  ]

  const tasks: Task[] = [
    {
      id: createId('tsk'),
      projectId,
      title: 'Define success metrics',
      description: 'Align on the KPIs we want to improve (activation, retention, and task completion).',
      status: 'todo',
      priority: 'high',
      dueDate: addDaysIso(6),
      assigneeId: adminId,
      createdAt: now,
      updatedAt: now,
    },
    {
      id: createId('tsk'),
      projectId,
      title: 'Audit current user flows',
      description: 'Identify friction points across onboarding and project creation.',
      status: 'in_progress',
      priority: 'medium',
      dueDate: addDaysIso(9),
      assigneeId: memberId,
      createdAt: now,
      updatedAt: now,
    },
    {
      id: createId('tsk'),
      projectId,
      title: 'Finalize design handoff checklist',
      description: 'Create a repeatable checklist for Figma specs, tokens, and accessibility notes.',
      status: 'done',
      priority: 'low',
      createdAt: now,
      updatedAt: now,
    },
  ]

  const comments: TaskComment[] = []

  const activity: ActivityEvent[] = []

  return { users, projects, tasks, comments, activity }
}

function addDaysIso(days: number) {
  const d = new Date()
  d.setDate(d.getDate() + days)
  return d.toISOString()
}
