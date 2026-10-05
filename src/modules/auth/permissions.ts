import { computed } from 'vue'

import type { ApiError } from '@/types/api'
import type { UserRole } from '@/types/auth'

import { useAuthStore } from './store'

export type Permission =
  | 'projects:create'
  | 'users:manage'
  | 'tasks:create'
  | 'tasks:update'

const PERMISSIONS_BY_ROLE: Record<UserRole, Permission[]> = {
  admin: ['projects:create', 'users:manage', 'tasks:create', 'tasks:update'],
  member: ['tasks:create', 'tasks:update'],
}

export function hasPermission(role: UserRole | null | undefined, permission: Permission) {
  if (!role) return false
  return PERMISSIONS_BY_ROLE[role].includes(permission)
}

export function usePermissions() {
  const auth = useAuthStore()

  const role = computed(() => auth.user?.role ?? null)
  const can = (permission: Permission) => hasPermission(role.value, permission)

  return { role, can }
}

export function assertPermission(permission: Permission): true {
  const auth = useAuthStore()
  if (hasPermission(auth.user?.role ?? null, permission)) return true

  throw {
    code: 'FORBIDDEN',
    message: 'You do not have permission to perform this action.',
  } satisfies ApiError
}
