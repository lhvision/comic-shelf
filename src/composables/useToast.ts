import { readonly, ref } from 'vue'

export interface Toast {
  id: number
  text: string
  tone: 'info' | 'error' | 'success'
}

const toasts = ref<Toast[]>([])
let nextId = 1

function push(text: string, tone: 'info' | 'error' | 'success' = 'info') {
  const id = nextId++
  toasts.value.push({ id, text, tone })
  window.setTimeout(() => {
    dismiss(id)
  }, 4200)
  return id
}

function dismiss(id: number) {
  const index = toasts.value.findIndex((toast) => toast.id === id)
  if (index !== -1) toasts.value.splice(index, 1)
}

export function useToast() {
  return {
    toasts: readonly(toasts),
    toast: push,
    dismiss,
  }
}
