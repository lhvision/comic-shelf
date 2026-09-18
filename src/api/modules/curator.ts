/**
 * @file curator.ts
 * @description 馆长通行证管理与访客设备解绑 API 模块（Curator Pass Management Module）。
 *
 * 职责：
 * 1. 查询当前所有已签发的访客通行证列表；
 * 2. 签发全新通行证（设定有效期、可用额度及访问范围）；
 * 3. 调整通行证配置或作废通行证；
 * 4. 解绑指定通行证下已绑定的终端设备。
 */

import { request, type RequestOptions } from '../core/http'
import type { CreateGuestPassPayload, GuestPass, UpdateGuestPassPayload } from '@/types'

/**
 * 获取全站所有由馆长签发的访客通行证列表
 *
 * @param options 可选的请求配置
 * @returns 访客通行证数组（包含使用统计与关联设备信息）
 */
export async function getCuratorPasses(options?: RequestOptions): Promise<GuestPass[]> {
  return request<GuestPass[]>('/curator/passes', {
    signal: options?.signal,
  })
}

/**
 * 签发一张全新的访客通行证
 *
 * @param payload 通行证创建载荷（有效期、名称、权限备注等）
 * @param options 可选的请求配置
 * @returns 创建成功的通行证对象
 */
export async function createCuratorPass(
  payload: CreateGuestPassPayload,
  options?: RequestOptions,
): Promise<GuestPass> {
  return request<GuestPass>('/curator/passes', {
    method: 'POST',
    body: JSON.stringify(payload),
    signal: options?.signal,
  })
}

/**
 * 更新或调整已有访客通行证的信息或有效状态
 *
 * @param passId 目标通行证数字 ID
 * @param payload 待更新的载荷
 * @param options 可选的请求配置
 * @returns 更新后的通行证对象
 */
export async function updateCuratorPass(
  passId: number,
  payload: UpdateGuestPassPayload,
  options?: RequestOptions,
): Promise<GuestPass> {
  return request<GuestPass>(`/curator/passes/${passId}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
    signal: options?.signal,
  })
}

/**
 * 撤销并永久删除指定的访客通行证
 *
 * @param passId 目标通行证数字 ID
 * @param options 可选的请求配置
 * @returns 操作结果 `{ ok: boolean }`
 */
export async function deleteCuratorPass(
  passId: number,
  options?: RequestOptions,
): Promise<{ ok: boolean }> {
  return request<{ ok: boolean }>(`/curator/passes/${passId}`, {
    method: 'DELETE',
    signal: options?.signal,
  })
}

/**
 * 解绑指定通行证下绑定的特定访客设备（使其需要重新认证）
 *
 * @param passId 目标通行证数字 ID
 * @param deviceId 目标设备数字 ID
 * @param options 可选的请求配置
 * @returns 操作结果 `{ ok: boolean }`
 */
export async function deleteCuratorPassDevice(
  passId: number,
  deviceId: number,
  options?: RequestOptions,
): Promise<{ ok: boolean }> {
  return request<{ ok: boolean }>(`/curator/passes/${passId}/devices/${deviceId}`, {
    method: 'DELETE',
    signal: options?.signal,
  })
}
