/**
 * 纸间 · Paper Room Chrome 扩展后台服务
 * 实现三大图源（禁漫、哔咔、拷贝）右键双模收录、智能图标直达与状态静默反馈
 */
import { DEFAULT_DOMAINS, sanitizeDomain } from './constants.js'

const IN_FLIGHT_SET = new Set()

/**
 * 校验 URL 协议安全性（严格限定 http/https，防范 javascript:/file: 注入）
 */
function isSafeUrl(raw) {
  if (!raw || typeof raw !== 'string') return false
  try {
    const u = new URL(raw)
    return u.protocol === 'http:' || u.protocol === 'https:'
  } catch {
    return false
  }
}

/**
 * 从 URL 解析出图源、车号与站点名称
 */
function resolveComicInfo(rawUrl) {
  if (!rawUrl || typeof rawUrl !== 'string') return null
  try {
    const u = new URL(rawUrl)
    const pathname = u.pathname
    const hash = u.hash || ''

    // 1. 禁漫天堂：/album/<数字车号>（单话 /photo/ 为分卷 ID，必须解析为相册后方可入库）
    const jm = pathname.match(/\/album\/(\d{3,10})/) || hash.match(/\/album\/(\d{3,10})/)
    if (jm) return { source: 'jm', id: jm[1], name: '禁漫天堂' }

    // 2. 哔咔漫画：/(comic|comics)/<24位Hex>
    const pica =
      pathname.match(/\/(?:comic|comics)\/([0-9a-fA-F]{24})/) ||
      hash.match(/\/(?:comic|comics)\/([0-9a-fA-F]{24})/)
    if (pica) return { source: 'picacg', id: pica[1].toLowerCase(), name: '哔咔漫画' }

    // 3. 拷贝漫画：/comic/<slug>
    const copy =
      pathname.match(/\/comic\/([a-zA-Z0-9_\-.]+)/) || hash.match(/\/comic\/([a-zA-Z0-9_\-.]+)/)
    if (copy) return { source: 'copymanga', id: copy[1], name: '拷贝漫画' }

    return null
  } catch {
    return null
  }
}

/**
 * 禁漫单话阅读页探测整部作品相册链接
 */
