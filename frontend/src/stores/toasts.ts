/** toast 通知：zustand store + 模块级 toast() 供 hook 外调用。
 * 同屏最多 3 条（旧的前 2 条 + 最新的）；3200ms 自动退场——先标记 leaving 播
 * 180ms 退场动画再移除，点击任意 toast 可关。直接消失的 toast 用户来不及
 * 感知"发生过什么"；堆叠不限则会淹没画布。 */
import { create } from 'zustand'

export type ToastTone = 'ok' | 'danger'

export interface ToastItem {
  id: number
  text: string
  tone: ToastTone
  leaving: boolean
}

const MAX_VISIBLE = 3
const AUTO_DISMISS_MS = 3200
const LEAVE_ANIMATION_MS = 180

interface ToastState {
  toasts: ToastItem[]
  push: (text: string, tone?: ToastTone) => void
  /** 标记退场（播动画），动画结束后移除 */
  close: (id: number) => void
  dismiss: (id: number) => void
}

let nextId = 0

export const useToasts = create<ToastState>((set, get) => ({
  toasts: [],
  push: (text, tone = 'ok') => {
    const id = ++nextId
    set((state) => ({
      toasts: [...state.toasts, { id, text, tone, leaving: false }].slice(-MAX_VISIBLE),
    }))
    setTimeout(() => get().close(id), AUTO_DISMISS_MS)
  },
  close: (id) => {
    const target = get().toasts.find((item) => item.id === id)
    if (!target || target.leaving) return
    set((state) => ({
      toasts: state.toasts.map((item) => (item.id === id ? { ...item, leaving: true } : item)),
    }))
    setTimeout(() => get().dismiss(id), LEAVE_ANIMATION_MS)
  },
  dismiss: (id) => set((state) => ({ toasts: state.toasts.filter((item) => item.id !== id) })),
}))

/** hook 外统一入口：toast('已保存') / toast('失败原因', 'danger') */
export function toast(text: string, tone: ToastTone = 'ok') {
  useToasts.getState().push(text, tone)
}
