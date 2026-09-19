import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import { getCurrentUser, login, register } from '@/api/auth'
import { AUTH_TOKEN_KEY, getApiErrorMessage } from '@/api/http'
import type { AuthUser, LoginPayload, RegisterPayload } from '@/types/auth'

export const useAuthStore = defineStore('auth', () => {
  const token = ref<string | null>(localStorage.getItem(AUTH_TOKEN_KEY))
  const user = ref<AuthUser | null>(null)
  const loading = ref(false)
  const initialized = ref(false)
  const error = ref<string | null>(null)

  const isAuthenticated = computed(() => Boolean(token.value && user.value))

  function saveToken(accessToken: string): void {
    token.value = accessToken
    localStorage.setItem(AUTH_TOKEN_KEY, accessToken)
  }

  function clearSession(): void {
    token.value = null
    user.value = null
    localStorage.removeItem(AUTH_TOKEN_KEY)
  }

  async function restore(): Promise<void> {
    if (!token.value) {
      initialized.value = true
      return
    }
    try {
      user.value = await getCurrentUser()
    } catch {
      clearSession()
    } finally {
      initialized.value = true
    }
  }

  async function loginWithCredentials(payload: LoginPayload): Promise<void> {
    loading.value = true
    error.value = null
    try {
      const response = await login(payload)
      saveToken(response.access_token)
      user.value = await getCurrentUser()
    } catch (requestError) {
      clearSession()
      error.value = getApiErrorMessage(requestError, 'Unable to sign in.')
      throw requestError
    } finally {
      loading.value = false
    }
  }

  async function registerAccount(payload: RegisterPayload): Promise<void> {
    loading.value = true
    error.value = null
    try {
      const response = await register(payload)
      saveToken(response.token.access_token)
      user.value = response.user
    } catch (requestError) {
      error.value = getApiErrorMessage(requestError, 'Unable to create the account.')
      throw requestError
    } finally {
      loading.value = false
    }
  }

  function logout(): void {
    clearSession()
  }

  return {
    token,
    user,
    loading,
    initialized,
    error,
    isAuthenticated,
    restore,
    loginWithCredentials,
    registerAccount,
    logout,
  }
})