async function extractJmAlbumUrl(tabId) {
  try {
    const [res] = await chrome.scripting.executeScript({
      target: { tabId },
      func: () => {
        // 1. 优先寻找返回相册链接或目录链接 (如 /album/12345)
        const links = document.querySelectorAll('a[href*="/album/"]')
        for (const a of links) {
          const href = a.getAttribute('href') || ''
          const m = href.match(/\/album\/(\d{3,10})/)
          if (m) return `${window.location.origin}/album/${m[1]}`
        }
        // 2. 从页面内嵌的 script 标签文本中提取 series_id 或 album_id (适配 isolated world 隔离域)
        const scripts = document.querySelectorAll('script')
        for (const s of scripts) {
          const text = s.textContent || ''
          const m = text.match(/(?:series_id|album_id)\s*=\s*['"]?(\d{3,10})['"]?/)
          if (m) return `${window.location.origin}/album/${m[1]}`
        }
        return null
      },
    })
    return res?.result || null
  } catch {
    return null
  }
}

/**
 * 探测指定 Tab 上的漫画信息（支持相册页及 JM 单话阅读页智能提取）
 */
async function detectComicFromTab(tab) {
  const currentUrl = tab?.url || tab?.pendingUrl
  if (!currentUrl || !isSafeUrl(currentUrl)) return null

  let targetUrl = currentUrl
  if (targetUrl.includes('/photo/') && tab.id) {
    const albumUrl = await extractJmAlbumUrl(tab.id)
    if (albumUrl) {
      targetUrl = albumUrl
    }
  }

  // 若仍为 /photo/ 单话阅读页且未提取到相册，返回无法提取相册标记
  if (/\/photo\/\d+/.test(targetUrl) && !/\/album\/\d+/.test(targetUrl)) {
    return { error: 'jm_photo_unresolved' }
  }

  const comic = resolveComicInfo(targetUrl)
  return comic ? { comic } : null
}

function parseBool(val, defaultValue = true) {
  if (val === false || val === 'false' || val === 0 || val === '0') return false
  if (val === true || val === 'true' || val === 1 || val === '1') return true
  return defaultValue
}

/**
 * 获取保存的配置（使用 storage.local 本地隔离存储，严禁敏感口令随 Google 账户同步上云）
 */
async function getConfig() {
  const data = await chrome.storage.local.get({
    serverUrl: 'http://localhost:8000',
    token: '',
    enableNotifications: true,
  })
  const serverUrl = (data.serverUrl || 'http://localhost:8000').trim().replace(/\/+$/, '')
  return {
    serverUrl,
    token: (data.token || '').trim(),
    enableNotifications: parseBool(data.enableNotifications, true),
  }
}

/**
 * 设置工具栏图标 Badge 短提示
 */
function setBadge(text, color) {
  try {
    chrome.action.setBadgeText({ text })
    if (color) {
      chrome.action.setBadgeBackgroundColor({ color })
    }
    setTimeout(() => {
      chrome.action.setBadgeText({ text: '' })
    }, 4000)
  } catch {
    // 忽略在无法设置 badge 时的异常
  }
}

/**
 * 弹出系统通知并在点击时直达对应地址（受用户选项开关控制，并持久化至 storage 抗 SW 休眠）
 */
async function showNotification(title, message, targetUrl = null) {
  const { enableNotifications } = await getConfig()
  if (!enableNotifications) return

  const notifId = `paper-room-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`
  if (targetUrl && isSafeUrl(targetUrl)) {
    await chrome.storage.local.set({ [`notif_${notifId}`]: targetUrl })
  }

  chrome.notifications.create(notifId, {
    type: 'basic',
    iconUrl: 'icons/icon-128.png',
    title,
    message,
    priority: 1,
  })
}

function buildUrlPatterns(domains) {
  const patterns = []
  for (const d of domains) {
    if (!d || typeof d !== 'string') continue
    const clean = sanitizeDomain(d)
    if (!clean) continue

    // 区分 IPv4 地址与标准域名
    const isIp = /^(\d{1,3}\.){3}\d{1,3}$/.test(clean)
    if (isIp) {
      patterns.push(`*://${clean}/*`)
    } else if (/^[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/.test(clean) || clean === 'localhost') {
      patterns.push(`*://*.${clean}/*`)
    }
  }
  return [...new Set(patterns)]
}

/**
 * 仅在漫画图源站点注册右键菜单，非漫画网站绝不显示
 */
async function registerContextMenu() {
  const data = await chrome.storage.local.get({ customDomains: [] })
  const customList = Array.isArray(data.customDomains) ? data.customDomains : []
  const allDomains = [...DEFAULT_DOMAINS, ...customList]
  let documentUrlPatterns = buildUrlPatterns(allDomains)
  if (documentUrlPatterns.length === 0) {
    documentUrlPatterns = buildUrlPatterns(DEFAULT_DOMAINS)
  }

  chrome.contextMenus.removeAll(() => {
    chrome.contextMenus.create(
      {
        id: 'paper-room-import-item',
        title: '收录至纸间',
        contexts: ['link', 'page'],
        documentUrlPatterns,
      },
      () => {
        if (chrome.runtime.lastError) {
          console.warn('注册右键菜单失败，回退默认规则:', chrome.runtime.lastError)
          const fallbackPatterns = buildUrlPatterns(DEFAULT_DOMAINS)
          chrome.contextMenus.create({
            id: 'paper-room-import-item',
            title: '收录至纸间',
            contexts: ['link', 'page'],
            documentUrlPatterns: fallbackPatterns,
          })
        }
      },
    )
  })
}

/**
 * 清理本地存储中超时的通知 ID 映射
 */
async function pruneStaleNotifications() {
  try {
    const all = await chrome.storage.local.get(null)
    const keysToRemove = Object.keys(all).filter((k) => k.startsWith('notif_'))
    if (keysToRemove.length > 0) {
      await chrome.storage.local.remove(keysToRemove)
    }
  } catch {
    // 忽略清理异常
  }
}

/**
 * 执行漫画收录操作并反馈状态与跳转目标
 * @param {{ source: string, id: string, name: string }} comic
 * @param {{ openTab?: boolean, silent?: boolean }} options
 * @returns {Promise<{ ok: boolean, detailUrl?: string, fromCache?: boolean }>}
 */
async function importComic(comic, { openTab = false, silent = false } = {}) {
  // 防重入与并发风暴防护：如果同一漫画正在收录中，阻断重复请求
  const inFlightKey = `${comic.source}:${comic.id}`
  if (IN_FLIGHT_SET.has(inFlightKey)) {
    if (!silent) {
      setBadge('...', '#d97706')
      await showNotification(
        '正在收录中',
        `《${comic.name}》车号 ${comic.id} 正在处理中，请勿重复点击。`,
      )
    }
    return { ok: false }
  }
  IN_FLIGHT_SET.add(inFlightKey)

  const { serverUrl, token } = await getConfig()
  if (!silent) {
    setBadge('...', '#766e62')
  }

  try {
    const headers = { 'Content-Type': 'application/json' }
    if (token) {
      headers['X-Auth-Token'] = token
      headers['Authorization'] = `Bearer ${token}`
    }

    const controller = new AbortController()
    const timeoutId = setTimeout(() => controller.abort(), 60000)

    const response = await fetch(`${serverUrl}/api/library/import`, {
      method: 'POST',
      headers,
      body: JSON.stringify({
        id: comic.id,
        source: comic.source,
        prefetch_covers: 4,
        prefetch_all: false,
        refresh: false,
      }),
      signal: controller.signal,
    })
    clearTimeout(timeoutId)

    if (response.status === 401 || response.status === 403) {
      if (!silent) {
        setBadge('AUTH', '#e5484d')
        await showNotification(
          '纸间访问认证失败',
          '馆长口令未配置或无效。右键点击插件图标选择「选项」配置正确口令。',
        )
      }
      chrome.runtime.openOptionsPage()
      return { ok: false }
    }

    if (!response.ok) {
      let detailMsg = response.statusText || `HTTP ${response.status}`
      try {
        const errJson = await response.json()
        if (errJson && errJson.detail) {
          detailMsg =
            typeof errJson.detail === 'string' ? errJson.detail : JSON.stringify(errJson.detail)
        }
      } catch {
        // 无法解析 JSON 错误，保留默认状态文本
      }
      if (!silent) {
        setBadge('ERR', '#e5484d')
        await showNotification('收录失败', `[${comic.name}] ${detailMsg}`)
      }
      return { ok: false }
    }

    const result = await response.json()
    const title = result.meta?.title || comic.id
    const sourceId = result.meta?.source_id || comic.id
    const detailUrl = `${serverUrl}/comic/${comic.source}/${sourceId}`

    if (!silent) {
      if (result.from_cache) {
        setBadge('已在', '#d97706')
        await showNotification(
          '该漫画已在书库中',
          `《${title}》\n已收藏于纸间，点击立即前往阅读`,
          detailUrl,
        )
      } else {
        setBadge('✓', '#3f6d4e')
        await showNotification(
          '收录成功',
          `《${title}》\n已纳进书库并在后台就绪，点击立即阅读`,
          detailUrl,
        )
      }
    }

    if (openTab && isSafeUrl(detailUrl)) {
      chrome.tabs.create({ url: detailUrl })
    }

    return { ok: true, detailUrl, fromCache: Boolean(result.from_cache) }
  } catch (error) {
    if (!silent) {
      setBadge('ERR', '#e5484d')
      const isTimeout = error.name === 'AbortError'
      const msg = isTimeout
        ? '请求超时（60s），请检查网络或纸间服务响应'
        : `无法连接到纸间服务（${serverUrl}），请检查服务是否启动。`
      await showNotification('连接纸间失败', msg)
    }
    return { ok: false }
  } finally {
    IN_FLIGHT_SET.delete(inFlightKey)
  }
}

if (typeof chrome !== 'undefined' && chrome?.runtime) {
  // 扩展安装或更新时注册
  chrome.runtime.onInstalled.addListener(() => {
    void registerContextMenu()
  })

  // 浏览器冷启动时防丢容灾并清理陈旧通知
  chrome.runtime.onStartup.addListener(() => {
    void registerContextMenu()
    void pruneStaleNotifications()
  })

  // 配置中的自定义域名变化时实时动态刷新菜单匹配规则
  chrome.storage.onChanged.addListener((changes, area) => {
    if (area === 'local' && changes.customDomains) {
      void registerContextMenu()
    }
  })

  // 点击扩展图标根据当前上下文智能跳转
  chrome.action.onClicked.addListener(async (tab) => {
    let currentTab = tab

    // 1. 若 tab 或 tab.url 缺失，主动通过 chrome.tabs.get / query 容灾获取
    if (!currentTab?.url && currentTab?.id) {
      try {
        currentTab = await chrome.tabs.get(currentTab.id)
      } catch (err) {
        console.warn('[Paper Room] 获取 Tab 详情异常:', err)
      }
    }
    if (!currentTab?.url) {
      try {
        const [active] = await chrome.tabs.query({ active: true, currentWindow: true })
        if (active) currentTab = active
      } catch (err) {
        console.warn('[Paper Room] 查询当前活动 Tab 异常:', err)
      }
    }

    const { serverUrl } = await getConfig()
    if (!isSafeUrl(serverUrl)) {
      chrome.runtime.openOptionsPage()
      return
    }

    // 2. 若当前在支持的外部漫画页面（禁漫、哔咔、拷贝），一键收录并直达纸间详情页
    const detection = await detectComicFromTab(currentTab)
    if (detection?.error === 'jm_photo_unresolved') {
      setBadge('!', '#e5484d')
      await showNotification(
        '无法识别相册车号',
        '禁漫单话阅读链接无法直接入库，请在相册主页点击扩展图标。',
      )
      return
    }

    if (detection?.comic) {
      const { comic } = detection
      const detailUrl = `${serverUrl}/comic/${comic.source}/${comic.id}`
      // 立即直达纸间本子详情页（解决系统通知拦截/只有声音无法点击直达的痛点）
      if (isSafeUrl(detailUrl)) {
        chrome.tabs.create({ url: detailUrl })
      }
      // 后台静默预热作品（纯页面跳转交互，绝不显示「已在」或「✓」等入库角标与通知，避免用户误解）
      void importComic(comic, { openTab: false, silent: true })
      return
    }

    // 4. 常规网页上下文：直达纸间书架主站
    chrome.tabs.create({ url: serverUrl })
  })

  // 点击系统通知直达对应漫画阅读详情页
  chrome.notifications.onClicked.addListener(async (notificationId) => {
    const key = `notif_${notificationId}`
    const data = await chrome.storage.local.get(key)
    const targetUrl = data[key]
    if (targetUrl && isSafeUrl(targetUrl)) {
      chrome.tabs.create({ url: targetUrl })
      await chrome.storage.local.remove(key)
    }
    chrome.notifications.clear(notificationId)
  })

  // 关闭或忽略通知时清理本地存储映射
  chrome.notifications.onClosed.addListener((notificationId) => {
    const key = `notif_${notificationId}`
    void chrome.storage.local.remove(key)
  })

  // 监听右键菜单点击
  chrome.contextMenus.onClicked.addListener(async (info, tab) => {
    if (info.menuItemId !== 'paper-room-import-item') return

    let targetUrl = info.linkUrl || info.pageUrl || tab?.url

    // 1. 若用户在相册详情页 (tab.url 包含 /album/) 右键点击了章节链接 (linkUrl 包含 /photo/)，直接采用相册主页 URL
    if (
      info.linkUrl &&
      info.linkUrl.includes('/photo/') &&
      tab?.url &&
      tab.url.includes('/album/')
    ) {
      targetUrl = tab.url
    }
    // 2. 若用户在单话阅读页空白处右键 (未点选链接)，尝试从当前阅读页 DOM 中提取整部作品相册 (/album/) 主链接
    else if (!info.linkUrl && targetUrl && targetUrl.includes('/photo/') && tab?.id) {
      const albumUrl = await extractJmAlbumUrl(tab.id)
      if (albumUrl) {
        targetUrl = albumUrl
      }
    }

    // 3. 禁漫单话阅读链接无法作为整部相册车号直接入库，若未能解析为相册则明确拦截并向用户提示
    if (targetUrl && /\/photo\/\d+/.test(targetUrl) && !/\/album\/\d+/.test(targetUrl)) {
      setBadge('!', '#e5484d')
      await showNotification(
        '无法识别相册车号',
        '禁漫单话阅读链接无法直接入库，请在相册主页空白处或封面链接上右键收录。',
      )
      return
    }

    const comic = resolveComicInfo(targetUrl)

    if (!comic) {
      setBadge('!', '#e5484d')
      await showNotification(
        '无法识别漫画来源',
        '请在支持的漫画详情页空白处或列表卡片链接上右键（支持禁漫、哔咔、拷贝）。',
      )
      return
    }

    void importComic(comic, { openTab: false })
  })
}

export {
  resolveComicInfo,
  buildUrlPatterns,
  isSafeUrl,
  detectComicFromTab,
  getConfig,
  showNotification,
  importComic,
}
