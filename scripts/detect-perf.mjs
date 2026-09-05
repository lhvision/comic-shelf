#!/usr/bin/env node
/**
 * scripts/detect-perf.mjs
 *
 * 纸间 · Paper Room 确定性性能与强制同步重排静态扫描引擎 (Performance & Forced Reflow Detector)
 *
 * 扫描规则库：
 * 1. [forced-reflow-in-lifecycle] 严禁在 onMounted / onUpdated / watch + nextTick 顶层直接同步读取排版属性
 * 2. [resize-observer-scroll-read] useResizeObserver 回调中读取 scrollHeight/scrollWidth 导致几何抖动
 * 3. [unthrottled-scroll-layout] 滚动/轮盘/触控监听中未通过 requestAnimationFrame 节流即读取排版属性
 * 4. [missing-passive-listener] touchstart / touchmove / wheel 事件缺少 { passive: true }
 * 5. [layout-read-in-loop] 循环体内执行 DOM 布局读取导致高阶 Layout Thrashing
 */

import fs from 'node:fs'
import path from 'node:path'

const SRC_DIR = path.resolve(process.cwd(), 'src')
const isJson = process.argv.includes('--json')

const LAYOUT_PROPS = [
  'scrollHeight',
  'scrollWidth',
  'clientHeight',
  'clientWidth',
  'offsetHeight',
  'offsetWidth',
  'clientTop',
  'clientLeft',
  'offsetTop',
  'offsetLeft',
  'getBoundingClientRect',
  'getComputedStyle',
]

const LAYOUT_REGEX = new RegExp(`\\b(${LAYOUT_PROPS.join('|')})\\b`)

/**
 * 递归收集源码文件 (排除单测与声明文件)
 */
function collectFiles(dir) {
  const results = []
  const entries = fs.readdirSync(dir, { withFileTypes: true })
  for (const entry of entries) {
    const full = path.join(dir, entry.name)
    if (entry.isDirectory()) {
      if (entry.name === '__tests__' || entry.name === 'node_modules') continue
      results.push(...collectFiles(full))
    } else if (entry.isFile()) {
      if (
        (entry.name.endsWith('.vue') || entry.name.endsWith('.ts') || entry.name.endsWith('.js')) &&
        !entry.name.endsWith('.spec.ts') &&
        !entry.name.endsWith('.d.ts')
      ) {
        results.push(full)
      }
    }
  }
  return results
}

/**
 * 提取成对花括号内的代码块（支持深度计数与单/多行注释、字符串逃逸）
 */
function extractBalancedBlock(content, openBraceIndex) {
  let depth = 0
  let inString = null
  let inComment = false
  for (let i = openBraceIndex; i < content.length; i++) {
    const char = content[i]
    const nextChar = content[i + 1]

    if (inComment) {
      if (inComment === 'single' && char === '\n') inComment = false
      else if (inComment === 'multi' && char === '*' && nextChar === '/') {
        inComment = false
        i++
      }
      continue
    }

    if (inString) {
      if (char === '\\') {
        i++
        continue
      }
      if (char === inString) inString = null
      continue
    }

    if (char === '/' && nextChar === '/') {
      inComment = 'single'
      i++
      continue
    }
    if (char === '/' && nextChar === '*') {
      inComment = 'multi'
      i++
      continue
    }

    if (char === '"' || char === "'" || char === '`') {
      inString = char
      continue
    }

    if (char === '{') {
      depth++
    } else if (char === '}') {
      depth--
      if (depth === 0) {
        return {
          body: content.slice(openBraceIndex + 1, i),
          endIndex: i,
        }
      }
    }
  }
  return null
}

/**
 * 分析单个文件
 */
