import { computed, ref } from 'vue'
import { useLocalStorage, StorageSerializers } from '@vueuse/core'
import {
  api,
  ApiError,
  getStoredToken,
  notifyAuthSuccess,
  onUnauthorized,
  setStoredToken,
} from '@/api/client'
import { useToast } from '@/composables/useToast'

const AUTH_PROFILE_STORAGE_KEY = 'comic-shelf:last-auth-profile'

export interface StoredAuthProfile {
  authRequired: boolean
  authenticated: boolean
  role: 'admin' | 'guest' | 'unauthorized'
  username: string
  userId: string
}

export const storedAuthProfile = useLocalStorage<StoredAuthProfile | null>(
  AUTH_PROFILE_STORAGE_KEY,
  null,
  {
    serializer: StorageSerializers.object,
  },
)

export function getStoredAuthProfile(): StoredAuthProfile | null {
  return storedAuthProfile.value
}

export function setStoredAuthProfile(profile: StoredAuthProfile | null): void {
  storedAuthProfile.value = profile
}

const initialProfile = getStoredAuthProfile()

const authRequired = ref(initialProfile?.authRequired ?? false)
const authenticated = ref(initialProfile?.authenticated ?? true)
const role = ref<'admin' | 'guest' | 'unauthorized'>(initialProfile?.role ?? 'admin')
const username = ref(initialProfile?.username ?? '')
const userId = ref(initialProfile?.userId ?? '')
const checking = ref(false)
const submitting = ref(false)
const errorMessage = ref('')
const requiresClaim = ref(false)
const requiresPin = ref(false)
const pendingToken = ref('')

function persistCurrentProfile(): void {
  setStoredAuthProfile({
    authRequired: authRequired.value,
    authenticated: authenticated.value,
    role: role.value,
    username: username.value,
    userId: userId.value,
  })
}

const PENDING_TOKEN_SESSION_KEY = 'comic-shelf:pending-token'

export function getSessionPendingToken(): string {
  try {
    return typeof window !== 'undefined'
      ? window.sessionStorage.getItem(PENDING_TOKEN_SESSION_KEY) || ''
      : ''
  } catch {
    return ''
  }
}

export function setSessionPendingToken(token: string): void {
  try {
    if (typeof window !== 'undefined') {
      if (token) {
        window.sessionStorage.setItem(PENDING_TOKEN_SESSION_KEY, token)
      } else {
        window.sessionStorage.removeItem(PENDING_TOKEN_SESSION_KEY)
      }
    }
  } catch {
    // Ignore storage quota or security errors
  }
}

