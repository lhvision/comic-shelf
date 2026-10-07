document.addEventListener('DOMContentLoaded', async () => {
  const serverUrlInput = document.getElementById('serverUrl')
  const tokenInput = document.getElementById('token')
  const customDomainsInput = document.getElementById('customDomains')
  const saveBtn = document.getElementById('saveBtn')
  const testBtn = document.getElementById('testBtn')
  const statusDiv = document.getElementById('status')

  // 加载已有配置
  const stored = await chrome.storage.local.get({
    serverUrl: 'http://localhost:8000',
    token: '',
    customDomains: [],
  })
  serverUrlInput.value = stored.serverUrl || 'http://localhost:8000'
  tokenInput.value = stored.token || ''
  customDomainsInput.value = Array.isArray(stored.customDomains)
    ? stored.customDomains.join(', ')
    : ''

  function showStatus(text, type = 'success') {
    statusDiv.textContent = text
    statusDiv.className = `status-msg ${type}`
  }

  // 保存配置
  saveBtn.addEventListener('click', async () => {
    let url = (serverUrlInput.value || 'http://localhost:8000').trim()
    if (!url.startsWith('http://') && !url.startsWith('https://')) {
      url = `http://${url}`
    }
    url = url.replace(/\/+$/, '')
    serverUrlInput.value = url

    const token = tokenInput.value.trim()
    const rawDomains = customDomainsInput.value.trim()
    const customDomains = rawDomains
      ? rawDomains
          .split(/[,，\s\n]+/)
          .map((d) =>
            d
              .trim()
              .replace(/^https?:\/\//, '')
              .replace(/\/.*$/, '')
              .replace(/^\*+\.?/, '')
              .replace(/:\d+$/, ''),
          )
          .filter(Boolean)
      : []

    await chrome.storage.local.set({
      serverUrl: url,
      token,
      customDomains,
    })

    showStatus('✓ 配置已保存', 'success')
    setTimeout(() => {
      if (statusDiv.textContent === '✓ 配置已保存') {
        statusDiv.textContent = ''
      }
    }, 3000)
  })

  // 测试连接
  testBtn.addEventListener('click', async () => {
    let url = (serverUrlInput.value || 'http://localhost:8000').trim()
    if (!url.startsWith('http://') && !url.startsWith('https://')) {
      url = `http://${url}`
    }
    url = url.replace(/\/+$/, '')
    serverUrlInput.value = url
    const token = tokenInput.value.trim()

    showStatus('正在连接纸间服务...', 'success')

    try {
      const headers = {}
      if (token) {
        headers['X-Auth-Token'] = token
        headers['Authorization'] = `Bearer ${token}`
      }

      const controller = new AbortController()
      const timeoutId = setTimeout(() => controller.abort(), 8000)

      const resp = await fetch(`${url}/api/auth/status`, {
        headers,
        signal: controller.signal,
      })
      clearTimeout(timeoutId)

      if (!resp.ok) {
        showStatus(`✕ 响应异常 (HTTP ${resp.status})`, 'error')
        return
      }

      const data = await resp.json()
      if (data.auth_required && !data.can_write) {
        showStatus('⚠️ 服务已连接，但口令不具备馆长写入权限', 'error')
      } else {
        const roleLabel = data.role === 'admin' ? '馆长 (admin)' : data.role || '馆长'
        showStatus(`✓ 连接成功！具备入库写入权限（角色: ${roleLabel}）`, 'success')
      }
    } catch (err) {
      if (err.name === 'AbortError') {
        showStatus('✕ 连接超时（8s），请确认服务地址是否正确且在运行', 'error')
      } else {
        showStatus(`✕ 连接失败: ${err.message || '无法访问目标服务器'}`, 'error')
      }
    }
  })
})
