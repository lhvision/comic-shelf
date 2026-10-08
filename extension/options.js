/**
 * 纸间 · Paper Room 扩展配置面板逻辑
 * 遵循 Impeccable 设计规范、可用性标准与草稿暂存单一提交模型
 */
import { BUILTIN_PROVIDERS, DEFAULT_DOMAINS, sanitizeDomain, isValidDomain } from './constants.js'

document.addEventListener('DOMContentLoaded', async () => {
  const serverUrlInput = document.getElementById('serverUrl')
  const serverUrlError = document.getElementById('serverUrlError')
  const tokenInput = document.getElementById('token')
  const enableNotificationsInput = document.getElementById('enableNotifications')
  const domainInput = document.getElementById('domainInput')
  const addDomainBtn = document.getElementById('addDomainBtn')
  const domainFeedback = document.getElementById('domainFeedback')
  const customChipsContainer = document.getElementById('customChipsContainer')
  const customSection = document.getElementById('customSection')
  const customCountBadge = document.getElementById('customCountBadge')
  const builtinCountText = document.getElementById('builtinCountText')
  const builtinDrawerContent = document.getElementById('builtinDrawerContent')
  const testBtn = document.getElementById('testBtn')
  const testBtnIcon = document.getElementById('testBtnIcon')
  const testBtnText = document.getElementById('testBtnText')
  const resetBtn = document.getElementById('resetBtn')
  const saveBtn = document.getElementById('saveBtn')
  const saveBtnText = document.getElementById('saveBtnText')
  const dirtyIndicator = document.getElementById('dirtyIndicator')
  const statusBox = document.getElementById('statusBox')
  const statusIcon = document.getElementById('statusIcon')
  const statusText = document.getElementById('statusText')

  // 本地草稿与已持久化快照
  let customDomainsDraft = []
  let savedSnapshot = {
    serverUrl: 'http://localhost:8000',
    token: '',
    enableNotifications: true,
    customDomains: [],
  }

  // 1. 脏状态与离开防护检测
  function isDirty() {
    const currentUrl = (serverUrlInput.value || '').trim()
    const currentToken = tokenInput.value.trim()
    const urlDirty = currentUrl !== savedSnapshot.serverUrl
    const tokenDirty = currentToken !== savedSnapshot.token
    const notifDirty = enableNotificationsInput.checked !== savedSnapshot.enableNotifications
    const domainsDirty =
      customDomainsDraft.length !== savedSnapshot.customDomains.length ||
      customDomainsDraft.some((d, idx) => d !== savedSnapshot.customDomains[idx])
    return urlDirty || tokenDirty || notifDirty || domainsDirty
  }

  function updateDirtyState() {
    const dirty = isDirty()
    if (dirty) {
      dirtyIndicator.style.display = 'inline-block'
      resetBtn.style.display = 'inline-flex'
      saveBtnText.textContent = '保存修改'
      window.onbeforeunload = (e) => {
        e.preventDefault()
        e.returnValue = ''
      }
    } else {
      dirtyIndicator.style.display = 'none'
      resetBtn.style.display = 'none'
      saveBtnText.textContent = '保存配置'
      window.onbeforeunload = null
    }
  }

  // 2. 校验服务 URL (RFC 规范防御性校验)
  function validateServerUrl(raw) {
    if (!raw) return { ok: false, msg: '服务地址不能为空' }
    let url = raw.trim()
    if (!url.startsWith('http://') && !url.startsWith('https://')) {
      url = `http://${url}`
    }
    url = url.replace(/\/+$/, '')
    try {
      const parsed = new URL(url)
      if (parsed.protocol !== 'http:' && parsed.protocol !== 'https:') {
        return { ok: false, msg: '服务地址必须使用 http:// 或 https:// 协议' }
      }
      if (!parsed.hostname) {
        return { ok: false, msg: '服务地址缺少有效主机名' }
      }
      return { ok: true, url }
    } catch {
      return { ok: false, msg: '请输入合法的 URL 地址 (如 http://localhost:8000)' }
    }
  }

  function clearServerUrlError() {
    serverUrlInput.removeAttribute('aria-invalid')
    serverUrlError.textContent = ''
    serverUrlError.className = 'field-error-msg'
  }

  function setServerUrlError(msg) {
    serverUrlInput.setAttribute('aria-invalid', 'true')
    serverUrlError.textContent = msg
    serverUrlError.className = 'field-error-msg show'
  }

  // 3. 渲染内置图源抽屉内容
  function renderBuiltinProviders() {
    builtinDrawerContent.innerHTML = ''
    builtinCountText.textContent = `共 ${DEFAULT_DOMAINS.length} 个`

    for (const provider of BUILTIN_PROVIDERS) {
      const group = document.createElement('div')
      group.className = 'provider-group'

      const label = document.createElement('div')
      label.className = 'provider-label'
      label.innerHTML = `<span>${provider.name}</span><span class="provider-badge">${provider.badge} · ${provider.domains.length}</span>`
      group.appendChild(label)

      const chipsWrap = document.createElement('div')
      chipsWrap.className = 'builtin-chips'
      for (const d of provider.domains) {
        const chip = document.createElement('span')
        chip.className = 'builtin-chip'
        chip.textContent = d
        chipsWrap.appendChild(chip)
      }
      group.appendChild(chipsWrap)
      builtinDrawerContent.appendChild(group)
    }
  }

  // 4. 渲染用户自定义分流胶囊群（支持键盘焦点回溯）
  function renderCustomChips(focusIndex = -1) {
    customChipsContainer.innerHTML = ''
    customCountBadge.textContent = `${customDomainsDraft.length} 个`

    if (customDomainsDraft.length === 0) {
      customSection.style.display = 'none'
      updateDirtyState()
      return
    }

    customSection.style.display = 'block'

    customDomainsDraft.forEach((domain, index) => {
      const chip = document.createElement('div')
      chip.className = 'domain-chip'
      chip.setAttribute('role', 'listitem')

      const text = document.createElement('span')
      text.className = 'chip-domain-text'
      text.textContent = domain
      text.title = domain

      const removeBtn = document.createElement('button')
      removeBtn.type = 'button'
      removeBtn.className = 'btn-remove'
      removeBtn.setAttribute('aria-label', `移除分流域名 ${domain}`)
      removeBtn.title = `移除 ${domain}`
      removeBtn.innerHTML = `
        <svg class="icon-svg" style="width: 12px; height: 12px;" viewBox="0 0 24 24">
          <line x1="18" y1="6" x2="6" y2="18"></line>
          <line x1="6" y1="6" x2="18" y2="18"></line>
        </svg>
      `

      removeBtn.addEventListener('click', (e) => {
        e.stopPropagation()
        customDomainsDraft.splice(index, 1)

        // 焦点回溯 (Focus Restoration): 优先聚集同位置或前一位置，若空则聚焦输入框
        let nextFocusIndex = index
        if (nextFocusIndex >= customDomainsDraft.length) {
          nextFocusIndex = customDomainsDraft.length - 1
        }
        renderCustomChips(nextFocusIndex)
      })

      chip.appendChild(text)
      chip.appendChild(removeBtn)
      customChipsContainer.appendChild(chip)
    })

    // 执行焦点复位
    if (focusIndex >= 0 && customChipsContainer.children[focusIndex]) {
      const targetBtn = customChipsContainer.children[focusIndex].querySelector('.btn-remove')
      if (targetBtn) {
        targetBtn.focus()
      }
    } else if (focusIndex >= 0 && customDomainsDraft.length === 0) {
      domainInput.focus()
    }

    updateDirtyState()
  }

  // 5. 提示信息展示（全矢量 SVG 图标）
  let statusTimer = null
  function showStatus(text, type = 'success', autoDismiss = false) {
    if (statusTimer) clearTimeout(statusTimer)
    statusBox.className = `status-box ${type} show`
    statusText.textContent = text

    if (type === 'success') {
      statusIcon.innerHTML = `<polyline points="20 6 9 17 4 12"></polyline>`
    } else if (type === 'warning') {
      statusIcon.innerHTML = `
        <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path>
        <line x1="12" y1="9" x2="12" y2="13"></line>
        <line x1="12" y1="17" x2="12.01" y2="17"></line>
      `
    } else {
      statusIcon.innerHTML = `
        <circle cx="12" cy="12" r="10"></circle>
        <line x1="15" y1="9" x2="9" y2="15"></line>
        <line x1="9" y1="9" x2="15" y2="15"></line>
      `
    }

    if (autoDismiss) {
      statusTimer = setTimeout(() => {
        statusBox.className = 'status-box'
      }, 4000)
    }
  }

  function setDomainFeedback(msg) {
    domainFeedback.textContent = msg
    if (msg) {
      domainFeedback.className = 'domain-feedback show'
      domainInput.setAttribute('aria-invalid', 'true')
    } else {
      domainFeedback.className = 'domain-feedback'
      domainInput.removeAttribute('aria-invalid')
    }
  }

  // 6. 域名追加（支持单项与多项批量粘贴逗号/换行分隔）
  function handleAddDomain() {
    const raw = domainInput.value.trim()
    if (!raw) {
      setDomainFeedback('请输入要追加的域名')
      domainInput.focus()
      return
    }

    const segments = raw
      .split(/[,，\s\n]+/)
      .map((s) => s.trim())
      .filter(Boolean)
    const added = []
    const skippedBuiltin = []
    const skippedDuplicate = []
    const skippedInvalid = []

    for (const segment of segments) {
      const domain = sanitizeDomain(segment)
      if (!domain || !isValidDomain(domain)) {
        skippedInvalid.push(segment)
        continue
      }
      if (DEFAULT_DOMAINS.includes(domain)) {
        skippedBuiltin.push(domain)
        continue
      }
      if (customDomainsDraft.includes(domain)) {
        skippedDuplicate.push(domain)
        continue
      }
      customDomainsDraft.push(domain)
      added.push(domain)
    }

    if (added.length === 0) {
      if (skippedInvalid.length > 0) {
        setDomainFeedback(`域名格式不合法: ${skippedInvalid.join(', ')}`)
      } else if (skippedBuiltin.length > 0) {
        setDomainFeedback(`已在系统内置分流中: ${skippedBuiltin.join(', ')}`)
      } else if (skippedDuplicate.length > 0) {
        setDomainFeedback(`已在追加列表中: ${skippedDuplicate.join(', ')}`)
      }
      domainInput.focus()
      return
    }

    setDomainFeedback('')
    domainInput.value = ''
    renderCustomChips()
    domainInput.focus()
  }

  addDomainBtn.addEventListener('click', handleAddDomain)
  domainInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
      e.preventDefault()
      handleAddDomain()
    } else {
      setDomainFeedback('')
    }
  })

  // 监听输入框变更触发脏状态感知
  serverUrlInput.addEventListener('input', () => {
    clearServerUrlError()
    updateDirtyState()
  })
  tokenInput.addEventListener('input', () => {
    updateDirtyState()
  })
  enableNotificationsInput.addEventListener('change', async () => {
    const isEnabled = enableNotificationsInput.checked
    savedSnapshot.enableNotifications = isEnabled
    try {
      await chrome.storage.local.set({ enableNotifications: isEnabled })
      updateDirtyState()
      showStatus(
        isEnabled ? '已开启系统通知提示' : '已关闭系统通知提示（静默模式：仅保留工具栏图标角标）',
        'success',
        true,
      )
    } catch (err) {
      showStatus(`保存通知设置失败: ${err.message}`, 'error', true)
    }
  })

  // 7. 加载已有配置并快照
  renderBuiltinProviders()

  const stored = await chrome.storage.local.get({
    serverUrl: 'http://localhost:8000',
    token: '',
    enableNotifications: true,
    customDomains: [],
  })

  savedSnapshot = {
    serverUrl: stored.serverUrl || 'http://localhost:8000',
    token: stored.token || '',
    enableNotifications: stored.enableNotifications !== false,
    customDomains: Array.isArray(stored.customDomains) ? [...stored.customDomains] : [],
  }

  serverUrlInput.value = savedSnapshot.serverUrl
  tokenInput.value = savedSnapshot.token
  enableNotificationsInput.checked = savedSnapshot.enableNotifications
  customDomainsDraft = [...savedSnapshot.customDomains]
  renderCustomChips()

  // 8. 重置放弃修改
  resetBtn.addEventListener('click', () => {
    serverUrlInput.value = savedSnapshot.serverUrl
    tokenInput.value = savedSnapshot.token
    enableNotificationsInput.checked = savedSnapshot.enableNotifications
    customDomainsDraft = [...savedSnapshot.customDomains]
    clearServerUrlError()
    setDomainFeedback('')
    renderCustomChips()
    showStatus('已放弃未保存的草稿修改，恢复为已保存配置', 'warning', true)
  })

  // 9. 保存配置
  async function handleSave() {
    const validated = validateServerUrl(serverUrlInput.value)
    if (!validated.ok) {
      setServerUrlError(validated.msg)
      serverUrlInput.focus()
      return
    }
    clearServerUrlError()
    serverUrlInput.value = validated.url

    const token = tokenInput.value.trim()
    const enableNotifications = enableNotificationsInput.checked

    saveBtn.disabled = true
    try {
      await chrome.storage.local.set({
        serverUrl: validated.url,
        token,
        enableNotifications,
        customDomains: [...customDomainsDraft],
      })

      savedSnapshot = {
        serverUrl: validated.url,
        token,
        enableNotifications,
        customDomains: [...customDomainsDraft],
      }
      updateDirtyState()

      showStatus('配置已保存至本地，右键收录菜单已同步生效', 'success', true)
    } catch (err) {
      showStatus(`保存配置失败: ${err.message || '未知异常'}`, 'error', true)
    } finally {
      saveBtn.disabled = false
    }
  }

  saveBtn.addEventListener('click', () => {
    void handleSave()
  })

  // 全局 Ctrl+S / Cmd+S 快捷键保存
  window.addEventListener('keydown', (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 's') {
      e.preventDefault()
      void handleSave()
    }
  })

  // 10. 测试连接 (带 Loading 旋转动效与防刷机制)
  testBtn.addEventListener('click', async () => {
    const validated = validateServerUrl(serverUrlInput.value)
    if (!validated.ok) {
      setServerUrlError(validated.msg)
      serverUrlInput.focus()
      return
    }
    clearServerUrlError()
    serverUrlInput.value = validated.url
    const token = tokenInput.value.trim()

    // 激活加载态
    testBtn.disabled = true
    testBtn.setAttribute('aria-busy', 'true')
    const originalIconHtml = testBtnIcon.innerHTML
    testBtnIcon.innerHTML = `<path class="icon-spin" d="M21 12a9 9 0 1 1-6.219-8.56"></path>`
    testBtnText.textContent = '正在连接...'

    showStatus('正在连接纸间阅览室服务...', 'warning', false)

    try {
      const headers = {}
      if (token) {
        headers['X-Auth-Token'] = token
        headers['Authorization'] = `Bearer ${token}`
      }

      const controller = new AbortController()
      const timeoutId = setTimeout(() => controller.abort(), 8000)

      const resp = await fetch(`${validated.url}/api/auth/status`, {
        headers,
        signal: controller.signal,
      })
      clearTimeout(timeoutId)

      if (!resp.ok) {
        showStatus(`服务器响应异常 (HTTP ${resp.status})，请检查服务状态`, 'error')
        return
      }

      const data = await resp.json()
      if (data.auth_required && !data.can_write) {
        showStatus('服务已成功连接，但当前口令缺少馆长写入权限', 'warning')
      } else {
        const roleLabel = data.role === 'admin' ? '馆长 (admin)' : data.role || '馆长'
        showStatus(`连接成功！具备纸间收录入库写入权限（角色: ${roleLabel}）`, 'success')
      }
    } catch (err) {
      if (err.name === 'AbortError') {
        showStatus('连接超时 (8s)，请确认服务地址是否正确且在运行', 'error')
      } else {
        showStatus(`连接失败: ${err.message || '无法访问目标服务器'}`, 'error')
      }
    } finally {
      testBtn.disabled = false
      testBtn.removeAttribute('aria-busy')
      testBtnIcon.innerHTML = originalIconHtml
      testBtnText.textContent = '测试连接'
    }
  })
})
