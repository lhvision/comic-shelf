#!/usr/bin/env node
import fs from 'node:fs'
import path from 'node:path'
import os from 'node:os'
import { spawnSync } from 'node:child_process'

function findScript(name) {
  const home = os.homedir()
  const candidates = [
    process.env.IMPECCABLE_DIR ? path.join(process.env.IMPECCABLE_DIR, 'scripts', name) : null,
    path.join(process.cwd(), '.agents/skills/impeccable/scripts', name),
    path.join(process.cwd(), '.claude/skills/impeccable/scripts', name),
    path.join(home, '.gemini/config/skills/impeccable/scripts', name),
    path.join(home, '.claude/skills/impeccable/scripts', name),
    path.join(home, '.agents/skills/impeccable/scripts', name),
  ].filter(Boolean)

  for (const p of candidates) {
    if (fs.existsSync(p)) return p
  }
  return null
}

const scriptPath = findScript('critique-storage.mjs')
if (scriptPath) {
  const res = spawnSync(process.execPath, [scriptPath, ...process.argv.slice(2)], {
    stdio: 'inherit',
    env: process.env,
  })
  process.exit(res.status ?? 0)
} else {
  // 跨平台降级：若他人运行环境未全局安装 impeccable skill，提供原生 Node.js 快照写入
  const args = process.argv.slice(2)
  const cmd = args[0]
  if (cmd === 'write') {
    const slug = (args[1] || 'general').replace(/[^a-zA-Z0-9_-]+/g, '-')
    const bodyPath = args[2]
    if (bodyPath && !fs.existsSync(bodyPath)) {
      console.error(`[critique] 指定的快照报告文件不存在: ${bodyPath}`)
      process.exit(1)
    }
    const body = bodyPath ? fs.readFileSync(bodyPath, 'utf-8') : ''
    const now = new Date()
    const timestamp = now
      .toISOString()
      .replace(/[:.]/g, '-')
      .replace(/-\d+Z$/, 'Z')
    const dir = path.join(process.cwd(), '.impeccable/critique')
    fs.mkdirSync(dir, { recursive: true })
    const targetFile = path.join(dir, `${timestamp}__${slug}.md`)
    fs.writeFileSync(targetFile, body.trim() + '\n', 'utf-8')
    console.log(targetFile)
    process.exit(0)
  } else if (cmd === 'slug') {
    const target = args[1] || ''
    console.log(target.replace(/[^a-zA-Z0-9_-]+/g, '-'))
    process.exit(0)
  } else {
    console.error('impeccable skill 未检测到，原生降级模式仅支持 write / slug')
    process.exit(1)
  }
}
