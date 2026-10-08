import fs from 'node:fs'
import path from 'node:path'
import { execFileSync, execSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const rootDir = path.resolve(__dirname, '..')
const srcDir = path.resolve(rootDir, 'extension')
const distDir = path.resolve(rootDir, 'dist')
const zipFile = path.resolve(distDir, 'paper-room-extension.zip')

if (!fs.existsSync(distDir)) {
  fs.mkdirSync(distDir, { recursive: true })
}

// 直接将 extension/ 归档打包为发布 Zip，严格排除文档、类型声明与隐藏文件等非运行时资产
const pythonScript = `
import os, sys, zipfile

src_dir, zip_path = sys.argv[1], sys.argv[2]
EXCLUDE_SUFFIXES = ('.md', '.d.ts', '.map')

with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
    for root, dirs, files in os.walk(src_dir):
        for f in files:
            if f.startswith('.') or f.endswith(EXCLUDE_SUFFIXES):
                continue
            full_path = os.path.join(root, f)
            arcname = os.path.relpath(full_path, src_dir)
            zf.write(full_path, arcname)
print(f'✅ Successfully packaged {zip_path} ({os.path.getsize(zip_path)} bytes)')
`

try {
  execFileSync('python3', ['-c', pythonScript, srcDir, zipFile], { stdio: 'inherit' })
} catch {
  execSync(`cd "${srcDir}" && zip -r "${zipFile}" . -x "*.md" "*.d.ts" ".*"`, { stdio: 'inherit' })
}
