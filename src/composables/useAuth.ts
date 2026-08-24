import { computed, ref } from 'vue'
import {
  api,
  getStoredToken,
  notifyAuthSuccess,
  onUnauthorized,
  setStoredToken,
} from '@/api/client'

const authRequired = ref(false)
const authenticated = ref(true)
const role = ref<'admin' | 'guest' | 'unauthorized'>('admin')
const modalVisible = ref(false)
const checking = ref(false)
const submitting = ref(false)
const errorMessage = ref('')

const canWrite = computed(
  () => !authRequired.value || (authenticated.value && role.value === 'admin'),
)
const isGuest = computed(() => authenticated.value && role.value === 'guest')

// Register 401 listener once at module level
onUnauthorized(() => {
  authenticated.value = false
  role.value = 'unauthorized'
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
      role.value = status.role
      if (status.auth_required && !status.authenticated) {
        // If we have a stored token, try logging in with it
        const stored = getStoredToken()
        if (stored) {
          try {
            const res = await api.login(stored)
            authenticated.value = true
            role.value = res.role || 'admin'
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
      errorMessage.value = '请输入通行口令'
      return false
    }
    submitting.value = true
    errorMessage.value = ''
    try {
      const res = await api.login(secret.trim())
      setStoredToken(res.token)
      authenticated.value = true
      role.value = res.role || 'admin'
      modalVisible.value = false
      notifyAuthSuccess()
      return true
    } catch (err: unknown) {
      errorMessage.value = err instanceof Error ? err.message : '通行口令错误'
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
      role.value = 'unauthorized'
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
    role,
    canWrite,
    isGuest,
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
