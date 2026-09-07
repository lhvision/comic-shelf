/**
 * @file url.ts
 * @description URL 格式化与直达链接构造工具函数。
 */

/**
 * 构造免密或跨端专属直达链接。
 *
 * 若目标 URL 在根路径直接拼接查询参数（形如 `https://example.com/?token=xxx`），
 * 自动剥离根路径多余的斜杠美化为 `https://example.com?token=xxx`，避免视觉冗余与拼写不适感。
 * 同时保留深层路由路径（如 `/comic/.../read/1?token=xxx`）与非根路径结构。
 *
 * @param base 基础 URL 或当前 location（支持 string 或 URL 对象）
 * @param token 访客口令或通行证凭据
 * @returns 美化后的免密直达链接字符串
 */
export function formatDirectLink(base: string | URL, token: string): string {
  const origin = typeof window !== 'undefined' ? window.location.origin : 'http://localhost'
  const url = typeof base === 'string' ? new URL(base, origin) : new URL(base.toString())
  if (url.protocol !== 'http:' && url.protocol !== 'https:') {
    throw new TypeError(`不支持的直达链接协议: ${url.protocol}`)
  }
  url.searchParams.set('token', token)
  url.hash = ''
  return url.toString().replace(`${url.origin}/?`, `${url.origin}?`)
}