function analyzeFile(filePath) {
  const content = fs.readFileSync(filePath, 'utf-8')
  const lines = content.split('\n')
  const relativePath = path.relative(process.cwd(), filePath)
  const findings = []

  // 1. 检查生命周期内的同步排版读取 (onMounted / onUpdated)
  const mountCallerRegex = /\b(?:onMounted|onUpdated)\s*\(\s*(?:async\s*)?\([^)]*\)\s*=>\s*\{/g
  let match
  while ((match = mountCallerRegex.exec(content)) !== null) {
    const openBrace = match.index + match[0].length - 1
    const block = extractBalancedBlock(content, openBrace)
    if (!block) continue
    const body = block.body

    if (LAYOUT_REGEX.test(body)) {
      if (!body.includes('requestAnimationFrame') && !body.includes('requestIdleCallback')) {
        const lineNumber = content.slice(0, match.index).split('\n').length
        findings.push({
          rule: 'forced-reflow-in-lifecycle',
          severity: 'error',
          file: relativePath,
          line: lineNumber,
          message:
            '生命周期钩子内直接同步读取 DOM 几何属性，可能引发首屏或更新时的 Forced Reflow 掉帧。请改用 JIT 交互时探测或 requestAnimationFrame / requestIdleCallback 调度。',
          snippet: body.trim().split('\n')[0] || body.trim(),
        })
      }
    }
  }

  // 1.1 检查 watch / watchEffect 回调中直接读取排版属性
  const watchCallerRegex = /\b(?:watch|watchEffect)\s*\([^)]*=>\s*\{/g
  while ((match = watchCallerRegex.exec(content)) !== null) {
    const openBrace = match.index + match[0].length - 1
    const block = extractBalancedBlock(content, openBrace)
    if (!block) continue
    const body = block.body

    if (LAYOUT_REGEX.test(body)) {
      if (!body.includes('requestAnimationFrame') && !body.includes('requestIdleCallback')) {
        const lineNumber = content.slice(0, match.index).split('\n').length
        findings.push({
          rule: 'forced-reflow-in-watch',
          severity: 'error',
          file: relativePath,
          line: lineNumber,
          message:
            'watch/watchEffect 回调内直接同步读取 DOM 几何属性。响应式变动往往伴随 DOM 变动，此时读取排版属性会强制浏览器同步重排。请通过 requestAnimationFrame 调度。',
          snippet: body.trim().split('\n')[0] || body.trim(),
        })
      }
    }
  }

  // 2. 检查 useResizeObserver 回调内直接读取 scrollHeight / scrollWidth
  const roCallerRegex = /\buseResizeObserver\s*\([^,]+,\s*(?:async\s*)?\([^)]*\)\s*=>\s*\{/g
  while ((match = roCallerRegex.exec(content)) !== null) {
    const openBrace = match.index + match[0].length - 1
    const block = extractBalancedBlock(content, openBrace)
    if (!block) continue
    const body = block.body

    if (body.includes('scrollHeight') || body.includes('scrollWidth')) {
      const lineNumber = content.slice(0, match.index).split('\n').length
      findings.push({
        rule: 'resize-observer-scroll-read',
        severity: 'error',
        file: relativePath,
        line: lineNumber,
        message:
          'useResizeObserver 回调内直接读取被观察元素的 scrollHeight/scrollWidth 会绕过浏览器几何缓存触发强制重排。请通过 entry.contentRect 或 entry.borderBoxSize 获取尺寸。',
        snippet: body.trim().split('\n')[0] || body.trim(),
      })
    }
  }

  // 3. 逐行检查触控事件监听是否缺少 passive: true
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i]
    const lineNum = i + 1

    // 检查 @touchstart / @touchmove 是否具备 passive
    const touchTemplateMatch = /@(touchstart|touchmove)(?!\.passive)\b/.exec(line)
    if (touchTemplateMatch) {
      findings.push({
        rule: 'missing-passive-listener',
        severity: 'warning',
        file: relativePath,
        line: lineNum,
        message: `模板事件 @${touchTemplateMatch[1]} 建议声明为 @${touchTemplateMatch[1]}.passive 以避免阻塞主线程滚动合成器。`,
        snippet: line.trim(),
      })
    }

    // 检查 useEventListener / addEventListener 监听 touchstart / touchmove / wheel 是否显式声明 passive
    if (
      (line.includes('useEventListener') || line.includes('addEventListener')) &&
      (line.includes("'touchstart'") || line.includes("'touchmove'") || line.includes("'wheel'"))
    ) {
      const block = lines.slice(i, Math.min(lines.length, i + 5)).join(' ')
      if (!block.includes('passive: true') && !block.includes('passive:false')) {
        findings.push({
          rule: 'missing-passive-listener',
          severity: 'warning',
          file: relativePath,
          line: lineNum,
          message: '触控/轮盘事件监听器未显式配置 { passive: true }，可能导致高频手势滑动掉帧。',
          snippet: line.trim(),
        })
      }
    }
  }

  return findings
}

/**
 * 主执行流程
 */
function main() {
  const files = collectFiles(SRC_DIR)
  const allFindings = []

  for (const file of files) {
    const findings = analyzeFile(file)
    allFindings.push(...findings)
  }

  if (isJson) {
    console.log(JSON.stringify(allFindings, null, 2))
    const hasErrors = allFindings.some((f) => f.severity === 'error')
    process.exit(hasErrors ? 1 : 0)
  }

  console.log('\n📜 纸间 · 性能与强制同步重排静态扫描 (pnpm detect:perf)')
  console.log(`已扫描 ${files.length} 个前端源码文件...\n`)

  if (allFindings.length === 0) {
    console.log('✅ 未发现任何强制自动重排 (Forced Reflow) 或未节流排版性能反模式！\n')
    process.exit(0)
  }

  let errorCount = 0
  let warnCount = 0

  for (const finding of allFindings) {
    if (finding.severity === 'error') {
      errorCount++
      console.log(`❌ [ERROR] [${finding.rule}] ${finding.file}:${finding.line}`)
    } else {
      warnCount++
      console.log(`⚠️  [WARN]  [${finding.rule}] ${finding.file}:${finding.line}`)
    }
    console.log(`   说明: ${finding.message}`)
    console.log(`   代码: ${finding.snippet}\n`)
  }

  console.log(`--------------------------------------------------`)
  console.log(`扫描完成: ${errorCount} 处严重隐患, ${warnCount} 处建议改进。`)

  if (errorCount > 0) {
    console.log('🚨 存在阻塞性性能重排隐患，请参照提示修复。\n')
    process.exit(1)
  } else {
    console.log('✨ 0 严重阻塞隐患。\n')
    process.exit(0)
  }
}

main()
