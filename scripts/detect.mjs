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

const scriptPath = findScript('detect.mjs')
if (scriptPath) {
  const res = spawnSync(process.execPath, [scriptPath, ...process.argv.slice(2)], {
    stdio: 'inherit',
    env: process.env,
  })
  process.exit(res.status ?? 0)
} else {
  // 跨平台降级：若他人环境未安装该 skill，输出提示并平滑退出 0
  console.log('[detect] Impeccable 规则检测脚本未在标准路径命中，跳过静态 Slop 检测。')
  process.exit(0)
}
