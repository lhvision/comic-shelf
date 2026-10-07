import fs from 'node:fs'
import path from 'node:path'
import { execSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const rootDir = path.resolve(__dirname, '..')
const srcDir = path.resolve(rootDir, 'extension')
const distDir = path.resolve(rootDir, 'dist')
const zipFile = path.resolve(distDir, 'paper-room-extension.zip')

if (!fs.existsSync(distDir)) {
  fs.mkdirSync(distDir, { recursive: true })
}

// 直接将 extension/ 归档打包为发布 Zip，免除冗余目录拷贝
const pythonScript = `
import zipfile, os

src_dir = r'''${srcDir}'''
zip_path = r'''${zipFile}'''

with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
    for root, dirs, files in os.walk(src_dir):
        for f in files:
            full_path = os.path.join(root, f)
            arcname = os.path.relpath(full_path, src_dir)
            zf.write(full_path, arcname)
print(f'✅ Successfully packaged {zip_path} ({os.path.getsize(zip_path)} bytes)')
`

try {
  execSync(`python3 -c "${pythonScript.replace(/"/g, '\\"')}"`, { stdio: 'inherit' })
} catch {
  execSync(`cd "${srcDir}" && zip -r "${zipFile}" .`, { stdio: 'inherit' })
}
