import { describe, it, expect } from 'vite-plus/test'
import { formatDirectLink } from '@/utils/url'

describe('formatDirectLink', () => {
  it('strips redundant trailing slash before query in root URLs', () => {
    expect(formatDirectLink('http://127.0.0.1:8000', 'guest-secret-456')).toBe(
      'http://127.0.0.1:8000?token=guest-secret-456',
    )
    expect(formatDirectLink('http://127.0.0.1:8000/', 'guest-secret-456')).toBe(
      'http://127.0.0.1:8000?token=guest-secret-456',
    )
    expect(formatDirectLink('https://shelf.moe:8443/', 'secure-token')).toBe(
      'https://shelf.moe:8443?token=secure-token',
    )
  })

  it('supports URL object as input', () => {
    const url = new URL('http://localhost:5173/')
    expect(formatDirectLink(url, 'my-token')).toBe('http://localhost:5173?token=my-token')
  })

  it('preserves deep routing paths and cleans hash fragments', () => {
    const readerUrl = 'https://shelf.moe/comic/jm/12345/read/5#page-5'
    expect(formatDirectLink(readerUrl, 'guest-token')).toBe(
      'https://shelf.moe/comic/jm/12345/read/5?token=guest-token',
    )
  })

  it('overwrites existing token and preserves other query parameters', () => {
    const urlWithParams = 'http://127.0.0.1:8000/?from=share&token=old-token'
    expect(formatDirectLink(urlWithParams, 'new-token')).toBe(
      'http://127.0.0.1:8000?from=share&token=new-token',
    )
  })

  it('handles subpath deployment base correctly', () => {
    const subpathUrl = new URL('/shelf/', 'http://127.0.0.1:8000')
    expect(formatDirectLink(subpathUrl, 'sub-token')).toBe(
      'http://127.0.0.1:8000/shelf/?token=sub-token',
    )
  })

  it('handles relative path string gracefully by falling back to origin', () => {
    expect(formatDirectLink('/comic/jm/123/read/1', 'tok')).toBe(
      'http://localhost:3000/comic/jm/123/read/1?token=tok',
    )
  })

  it('rejects unsupported protocols to prevent XSS injection', () => {
    expect(() => formatDirectLink('javascript:alert(1)', 'tok')).toThrow(TypeError)
    expect(() => formatDirectLink('data:text/html,<script>', 'tok')).toThrow(TypeError)
  })
})
