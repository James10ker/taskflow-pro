import { mockHttp } from '@/api/http'
import type { User } from '@/types/auth'

import { createMockAdapter } from './mockAdapter'
import { createDb } from './mockDb'

export function installMockApi(currentUserProvider: () => User | null) {
  const db = createDb()
  mockHttp.defaults.adapter = createMockAdapter(db, currentUserProvider)
}