const canWrite = computed(
  () => !authRequired.value || (authenticated.value && role.value === 'admin'),
)
const isGuest = computed(() => authenticated.value && role.value === 'guest')
const isDirectPass = computed(() => authenticated.value && userId.value.startsWith('direct:'))
const directPassComic = computed<{ source: string; sourceId: string } | null>(() => {
  if (!isDirectPass.value) return null
  const parts = userId.value.split(':')
  if (parts.length >= 3) {
    return { source: parts[1] || '', sourceId: parts[2] || '' }
  }
  return null
})

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
        setSessionPendingToken('')
        notifyAuthSuccess()
        persistCurrentProfile()
        return
      } else if (res.requires_pin) {
        pendingToken.value = stored
        setSessionPendingToken(stored)
        requiresPin.value = true
        requiresClaim.value = false
        username.value = res.username || ''
        authenticated.value = false
        role.value = 'unauthorized'
        persistCurrentProfile()
        return
      } else if (res.requires_claim) {
        pendingToken.value = stored
        setSessionPendingToken(stored)
        requiresClaim.value = true
        requiresPin.value = false
        username.value = res.username || ''
        authenticated.value = false
        role.value = 'unauthorized'
        persistCurrentProfile()
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
  persistCurrentProfile()
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
      persistCurrentProfile()

      // 0. 支持链接免密直达：若 URL Query 携带 ?token=... 或 ?temp_token=...，自动验证入馆
      let urlToken: string | null = null
      if (typeof window !== 'undefined') {
        const params = new URLSearchParams(window.location.search)
        urlToken = params.get('token') || params.get('temp_token')
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
            persistCurrentProfile()
          } else if (res.requires_claim) {
            pendingToken.value = urlToken
            setSessionPendingToken(urlToken)
            requiresClaim.value = true
            requiresPin.value = false
            username.value = res.username || ''
          } else if (res.requires_pin) {
            pendingToken.value = urlToken
            setSessionPendingToken(urlToken)
            requiresPin.value = true
            requiresClaim.value = false
            username.value = res.username || ''
          }

          // 清理地址栏 token / temp_token 参数，防止二次复制分享泄露口令
          const cleanUrl = new URL(window.location.href)
          cleanUrl.searchParams.delete('token')
          cleanUrl.searchParams.delete('temp_token')
          window.history.replaceState({}, '', cleanUrl.pathname + cleanUrl.search + cleanUrl.hash)
          if (res.ok) return true
        } catch (err: unknown) {
          setSessionPendingToken('')
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
              setSessionPendingToken('')
              notifyAuthSuccess()
              persistCurrentProfile()
              return true
            } else if (res.requires_claim) {
              pendingToken.value = stored
              setSessionPendingToken(stored)
              requiresClaim.value = true
              requiresPin.value = false
            } else if (res.requires_pin) {
              pendingToken.value = stored
              setSessionPendingToken(stored)
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
              persistCurrentProfile()
            }
          }
        }

        // Check if there is an in-flight pending pass token in sessionStorage (survives tab reload / mobile switch)
        const sessionPending = getSessionPendingToken()
        if (status.auth_required && !authenticated.value && sessionPending && !pendingToken.value) {
          try {
            const res = await api.login(sessionPending)
            if (res.ok) {
              setStoredToken(res.token)
              authenticated.value = true
              role.value = res.role || 'guest'
              username.value = res.username || (res.role === 'admin' ? '馆长' : '访客')
              userId.value = res.user_id || ''
              requiresClaim.value = false
              requiresPin.value = false
              pendingToken.value = ''
              setSessionPendingToken('')
              notifyAuthSuccess()
              persistCurrentProfile()
              return true
            } else if (res.requires_claim) {
              pendingToken.value = sessionPending
              requiresClaim.value = true
              requiresPin.value = false
              username.value = res.username || ''
            } else if (res.requires_pin) {
              pendingToken.value = sessionPending
              requiresPin.value = true
              requiresClaim.value = false
              username.value = res.username || ''
            } else {
              setSessionPendingToken('')
            }
          } catch {
            setSessionPendingToken('')
          }
        }
      }
    } catch {
      /* network or server offline */
      // 离线环境保持由 localStorage 还原的上次登录身份与本地权限
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
        setSessionPendingToken('')
        notifyAuthSuccess()
        persistCurrentProfile()
        return true
      } else if (res.requires_claim) {
        pendingToken.value = secret.trim()
        setSessionPendingToken(secret.trim())
        requiresClaim.value = true
        requiresPin.value = false
        username.value = res.username || ''
        errorMessage.value = ''
        return false
      } else if (res.requires_pin) {
        pendingToken.value = secret.trim()
        setSessionPendingToken(secret.trim())
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
    const sanitizedUsername = customUsername
      ? customUsername.replace(/[<>]/g, '').trim().slice(0, 20) || undefined
      : undefined
    try {
      const res = await api.claimPass({
        token: tokenToClaim,
        pin: pin.trim(),
        username: sanitizedUsername,
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
        setSessionPendingToken('')
        notifyAuthSuccess()
        persistCurrentProfile()
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
    setSessionPendingToken('')
    errorMessage.value = ''
  }

  async function logout(): Promise<void> {
    try {
      await api.logout()
    } finally {
      setStoredToken('')
      setSessionPendingToken('')
      authenticated.value = false
      role.value = 'unauthorized'
      username.value = ''
      userId.value = ''
      resetAuthFormState()
      persistCurrentProfile()
      toast('已退出入馆状态', 'info')
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
    isDirectPass,
    directPassComic,
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
