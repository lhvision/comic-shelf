import { ref } from 'vue'
import {
  api,
  getStoredToken,
  notifyAuthSuccess,
  onUnauthorized,
  setStoredToken,
} from '@/api/client'

const authRequired = ref(false)
const authenticated = ref(true)
const modalVisible = ref(false)
const checking = ref(false)
const submitting = ref(false)
const errorMessage = ref('')

// Register 401 listener once at module level
onUnauthorized(() => {
  authenticated.value = false
  if (authRequired.value) {
    modalVisible.value = true
  }
})

export function useAuth() {
  async function checkStatus() {
    checking.value = true
    try {
      const status = await api.authStatus()
      authRequired.value = status.auth_required
      authenticated.value = status.authenticated
      if (status.auth_required && !status.authenticated) {
        // If we have a stored token, try logging in with it or opening modal
        const stored = getStoredToken()
        if (stored) {
          try {
            await api.login(stored)
            authenticated.value = true
            modalVisible.value = false
            notifyAuthSuccess()
            return true
          } catch {
            setStoredToken('')
            modalVisible.value = true
          }
        } else {
          modalVisible.value = true
        }
      }
    } catch {
      /* network or server offline */
    } finally {
      checking.value = false
    }
    return authenticated.value
  }

  async function login(secret: string): Promise<boolean> {
    if (!secret.trim()) {
      errorMessage.value = '请输入访问口令'
      return false
    }
    submitting.value = true
    errorMessage.value = ''
    try {
      const res = await api.login(secret.trim())
      setStoredToken(res.token)
      authenticated.value = true
      modalVisible.value = false
      notifyAuthSuccess()
      return true
    } catch (err: unknown) {
      errorMessage.value = err instanceof Error ? err.message : '访问口令错误'
      return false
    } finally {
      submitting.value = false
    }
  }

  async function logout(): Promise<void> {
    try {
      await api.logout()
    } finally {
      setStoredToken('')
      authenticated.value = false
      if (authRequired.value) {
        modalVisible.value = true
      }
    }
  }

  function openModal() {
    modalVisible.value = true
    errorMessage.value = ''
  }

  function closeModal() {
    if (authenticated.value || !authRequired.value) {
      modalVisible.value = false
      errorMessage.value = ''
    }
  }

  return {
    authRequired,
    authenticated,
    modalVisible,
    checking,
    submitting,
    errorMessage,
    checkStatus,
    login,
    logout,
    openModal,
    closeModal,
  }
}
