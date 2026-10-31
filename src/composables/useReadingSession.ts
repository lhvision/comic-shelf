/**
 * @file useReadingSession.ts
 * @description PWA 独立视口阅读会话跟踪与冷启动恢复组合式函数。
 *
 * 核心职责：
 * 1. 记录读者在阅读器内的活跃会话（作品来源、车号、当前页码、总页数与时间戳）；
 * 2. 区分「读者主动返回书架/详情」与「直接退出/杀后台」——主动离开时失活会话，直接退出时保留活跃态；
 * 3. 独立应用（Standalone PWA）冷启动时检测未完结的活跃会话，提供秒级接续直达与轻量反馈提示。
 */

import { watch } from 'vue'
import { StorageSerializers, useLocalStorage } from '@vueuse/core'
import type { Router } from 'vue-router'
import { useAuth } from '@/composables/useAuth'

export interface ActiveReadingSession {
  userId?: string
  source: string
  sourceId: string
  page: number
  totalPages: number
  updatedAt: number
  /** 是否处于阅读器内部中断（true 表示未通过返回按钮正常离开） */
  active: boolean
}

export const SESSION_KEY = 'comic-shelf:active-reading-session:v1'
export const RESUME_ON_LAUNCH_KEY = 'comic-shelf:resume-on-launch:v1'

/**
 * 归一化用户身份，统一馆长/个人模式缺省标识，并保持多租户/访客通行证严格隔离。
 */
export function normalizeSessionUid(uid?: string | null): string {
  const trimmed = (uid || '').trim()
  if (!trimmed || trimmed === 'default' || trimmed === 'curator') {
    return 'curator'
  }
  return trimmed
}

/**
 * 阅览室阅读会话管理组合式函数。
 *
 * 结合当前登录用户的 userId 进行隔离，杜绝跨访客/跨馆长会话污染与私密藏书泄漏。
 *
 * @returns 会话状态与恢复动作
 */
export function useReadingSession() {
  const { userId, authRequired, authenticated, isDirectPass, directPassComic } = useAuth()
  const session = useLocalStorage<ActiveReadingSession | null>(SESSION_KEY, null, {
    serializer: StorageSerializers.object,
  })
  const resumeOnLaunch = useLocalStorage<boolean>(RESUME_ON_LAUNCH_KEY, true)

  // 仅在真实发生账号切换（A -> B）或显式登出（A -> ""）时清理端侧会话；
  // 排除冷启动从初态空值水合为已登录身份（"" -> A）的正常初始化时序。
  watch(userId, (newUid, oldUid) => {
    if (oldUid && oldUid !== newUid) {
      clearSession()
    }
  })

  /**
   * 记录或更新当前阅读会话。
   *
   * @param data 会话数据载荷
   */
  function recordSession(data: {
    source: string
    sourceId: string
    page: number
    totalPages: number
  }): void {
    if (!data.source || !data.sourceId) return
    const page = Number.isFinite(data.page) ? Math.max(1, Math.floor(data.page)) : 1
    const totalPages =
      Number.isFinite(data.totalPages) && data.totalPages > 0 ? Math.floor(data.totalPages) : 0
    const isCompleted = totalPages > 0 && page >= totalPages
    session.value = {
      userId: normalizeSessionUid(userId.value),
      source: data.source,
      sourceId: data.sourceId,
      page,
      totalPages,
      updatedAt: Date.now(),
      active: !isCompleted,
    }
  }

  /**
   * 读者主动返回书架或详情页，失活当前会话（防下次冷启动误恢复）。
   */
  function deactivateSession(): void {
    if (session.value) {
      session.value = {
        ...session.value,
        active: false,
      }
    }
  }

  /**
   * 清空在读会话记录（如登出或手动重置）。
   */
  function clearSession(): void {
    session.value = null
  }

  /**
   * 尝试在冷启动时恢复在读会话。
   *
   * @param router 路由实例
   * @param showToast 可选的消息提示回调
   * @returns 是否成功触发了恢复导航
   */
  function tryResumeSession(
    router: Router,
    showToast?: (message: string, tone?: 'info' | 'error' | 'success') => void | number,
  ): boolean {
    if (!resumeOnLaunch.value) return false

    // 1. 全局鉴权守卫：若开启了全站认证且当前尚未登录，严禁向未授权访客恢复任何在读会话
    if (authRequired.value && !authenticated.value) return false

    const s = session.value
    if (!s || !s.active) return false
    if (!s.source || !s.sourceId) return false

    // 2. 单本沙箱守卫：若持有单本限定通行证，严禁恢复非该限定本的任何外部会话
    if (isDirectPass.value) {
      if (!directPassComic.value) return false
      if (
        s.source !== directPassComic.value.source ||
        s.sourceId !== directPassComic.value.sourceId
      ) {
        return false
      }
    }

    // 3. 租户/访客隔离：跨账号或访客登录时，禁止恢复前一用户的会话
    const currentUid = normalizeSessionUid(userId.value)
    const sessionUid = normalizeSessionUid(s.userId)
    if (sessionUid !== currentUid) return false

    if (s.totalPages > 0 && s.page >= s.totalPages) {
      deactivateSession()
      return false
    }

    const targetUrl = `/comic/${encodeURIComponent(s.source)}/${encodeURIComponent(s.sourceId)}/read/${s.page}`
    void router.replace(targetUrl)
    showToast?.(`已为您恢复上次在读：第 ${s.page} 页`, 'info')
    return true
  }

  return {
    session,
    resumeOnLaunch,
    recordSession,
    deactivateSession,
    clearSession,
    tryResumeSession,
  }
}
