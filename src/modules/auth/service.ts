import type { AuthSession, User } from '@/types/auth'
import { requestReal } from '@/api/http'

export type LoginPayload = {
  email: string
  password: string
}

export type RegisterPayload = {
  email: string
  name: string
  password: string
}

export async function login(payload: LoginPayload) {
  return requestReal<AuthSession>({
    url: '/auth/login',
    method: 'POST',
    data: payload,
  })
}

export async function register(payload: RegisterPayload) {
  return requestReal<AuthSession>({
    url: '/auth/register',
    method: 'POST',
    data: payload,
  })
}

export async function me() {
  return requestReal<User>({
    url: '/auth/me',
    method: 'GET',
  })
}
