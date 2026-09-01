/**
 * @file useFileStaging.ts
 * @description 通用画页与多图暂存池组合式函数（Composable）。
 *
 * 核心职责：
 * 1. 自然文件名排序：确保 `page_1.png`、`page_2.png`、`page_10.png` 按人类直觉的数字升序编排；
 * 2. 格式白名单过滤：自动过滤非图片类型（JPG/PNG/WebP/GIF/AVIF/BMP）并可选触发轻量通知；
 * 3. 聚合选择与拖拽：整合 VueUse 的 `useFileDialog`（点击选择）与 `useDropZone`（拖放区域）；
 * 4. 幂等与去重保护：支持基于 `name_size` 复合键去重，避免重复拖入导致的画页翻倍。
 */

import { ref, toValue, type MaybeRefOrGetter, type Ref } from 'vue'
import { useFileDialog, useDropZone } from '@vueuse/core'
import { useToast } from '@/composables/useToast'

/**
 * 自然文件名排序算法（Natural Alphanumeric Sort）
 * @param files 待排序的 File 数组
 * @returns 按文件名数字升序排列的新数组副本
 * @example
 * naturalSortFiles([File('p10.png'), File('p2.png')]) // => [File('p2.png'), File('p10.png')]
 */
export function naturalSortFiles(files: File[]): File[] {
  return [...files].sort((a, b) =>
    a.name.localeCompare(b.name, undefined, { numeric: true, sensitivity: 'base' }),
  )
}

/**
 * 图片文件格式校验与过滤
 * @param files 原始文件列表
 * @returns 过滤后的有效图片数组与被忽略的文件数量
 */
export function filterImageFiles(files: File[]): { valid: File[]; ignoredCount: number } {
  const valid = files.filter((f) => /\.(jpe?g|png|webp|gif|avif|bmp)$/i.test(f.name))
  return {
    valid,
    ignoredCount: files.length - valid.length,
  }
}

/**
 * `useFileStaging` 配置选项
 */
export interface UseFileStagingOptions {
  /** 是否开启文件名+文件大小的去重合并（默认: true） */
  deduplicate?: boolean
  /** 拖入非图片文件时是否弹出 Toast 提示（默认: true） */
  notifyIgnored?: boolean
  /** 禁用交互状态（如处于提交中、上传中或权限锁定时） */
  disabled?: MaybeRefOrGetter<boolean>
  /** 初始预设的文件列表 */
  initialFiles?: File[]
}

/**
 * 画页与多图暂存池 Hook
 * @param options 配置项
 * @returns 响应式文件列表、拖拽 Ref、打开文件弹窗函数与增删管理工具
 */
export function useFileStaging(options: UseFileStagingOptions = {}) {
  const { deduplicate = true, notifyIgnored = true, disabled } = options
  const { toast } = useToast()

  /** 当前暂存池中的就绪文件列表（已自然排序） */
  const files = ref<File[]>(options.initialFiles ?? []) as Ref<File[]>

  /** 绑定至拖拽接收 DOM 容器的 Template Ref */
  const dropZoneRef = ref<HTMLElement | null>(null)

  /**
   * 将原始文件加入暂存池（自动完成格式过滤、去重与自然排序）
   * @param rawList 待加入的文件列表
   * @param customDeduplicate 是否强制覆盖默认去重策略
   */
  function stageFiles(rawList: File[], customDeduplicate = deduplicate) {
    if (toValue(disabled)) return

    const { valid, ignoredCount } = filterImageFiles(rawList)
    if (ignoredCount > 0 && notifyIgnored) {
      toast('已自动忽略非图片格式文件（仅支持 JPG/PNG/WebP/AVIF 等）', 'info')
    }

    if (customDeduplicate) {
      const fileMap = new Map(files.value.map((f) => [`${f.name}_${f.size}`, f]))
      for (const f of valid) {
        fileMap.set(`${f.name}_${f.size}`, f)
      }
      files.value = naturalSortFiles(Array.from(fileMap.values()))
    } else {
      files.value = naturalSortFiles([...files.value, ...valid])
    }
  }

  const { open: triggerFileDialog, onChange: onFileDialogChange } = useFileDialog({
    multiple: true,
    accept: 'image/*',
    reset: true,
  })

  /** 主动唤起系统本地文件选择器 */
  function openFileDialog() {
    if (toValue(disabled)) return
    triggerFileDialog()
  }

  onFileDialogChange((selected) => {
    if (selected && !toValue(disabled)) {
      stageFiles(Array.from(selected))
    }
  })

  const { isOverDropZone } = useDropZone(dropZoneRef, {
    onDrop: (dropped) => {
      if (dropped && !toValue(disabled)) {
        stageFiles(dropped)
      }
    },
  })

  /** 从暂存池中移除指定索引的图片 */
  function removeFile(index: number) {
    if (index >= 0 && index < files.value.length) {
      files.value.splice(index, 1)
    }
  }

  /** 清空当前暂存池中的所有图片 */
  function clearFiles() {
    files.value = []
  }

  return {
    files,
    dropZoneRef,
    isOverDropZone,
    openFileDialog,
    stageFiles,
    removeFile,
    clearFiles,
    naturalSortFiles,
    filterImageFiles,
  }
}
