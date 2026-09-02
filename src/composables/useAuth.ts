import { computed, ref } from 'vue'
import {
  api,
  ApiError,
  getStoredToken,
  notifyAuthSuccess,
  onUnauthorized,
  setStoredToken,
} from '@/api/client'
import { useToast } from '@/composables/useToast'

const authRequired = ref(false)
const authenticated = ref(true)
const role = ref<'admin' | 'guest' | 'unauthorized'>('admin')
const username = ref('')
const userId = ref('')
const modalVisible = ref(false)
const checking = ref(false)
const submitting = ref(false)
const errorMessage = ref('')

const canWrite = computed(
  () => !authRequired.value || (authenticated.value && role.value === 'admin'),
)
const isGuest = computed(() => authenticated.value && role.value === 'guest')

// Register 401 listener once at module level with auto-reconnect attempt
let isReauthenticating = false
onUnauthorized(async () => {
  if (isReauthenticating) return
  const stored = getStoredToken()
  if (stored) {
    isReauthenticating = true
    try {
      const res = await api.login(stored)
      authenticated.value = true
      role.value = res.role || 'admin'
      username.value = res.username || (res.role === 'admin' ? '馆长' : '访客')
      userId.value = res.user_id || ''
      modalVisible.value = false
      notifyAuthSuccess()
      return
    } catch {
      // Re-authentication failed, proceed to unauthorized state
    } finally {
      isReauthenticating = false
    }
  }

  authenticated.value = false
  role.value = 'unauthorized'
  if (authRequired.value) {
    modalVisible.value = true
  }
})

export function useAuth() {
  const { toast } = useToast()

  async function checkStatus() {
    checking.value = true
    try {
      const status = await api.authStatus()
      authRequired.value = status.auth_required
      authenticated.value = status.authenticated
      role.value = status.role
      username.value = status.username || (status.role === 'admin' ? '馆长' : '')
      userId.value = status.user_id || ''

      // 0. 支持链接免密直达：若 URL Query 携带 ?token=...，自动验证入馆
      let urlToken: string | null = null
      if (typeof window !== 'undefined') {
        const params = new URLSearchParams(window.location.search)
        urlToken = params.get('token')
      }

      if (urlToken) {
        try {
          const res = await api.login(urlToken)
          setStoredToken(urlToken)
          authenticated.value = true
          role.value = res.role || 'guest'
          username.value = res.username || (res.role === 'admin' ? '馆长' : '访客')
          userId.value = res.user_id || ''
          modalVisible.value = false
          notifyAuthSuccess()

          // 清理地址栏 token 参数，防止二次复制分享泄露口令
          const cleanUrl = new URL(window.location.href)
          cleanUrl.searchParams.delete('token')
          window.history.replaceState({}, '', cleanUrl.pathname + cleanUrl.search + cleanUrl.hash)
          return true
        } catch (err: unknown) {
          const msg =
            err instanceof Error ? err.message : '该直达通行证已失效或过期，请向馆长申请新凭证'
          toast(msg, 'error')
          const cleanUrl = new URL(window.location.href)
          cleanUrl.searchParams.delete('token')
          window.history.replaceState({}, '', cleanUrl.pathname + cleanUrl.search + cleanUrl.hash)
        }
      }

      // If auth is required, check if we have a stored token to restore curator privileges
      const stored = getStoredToken()
      if (status.auth_required && stored && (!status.authenticated || role.value !== 'admin')) {
        try {
          const res = await api.login(stored)
          authenticated.value = true
          role.value = res.role || 'admin'
          username.value = res.username || (res.role === 'admin' ? '馆长' : '')
          userId.value = res.user_id || ''
          modalVisible.value = false
          notifyAuthSuccess()
          return true
        } catch (err: unknown) {
          // Only clear stored token if the server explicitly rejected the credentials with wrong password / disabled
          const isExplicitWrongAuth =
            (err instanceof ApiError &&
              (err.status === 401 || err.status === 403) &&
              (err.detail.includes('口令错误') ||
                err.detail.includes('已停用') ||
                err.detail.includes('已失效'))) ||
            (err instanceof Error &&
              (err.message.includes('口令错误') || err.message.includes('已停用')))

          if (isExplicitWrongAuth) {
            setStoredToken('')
            username.value = ''
            userId.value = ''
          }
          if (!authenticated.value) {
            modalVisible.value = true
          }
        }
      } else if (status.auth_required && !status.authenticated) {
        modalVisible.value = true
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
      username.value = res.username || (res.role === 'admin' ? '馆长' : '')
      userId.value = res.user_id || ''
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
      username.value = ''
      userId.value = ''
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
    username,
    userId,
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
