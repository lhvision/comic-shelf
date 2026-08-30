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

  async function removeDevice(passId: number, deviceId: number): Promise<boolean> {
    if (operatingId.value !== null) return false
    operatingId.value = passId
    try {
      await api.deleteCuratorPassDevice(passId, deviceId)
      const pass = passes.value.find((p) => p.id === passId)
      if (pass && pass.devices) {
        pass.devices = pass.devices.filter((d) => d.id !== deviceId)
        pass.device_count = pass.devices.length
        if (pass.device_count === 0) {
          pass.activation_status = 'pending'
        } else if (pass.device_count >= pass.max_devices) {
          pass.activation_status = 'full'
        } else {
          pass.activation_status = 'active'
        }
      }
      toast('已移除该设备，该端已被踢下线', 'info')
      return true
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : '移除设备失败'
      toast(msg, 'error')
      return false
    } finally {
      operatingId.value = null
    }
  }

  async function updateMaxDevices(passId: number, maxDevices: number): Promise<boolean> {
    const ok = await updatePass(passId, { max_devices: maxDevices })
    if (ok) {
      toast(`已将设备配额调整为 ${maxDevices} 台`, 'success')
    }
    return ok
  }

  async function copyToken(target: GuestPass | string): Promise<boolean> {
    const token = typeof target === 'string' ? target : target.token
    const deviceCount = typeof target === 'string' ? 0 : target.device_count || 0
    try {
      await copy(token)
      if (deviceCount > 0) {
        toast(`⚠️ 口令已复制。该通行证已有 ${deviceCount} 台设备在使用中，谨防设备互挤`, 'info')
      } else {
        toast('通行口令已复制，可安心发放给新朋友', 'success')
      }
      return true
    } catch {
      toast('复制失败，请手动长按或选中复制', 'error')
      return false
    }
  }

  async function copyShareLink(target: GuestPass | string): Promise<boolean> {
    const token = typeof target === 'string' ? target : target.token
    const deviceCount = typeof target === 'string' ? 0 : target.device_count || 0
    try {
      const url = new URL(window.location.origin)
      url.searchParams.set('token', token)
      await copy(url.toString())
      if (deviceCount > 0) {
        toast(`⚠️ 直达链接已复制。该通行证已有 ${deviceCount} 台设备在使用中，谨防设备互挤`, 'info')
      } else {
        toast('专属直达链接已复制，朋友打开即可免密入馆', 'success')
      }
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
    removeDevice,
    updateMaxDevices,
    copyToken,
    copyShareLink,
    openModal,
    closeModal,
  }
}
