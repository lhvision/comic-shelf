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
const checking = ref(false)
const submitting = ref(false)
const errorMessage = ref('')
const requiresClaim = ref(false)
const requiresPin = ref(false)
const pendingToken = ref('')

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
      if (res.ok) {
        authenticated.value = true
        role.value = res.role || 'admin'
        username.value = res.username || (res.role === 'admin' ? '馆长' : '访客')
        userId.value = res.user_id || ''
        requiresClaim.value = false
        requiresPin.value = false
        pendingToken.value = ''
        notifyAuthSuccess()
        return
      }
    } catch {
      // Re-authentication failed, proceed to unauthorized state
    } finally {
      isReauthenticating = false
    }
  }

  authenticated.value = false
  role.value = 'unauthorized'
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
          if (res.ok) {
            setStoredToken(urlToken)
            authenticated.value = true
            role.value = res.role || 'guest'
            username.value = res.username || (res.role === 'admin' ? '馆长' : '访客')
            userId.value = res.user_id || ''
            requiresClaim.value = false
            requiresPin.value = false
            pendingToken.value = ''
            notifyAuthSuccess()
          } else if (res.requires_claim) {
            pendingToken.value = urlToken
            requiresClaim.value = true
            requiresPin.value = false
            username.value = res.username || ''
          } else if (res.requires_pin) {
            pendingToken.value = urlToken
            requiresPin.value = true
            requiresClaim.value = false
            username.value = res.username || ''
          }

          // 清理地址栏 token 参数，防止二次复制分享泄露口令
          const cleanUrl = new URL(window.location.href)
          cleanUrl.searchParams.delete('token')
          window.history.replaceState({}, '', cleanUrl.pathname + cleanUrl.search + cleanUrl.hash)
          if (res.ok) return true
        } catch (err: unknown) {
          const msg =
            err instanceof Error ? err.message : '该直达通行证已失效或过期，请向馆长申请新凭证'
          toast(msg, 'error')
          const cleanUrl = new URL(window.location.href)
          cleanUrl.searchParams.delete('token')
          window.history.replaceState({}, '', cleanUrl.pathname + cleanUrl.search + cleanUrl.hash)
        }
      } else {
        // If auth is required, check if we have a stored token to restore curator privileges
        const stored = getStoredToken()
        if (status.auth_required && stored && (!status.authenticated || role.value !== 'admin')) {
          try {
            const res = await api.login(stored)
            if (res.ok) {
              authenticated.value = true
              role.value = res.role || 'admin'
              username.value = res.username || (res.role === 'admin' ? '馆长' : '')
              userId.value = res.user_id || ''
              requiresClaim.value = false
              requiresPin.value = false
              pendingToken.value = ''
              notifyAuthSuccess()
              return true
            } else if (res.requires_claim) {
              pendingToken.value = stored
              requiresClaim.value = true
              requiresPin.value = false
            } else if (res.requires_pin) {
              pendingToken.value = stored
              requiresPin.value = true
              requiresClaim.value = false
            }
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
          }
        }
      }
    } catch {
      /* network or server offline */
    } finally {
      checking.value = false
    }
    return authenticated.value
  }

  async function login(secret: string, pin?: string): Promise<boolean> {
    if (!secret.trim()) {
      errorMessage.value = '请输入通行口令'
      return false
    }
    submitting.value = true
    errorMessage.value = ''
    try {
      const res = await api.login(secret.trim(), pin?.trim())
      if (res.ok) {
        setStoredToken(res.token)
        authenticated.value = true
        role.value = res.role || 'admin'
        username.value = res.username || (res.role === 'admin' ? '馆长' : '访客')
        userId.value = res.user_id || ''
        requiresClaim.value = false
        requiresPin.value = false
        pendingToken.value = ''
        notifyAuthSuccess()
        return true
      } else if (res.requires_claim) {
        pendingToken.value = secret.trim()
        requiresClaim.value = true
        requiresPin.value = false
        username.value = res.username || ''
        errorMessage.value = ''
        return false
      } else if (res.requires_pin) {
        pendingToken.value = secret.trim()
        requiresPin.value = true
        requiresClaim.value = false
        username.value = res.username || ''
        errorMessage.value = ''
        return false
      }
      return false
    } catch (err: unknown) {
      errorMessage.value = err instanceof Error ? err.message : '通行口令错误'
      return false
    } finally {
      submitting.value = false
    }
  }

  async function claimPass(pin: string, customUsername?: string): Promise<boolean> {
    const tokenToClaim = pendingToken.value.trim()
    if (!tokenToClaim) {
      errorMessage.value = '通行凭证缺失，请重新输入口令'
      return false
    }
    if (!pin.trim() || !/^\d{4,6}$/.test(pin.trim())) {
      errorMessage.value = 'PIN 码必须为 4~6 位纯数字'
      return false
    }
    submitting.value = true
    errorMessage.value = ''
    try {
      const res = await api.claimPass({
        token: tokenToClaim,
        pin: pin.trim(),
        username: customUsername?.trim() || undefined,
      })
      if (res.ok) {
        setStoredToken(res.token)
        authenticated.value = true
        role.value = 'guest'
        username.value = res.username || '访客'
        userId.value = res.user_id || ''
        requiresClaim.value = false
        requiresPin.value = false
        pendingToken.value = ''
        notifyAuthSuccess()
        toast('借阅通行证认领成功！欢迎入馆', 'success')
        return true
      }
      return false
    } catch (err: unknown) {
      errorMessage.value = err instanceof Error ? err.message : '认领失败，请重试'
      return false
    } finally {
      submitting.value = false
    }
  }

  function resetAuthFormState() {
    requiresClaim.value = false
    requiresPin.value = false
    pendingToken.value = ''
    errorMessage.value = ''
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
      resetAuthFormState()
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
    checking,
    submitting,
    errorMessage,
    requiresClaim,
    requiresPin,
    pendingToken,
    checkStatus,
    login,
    claimPass,
    resetAuthFormState,
    logout,
    getStoredToken,
  }
}
