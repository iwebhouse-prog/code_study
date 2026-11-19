import type { AxiosInstance } from 'axios'
import type { AuthUser } from '../stores/auth-store'
import { apiClient } from './api-client'

export const REFRESH_PATH = '/auth/refresh'

/** User object as the backend sends it (contracts/auth-api.md). */
interface UserResponse {
  id: string
  email: string
  skill_level: string
}

export interface Credentials {
  email: string
  password: string
}

export function toAuthUser(body: UserResponse): AuthUser {
  return { id: body.id, email: body.email, skillLevel: body.skill_level }
}

// The server sets and clears the token cookies; nothing here sees a token.
export function createAuthService(client: AxiosInstance) {
  return {
    register: async (credentials: Credentials) =>
      toAuthUser((await client.post<UserResponse>('/auth/register', credentials)).data),
    login: async (credentials: Credentials) =>
      toAuthUser((await client.post<UserResponse>('/auth/login', credentials)).data),
    me: async () => toAuthUser((await client.get<UserResponse>('/auth/me')).data),
    refresh: async () => toAuthUser((await client.post<UserResponse>(REFRESH_PATH)).data),
    logout: async (): Promise<void> => {
      await client.post('/auth/logout')
    },
  }
}

export const authService = createAuthService(apiClient)
