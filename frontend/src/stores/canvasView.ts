/** 画布视图状态：zustand 全局单例（编辑器打开期间跨会话保留手感），永不持久化。
 *
 * 这里的 scale 是"视图缩放"（看多大），与 Layer.transform 的"图层形变"（内容多大）
 * 严格分离——前者不进任何文档或数据库。锚点缩放公式是手感核心：
 * 以 pivot 为不动点，x' = pivot.x - (pivot.x - x) * ratio，用户视线下的内容不漂移。
 */
import { create } from 'zustand'

export const MIN_SCALE = 0.05
export const MAX_SCALE = 8
/** 适应时四周留白比例 */
export const FIT_RATIO = 0.92
/** 工具栏 −/＋ 的倍率步长 */
export const ZOOM_STEP = 1.2

interface Anchor {
  x: number
  y: number
}

interface CanvasViewState {
  x: number
  y: number
  scale: number
  viewportWidth: number
  viewportHeight: number
  setViewport: (width: number, height: number) => void
  /** 居中放置并留白；scale 封顶 100%（适应不放大超过实际像素） */
  fit: (docWidth: number, docHeight: number) => void
  zoomBy: (factor: number, anchor?: Anchor) => void
  /** 1 = 实际像素 */
  zoomTo: (target: number, anchor?: Anchor) => void
  pan: (x: number, y: number) => void
}

const clampScale = (value: number) => Math.min(MAX_SCALE, Math.max(MIN_SCALE, value))

export const useCanvasView = create<CanvasViewState>((set, get) => ({
  x: 0,
  y: 0,
  scale: 1,
  viewportWidth: 0,
  viewportHeight: 0,
  setViewport: (width, height) => set({ viewportWidth: width, viewportHeight: height }),
  fit: (docWidth, docHeight) => {
    const { viewportWidth, viewportHeight } = get()
    if (!viewportWidth || !viewportHeight || !docWidth || !docHeight) return
    const scale = clampScale(
      Math.min((viewportWidth / docWidth) * FIT_RATIO, (viewportHeight / docHeight) * FIT_RATIO, 1),
    )
    set({
      scale,
      x: (viewportWidth - docWidth * scale) / 2,
      y: (viewportHeight - docHeight * scale) / 2,
    })
  },
  zoomBy: (factor, anchor) => {
    const { x, y, scale, viewportWidth, viewportHeight } = get()
    const pivot = anchor ?? { x: viewportWidth / 2, y: viewportHeight / 2 }
    const nextScale = clampScale(scale * factor)
    const ratio = nextScale / scale
    set({
      scale: nextScale,
      x: pivot.x - (pivot.x - x) * ratio,
      y: pivot.y - (pivot.y - y) * ratio,
    })
  },
  zoomTo: (target, anchor) => {
    const { scale } = get()
    get().zoomBy(clampScale(target) / scale, anchor)
  },
  pan: (x, y) => set({ x, y }),
}))
