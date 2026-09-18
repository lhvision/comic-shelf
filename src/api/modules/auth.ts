/**
 * @file auth.ts
 * @description 身份认证与权限状态领域 API 模块（Authentication & Authorization Module）。
 *
 * 职责：
 * 1. 提供服务健康探测与鉴权需求检查；
 * 2. 处理馆长主密码登录、访客通行证认领、会话注销；
 * 3. 获取当前会话权限状态与角色识别。
 */

import { request, type RequestOptions } from '../core/http'
import type {
  AuthStatus,
  ClaimGuestPassPayload,
  DirectPassPayload,
  DirectPassResponse,
  LoginResult,
} from '@/types'

/**
 * 探测后端服务健康状态及是否开启了鉴权保护
 *
 * @param options 可选的请求配置（如取消信号、超时等）
 * @returns 包含 `ok: boolean` 与 `auth_required?: boolean` 的健康响应
 */
export async function health(
  options?: RequestOptions,
): Promise<{ ok: boolean; auth_required?: boolean }> {
  return request<{ ok: boolean; auth_required?: boolean }>('/health', {
    signal: options?.signal,
  })
}

/**
 * 获取当前登录用户的权限与角色状态
 *
 * @param options 可选的请求配置
 * @returns 当前认证状态对象（含 role, expires_at, authenticated 等）
 */
export async function authStatus(options?: RequestOptions): Promise<AuthStatus> {
  return request<AuthStatus>('/auth/status', {
    signal: options?.signal,
  })
}

/**
 * 提交馆长主密码或访客凭证以完成登录鉴权
 *
 * @param secret 馆长主密码或通行证 Token
 * @param pin 可选的二级 PIN 码
 * @param username 可选的用户名
 * @returns 登录结果，包含签发的 JWT Token 及角色信息
 */
export async function login(secret: string, pin?: string, username?: string): Promise<LoginResult> {
  return request<LoginResult>('/auth/login', {
    method: 'POST',
    body: JSON.stringify({ secret, pin, username }),
  })
}

/**
 * 认领并激活指定的访客通行证
 *
 * @param payload 通行证认领载荷（含 pass_code / pass_id 等）
 * @returns 登录结果，包含已鉴权的访客会话凭证
 */
export async function claimPass(payload: ClaimGuestPassPayload): Promise<LoginResult> {
  return request<LoginResult>('/auth/claim', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

/**
 * 注销当前登录会话
 *
 * @returns 操作结果 `{ ok: boolean }`
 */
export async function logout(): Promise<{ ok: boolean }> {
  return request<{ ok: boolean }>('/auth/logout', {
    method: 'POST',
  })
}

/**
 * 签发单本沙箱临时直达阅读通行证（Single-Book Sandbox）
 *
 * @param payload 单本直达通行证载荷（包含 source, source_id, page_index, ttl_seconds）
 * @param options 可选的请求配置
 * @returns 签发的临时直达凭证与直达 URL
 */
export async function createDirectPass(
  payload: DirectPassPayload,
  options?: RequestOptions,
): Promise<DirectPassResponse> {
  return request<DirectPassResponse>(
    '/auth/direct-pass',
    {
      method: 'POST',
      body: JSON.stringify(payload),
      signal: options?.signal,
    },
    options,
  )
}
