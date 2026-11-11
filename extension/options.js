/**
 * 纸间 · Paper Room 扩展配置面板逻辑
 * 遵循 Impeccable 设计规范、可用性标准与草稿暂存单一提交模型
 */
import {
  BUILTIN_PROVIDERS,
  createEmptyCustomDomainsMap,
  sanitizeDomain,
  isValidDomain,
  guessProviderFromDomain,
  findDomainOwner,
  migrateCustomDomains,
} from './constants.js'

document.addEventListener('DOMContentLoaded', async () => {
  const serverUrlInput = document.getElementById('serverUrl')
  const serverUrlError = document.getElementById('serverUrlError')
  const tokenInput = document.getElementById('token')
  const enableNotificationsInput = document.getElementById('enableNotifications')
  const providerSelect = document.getElementById('providerSelect')
  const domainInput = document.getElementById('domainInput')
  const addDomainBtn = document.getElementById('addDomainBtn')
  const domainFeedback = document.getElementById('domainFeedback')
  const domainSuggestHint = document.getElementById('domainSuggestHint')
  const providerCardsContainer = document.getElementById('providerCardsContainer')
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

  /**
   * 深拷贝图源自定义分流字典
   */
  function cloneCustomDomains(map) {
    const res = createEmptyCustomDomainsMap()
    if (map && typeof map === 'object') {
      for (const p of BUILTIN_PROVIDERS) {
        if (Array.isArray(map[p.source])) {
          res[p.source] = [...map[p.source]]
        }
      }
    }
    return res
  }

  // 本地草稿与已持久化快照
  let customDomainsDraft = createEmptyCustomDomainsMap()
  let savedSnapshot = {
    serverUrl: 'http://localhost:8000',
    token: '',
    enableNotifications: true,
    customDomains: createEmptyCustomDomainsMap(),
  }

  // 1. 脏状态与离开防护检测
  function isDirty() {
    const currentUrl = (serverUrlInput.value || '').trim()
    const currentToken = tokenInput.value.trim()
    const urlDirty = currentUrl !== savedSnapshot.serverUrl
    const tokenDirty = currentToken !== savedSnapshot.token
    const notifDirty = enableNotificationsInput.checked !== savedSnapshot.enableNotifications

    const sources = BUILTIN_PROVIDERS.map((p) => p.source)
    const domainsDirty = sources.some((src) => {
      const draftList = customDomainsDraft[src] || []
      const savedList = savedSnapshot.customDomains[src] || []
      if (draftList.length !== savedList.length) return true
      return draftList.some((d, idx) => d !== savedList[idx])
    })

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

  /**
   * 渲染三大图源统一面板
   * @param {string|null} [focusSource]
   * @param {number} [focusIndex]
   */
  function renderProviderCards(focusSource = null, focusIndex = -1) {
    providerCardsContainer.innerHTML = ''

    for (const provider of BUILTIN_PROVIDERS) {
      const card = document.createElement('div')
      card.className = 'provider-card'
      card.setAttribute('data-source', provider.source)

      const customList = customDomainsDraft[provider.source] || []
      const builtinList = provider.domains || []

      // 卡片头部
      const header = document.createElement('div')
      header.className = 'provider-card-header'

      const title = document.createElement('div')
      title.className = 'provider-card-title'
      title.innerHTML = `<span>${provider.name}</span><span class="provider-badge">${provider.badge}</span>`

      const summary = document.createElement('div')
      summary.className = 'provider-count-summary'
      summary.textContent = `${customList.length} 自定义 · ${builtinList.length} 内置`

      header.appendChild(title)
      header.appendChild(summary)
      card.appendChild(header)

      // 自定义分流区块
      const customSubgroup = document.createElement('div')
      customSubgroup.className = 'card-subgroup'

      const customTitle = document.createElement('div')
      customTitle.className = 'card-subgroup-title'
      customTitle.innerHTML = `<span>自定义分流 (${customList.length})</span>`
      customSubgroup.appendChild(customTitle)

      const customChipsWrap = document.createElement('div')
      customChipsWrap.className = 'custom-chips-wrap'
      customChipsWrap.setAttribute('role', 'list')

      if (customList.length === 0) {
        const emptyTip = document.createElement('div')
        emptyTip.className = 'empty-custom-tip'
        emptyTip.textContent = '暂无自定义分流域名（若该源有新镜像，可在上方输入添加）'
        customChipsWrap.appendChild(emptyTip)
      } else {
        customList.forEach((domain, idx) => {
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
          removeBtn.setAttribute('aria-label', `移除【${provider.name}】分流域名 ${domain}`)
          removeBtn.title = `移除 ${domain}`
          removeBtn.innerHTML = `
            <svg class="icon-svg" style="width: 12px; height: 12px;" viewBox="0 0 24 24">
              <line x1="18" y1="6" x2="6" y2="18"></line>
              <line x1="6" y1="6" x2="18" y2="18"></line>
            </svg>
          `

          removeBtn.addEventListener('click', (e) => {
            e.stopPropagation()
            customDomainsDraft[provider.source].splice(idx, 1)

            // 焦点回溯 (Focus Restoration)
            let nextFocusIndex = idx
            if (nextFocusIndex >= customDomainsDraft[provider.source].length) {
              nextFocusIndex = customDomainsDraft[provider.source].length - 1
            }
            renderProviderCards(provider.source, nextFocusIndex)
            updateDirtyState()
          })

          chip.appendChild(text)
          chip.appendChild(removeBtn)
          customChipsWrap.appendChild(chip)
        })
      }

      customSubgroup.appendChild(customChipsWrap)
      card.appendChild(customSubgroup)

      // 内置分流区块 (可折叠抽屉)
      const builtinDrawer = document.createElement('details')
      builtinDrawer.className = 'builtin-drawer'

      const summaryElem = document.createElement('summary')
      summaryElem.innerHTML = `
        <span class="summary-label">
          <svg class="icon-svg" style="width: 13px; height: 13px" viewBox="0 0 24 24">
            <circle cx="12" cy="12" r="10"></circle>
            <line x1="2" y1="12" x2="22" y2="12"></line>
            <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"></path>
          </svg>
          <span>官方内置分流 (${builtinList.length} 个)</span>
        </span>
        <svg class="icon-svg drawer-chevron" viewBox="0 0 24 24">
          <polyline points="6 9 12 15 18 9"></polyline>
        </svg>
      `
      builtinDrawer.appendChild(summaryElem)

      const drawerContent = document.createElement('div')
      drawerContent.className = 'drawer-content'
      const builtinChipsWrap = document.createElement('div')
      builtinChipsWrap.className = 'builtin-chips'

      for (const d of builtinList) {
        const chip = document.createElement('span')
        chip.className = 'builtin-chip'
        chip.textContent = d
        builtinChipsWrap.appendChild(chip)
      }
      drawerContent.appendChild(builtinChipsWrap)
      builtinDrawer.appendChild(drawerContent)
      card.appendChild(builtinDrawer)

      providerCardsContainer.appendChild(card)
    }

    // 执行焦点复位
    if (typeof focusSource === 'string' && focusIndex >= 0) {
      const card = providerCardsContainer.querySelector(`[data-source="${focusSource}"]`)
      if (card) {
        const chips = card.querySelectorAll('.btn-remove')
        if (chips[focusIndex]) {
          chips[focusIndex].focus()
        } else if (chips.length > 0) {
          chips[chips.length - 1].focus()
        } else {
          domainInput.focus()
        }
      }
    }
  }

  // 4. 提示信息展示（全矢量 SVG 图标）
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

  let suggestTimer = null
  function setSuggestHint(msg) {
    if (suggestTimer) clearTimeout(suggestTimer)
    domainSuggestHint.textContent = msg
    if (msg) {
      domainSuggestHint.className = 'domain-suggest-hint show'
      suggestTimer = setTimeout(() => {
        domainSuggestHint.className = 'domain-suggest-hint'
      }, 3500)
    } else {
      domainSuggestHint.className = 'domain-suggest-hint'
    }
  }

  // 5. 域名智能预判切换
  domainInput.addEventListener('input', () => {
    setDomainFeedback('')
    const val = domainInput.value.trim()
    if (!val) {
      setSuggestHint('')
      return
    }

    const guessed = guessProviderFromDomain(val)
    if (guessed && guessed !== providerSelect.value) {
      providerSelect.value = guessed
      const p = BUILTIN_PROVIDERS.find((item) => item.source === guessed)
      setSuggestHint(`已根据域名特征自动切换目标为【${p?.name || guessed}】，可按需手动调整`)
    }
  })

  // 6. 域名追加（带全局唯一性排重校验，支持单项与多项批量粘贴）
  function handleAddDomain() {
    const raw = domainInput.value.trim()
    if (!raw) {
      setDomainFeedback('请输入要追加的分流域名')
      domainInput.focus()
      return
    }

    const targetSource = providerSelect.value
    const targetProvider = BUILTIN_PROVIDERS.find((p) => p.source === targetSource)

    const segments = raw
      .split(/[,，\s\n]+/)
      .map((s) => s.trim())
      .filter(Boolean)

    const added = []
    const skippedInvalid = []
    const skippedCollisions = []

    for (const segment of segments) {
      const domain = sanitizeDomain(segment)
      if (!domain || !isValidDomain(domain)) {
        skippedInvalid.push(segment)
        continue
      }

      // 0. 防范将纸间服务自身主机名作为图源分流添加
      let serverHost = ''
      try {
        const rawServer = serverUrlInput.value.trim()
        if (rawServer) {
          const urlStr = rawServer.startsWith('http') ? rawServer : `http://${rawServer}`
          serverHost = new URL(urlStr).hostname.toLowerCase()
        }
      } catch {
        // 忽略解析异常
      }
      if (serverHost && (domain === serverHost || domain.endsWith(`.${serverHost}`))) {
        skippedCollisions.push(`${domain}（为当前纸间服务自身地址，不可作为图源分流）`)
        continue
      }

      // 全局唯一性排重：所有域名在全系统仅允许出现一次，且防范父子域名重叠冲突
      const owner = findDomainOwner(domain, customDomainsDraft)
      if (owner) {
        if (owner.conflictType === 'exact') {
          if (owner.isBuiltin) {
            skippedCollisions.push(`${domain}（已在【${owner.name}】官方内置中）`)
          } else if (owner.source === targetSource) {
            skippedCollisions.push(`${domain}（已在【${owner.name}】自定义分流中）`)
          } else {
            skippedCollisions.push(
              `${domain}（已属于【${owner.name}】自定义分流，不可跨图源重复配置）`,
            )
          }
        } else if (owner.conflictType === 'subdomain') {
          if (owner.source === targetSource) {
            skippedCollisions.push(
              `${domain}（已属于【${owner.name}】域名 ${owner.conflictDomain} 的子域名，无需重复添加）`,
            )
          } else {
            skippedCollisions.push(
              `${domain}（属于【${owner.name}】域名 ${owner.conflictDomain} 的子域名，不可跨图源冲突添加）`,
            )
          }
        } else if (owner.conflictType === 'parent') {
          skippedCollisions.push(
            `${domain}（包含了【${owner.name}】已有分流 ${owner.conflictDomain}，不可跨层级重叠添加）`,
          )
        }
        continue
      }

      if (!customDomainsDraft[targetSource]) {
        customDomainsDraft[targetSource] = []
      }
      customDomainsDraft[targetSource].push(domain)
      added.push(domain)
    }

    if (added.length === 0) {
      if (skippedInvalid.length > 0) {
        setDomainFeedback(`域名格式不合法: ${skippedInvalid.join(', ')}`)
      } else if (skippedCollisions.length > 0) {
        setDomainFeedback(`域名冲突拦截: ${skippedCollisions.join('；')}`)
      }
      domainInput.focus()
      return
    }

    setDomainFeedback('')
    setSuggestHint('')
    domainInput.value = ''
    renderProviderCards()
    updateDirtyState()

    if (skippedCollisions.length > 0) {
      showStatus(
        `成功向【${targetProvider?.name}】添加 ${added.length} 个分流，其余冲突项已跳过: ${skippedCollisions.join('；')}`,
        'warning',
        true,
      )
    } else {
      showStatus(
        `成功向【${targetProvider?.name}】追加 ${added.length} 个分流域名`,
        'success',
        true,
      )
    }

    domainInput.focus()
  }

  addDomainBtn.addEventListener('click', handleAddDomain)
  domainInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
      e.preventDefault()
      handleAddDomain()
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

  // 7. 加载已有配置并快照（含存量老数据自愈迁移）
  const stored = await chrome.storage.local.get({
    serverUrl: 'http://localhost:8000',
    token: '',
    enableNotifications: true,
    customDomains: {},
  })

  const migratedCustomMap = migrateCustomDomains(stored.customDomains)

  // 若从老格式迁移成功，异步保存以自愈存储
  if (Array.isArray(stored.customDomains)) {
    try {
      await chrome.storage.local.set({ customDomains: migratedCustomMap })
    } catch (err) {
      console.warn('[Paper Room] 迁移存储写回异常:', err)
    }
  }

  savedSnapshot = {
    serverUrl: stored.serverUrl || 'http://localhost:8000',
    token: stored.token || '',
    enableNotifications: stored.enableNotifications !== false,
    customDomains: cloneCustomDomains(migratedCustomMap),
  }

  serverUrlInput.value = savedSnapshot.serverUrl
  tokenInput.value = savedSnapshot.token
  enableNotificationsInput.checked = savedSnapshot.enableNotifications
  customDomainsDraft = cloneCustomDomains(migratedCustomMap)
  renderProviderCards()

  // 8. 重置放弃修改
  resetBtn.addEventListener('click', () => {
    serverUrlInput.value = savedSnapshot.serverUrl
    tokenInput.value = savedSnapshot.token
    enableNotificationsInput.checked = savedSnapshot.enableNotifications
    customDomainsDraft = cloneCustomDomains(savedSnapshot.customDomains)
    clearServerUrlError()
    setDomainFeedback('')
    setSuggestHint('')
    renderProviderCards()
    updateDirtyState()
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
      const persistedDomains = cloneCustomDomains(customDomainsDraft)
      await chrome.storage.local.set({
        serverUrl: validated.url,
        token,
        enableNotifications,
        customDomains: persistedDomains,
      })

      savedSnapshot = {
        serverUrl: validated.url,
        token,
        enableNotifications,
        customDomains: cloneCustomDomains(persistedDomains),
      }
      updateDirtyState()

      showStatus('配置已保存至本地，各图源分流与右键收录菜单已同步生效', 'success', true)
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
