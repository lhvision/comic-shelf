import { ref } from 'vue'
import { useClipboard } from '@vueuse/core'
import { api } from '@/api/client'
import { useToast } from '@/composables/useToast'
import type { CreateGuestPassPayload, GuestPass, UpdateGuestPassPayload } from '@/types'

const passes = ref<GuestPass[]>([])
const loading = ref(false)
const operatingId = ref<number | null>(null)
const fetchError = ref<string | null>(null)
const modalVisible = ref(false)

export function useGuestPasses() {
  const { copy } = useClipboard()
  const { toast } = useToast()

  async function fetchPasses() {
    loading.value = true
    fetchError.value = null
    try {
      passes.value = await api.getCuratorPasses()
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : '获取访客通行证列表失败'
      fetchError.value = msg
      toast(msg, 'error')
    } finally {
      loading.value = false
    }
  }

  async function createPass(payload: CreateGuestPassPayload): Promise<GuestPass | null> {
    try {
      const newPass = await api.createCuratorPass(payload)
      passes.value.unshift(newPass)
      toast(`已为「${newPass.username}」印发通行证`, 'success')
      return newPass
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : '派发失败'
      toast(msg, 'error')
      return null
    }
  }

  async function updatePass(passId: number, payload: UpdateGuestPassPayload): Promise<boolean> {
    if (operatingId.value !== null) return false
    operatingId.value = passId
    try {
      const updated = await api.updateCuratorPass(passId, payload)
      const idx = passes.value.findIndex((p) => p.id === passId)
      if (idx !== -1) {
        passes.value[idx] = updated
      }
      return true
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : '更新通行证失败'
      toast(msg, 'error')
      return false
    } finally {
      operatingId.value = null
    }
  }

  async function renewPass(passId: number, days = 30): Promise<void> {
    const ok = await updatePass(passId, { extend_days: days })
    if (ok) {
      toast(`已成功续期 ${days} 天`, 'success')
    }
  }

  async function resetToken(passId: number): Promise<void> {
    const ok = await updatePass(passId, { reset_token: true })
    if (ok) {
      toast('密钥已重置，旧口令已失效', 'success')
    }
  }

  async function toggleActive(passId: number, active: boolean): Promise<void> {
    const ok = await updatePass(passId, { is_active: active })
    if (ok) {
      toast(active ? '通行证已重新启用' : '通行证已停用', 'info')
    }
  }

  async function removePass(passId: number): Promise<void> {
    if (operatingId.value !== null) return
    operatingId.value = passId
    try {
      await api.deleteCuratorPass(passId)
      passes.value = passes.value.filter((p) => p.id !== passId)
      toast('已注销该访客通行证', 'info')
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : '注销失败'
      toast(msg, 'error')
    } finally {
      operatingId.value = null
    }
  }

  async function copyToken(token: string): Promise<boolean> {
    try {
      await copy(token)
      toast('通行口令已复制到剪贴板', 'success')
      return true
    } catch {
      toast('复制失败，请手动长按或选中复制', 'error')
      return false
    }
  }

  async function copyShareLink(token: string): Promise<boolean> {
    try {
      const url = new URL(window.location.origin)
      url.searchParams.set('token', token)
      await copy(url.toString())
      toast('直达链接已复制，朋友打开即可免密入馆', 'success')
      return true
    } catch {
      toast('复制失败，请手动长按或选中复制', 'error')
      return false
    }
  }

  function openModal() {
    modalVisible.value = true
    void fetchPasses()
  }

  function closeModal() {
    modalVisible.value = false
  }

  return {
    passes,
    loading,
    operatingId,
    fetchError,
    modalVisible,
    fetchPasses,
    createPass,
    renewPass,
    resetToken,
    toggleActive,
    removePass,
    copyToken,
    copyShareLink,
    openModal,
    closeModal,
  }
}
