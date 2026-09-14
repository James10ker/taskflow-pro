import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import type { ApiError } from '@/types/api'
import type { AuthSession, User } from '@/types/auth'
import { readJson, writeJson } from '@/utils/storage'
import { setAuthTokenProvider } from '@/api/http'

import * as authService from './service'

const STORAGE_KEY = 'taskflow_pro_session_v1'

type StoredSession = AuthSession | null

export const useAuthStore = defineStore('auth', () => {
  const session = ref<AuthSession | null>(null)
  const loading = ref(false)
  const error = ref<ApiError | null>(null)

  const isAuthenticated = computed(() => Boolean(session.value?.token.accessToken))
  const user = computed<User | null>(() => session.value?.user ?? null)
  const token = computed(() => session.value?.token.accessToken ?? null)

  function hydrate() {
    const stored = readJson<StoredSession>(STORAGE_KEY, null)
    session.value = stored

    setAuthTokenProvider(() => token.value)
  }

  async function login(email: string, password: string) {
    loading.value = true
    error.value = null

    try {
      const next = await authService.login({ email, password })
      session.value = next
      writeJson(STORAGE_KEY, next)
      return true
    } catch (err) {
      error.value = err as ApiError
      return false
    } finally {
      loading.value = false
    }
  }

  async function register(name: string, email: string, password: string) {
    loading.value = true
    error.value = null

    try {
      const next = await authService.register({ name, email, password })
      session.value = next
      writeJson(STORAGE_KEY, next)
      return true
    } catch (err) {
      error.value = err as ApiError
      return false
    } finally {
      loading.value = false
    }
  }

  async function refreshMe() {
    if (!token.value) return false

    try {
      const me = await authService.me()
      if (session.value) {
        session.value = { ...session.value, user: me }
        writeJson(STORAGE_KEY, session.value)
      }
      return true
    } catch {
      logout()
      return false
    }
  }

  function logout() {
    session.value = null
    error.value = null
    writeJson(STORAGE_KEY, null)
  }

  return {
    session,
    loading,
    error,
    isAuthenticated,
    user,
    token,
    hydrate,
    login,
    register,
    refreshMe,
    logout,
  }
})
