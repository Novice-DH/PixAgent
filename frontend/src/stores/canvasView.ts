/** 画布视图状态：zustand 全局单例（编辑器打开期间跨会话保留手感），永不持久化。
 *
 * 这里的 scale 是"视图缩放"（看多大），与 Layer.transform 的"图层形变"（内容多大）
 * 严格分离——前者不进任何文档或数据库。锚点缩放公式是手感核心：
 * 以 pivot 为不动点，x' = pivot.x - (pivot.x - x) * ratio，用户视线下的内容不漂移。
 *
 * 手感分界（S11）：离散操作（按钮/快捷键/适应）走 260ms easeOut 缓动，
 * 连续手势（滚轮/平移）直接跟手不插动画；任何直接操作先停进行中的缓动——
 * 用户和动画不抢方向盘。Stage 不做 scale 变换，缩放是各渲染方按 scale 重算屏幕几何。
 */
import { create } from 'zustand'

export const MIN_SCALE = 0.05
export const MAX_SCALE = 8
/** 适应时四周留白比例 */
export const FIT_RATIO = 0.92
/** 按钮/快捷键的倍率步长 */
export const ZOOM_STEP = 1.25
/** 离散缩放缓动时长（easeOut 立方） */
export const GLIDE_MS = 260
/** 滚轮增量先夹取到 ±WHEEL_CAP 再取指数：触控板小增量与鼠标大格同速感 */
export const WHEEL_CAP = 50
export const WHEEL_GAIN = 0.0035

interface Anchor {
  x: number
  y: number
}

interface ViewTransform {
  x: number
  y: number
  scale: number
}

interface CanvasViewState {
  x: number
  y: number
  scale: number
  viewportWidth: number
  viewportHeight: number
  /** 视口尺寸变化时中心锚定：x/y 补偿差值一半，画面内容不跳位（首帧直接 set） */
  setViewport: (width: number, height: number) => void
  /** 居中放置并留白；scale 封顶 100%（适应不放大）。默认带缓动，首次落位传 animate:false */
  fit: (docWidth: number, docHeight: number, options?: { animate?: boolean }) => void
  /** 滚轮缩放入口：增量先夹取再指数映射，指针为锚，直接跟手 */
  zoomByWheel: (delta: number, anchor?: Anchor) => void
  /** 按钮/快捷键步进：走缓动、以视口中心为锚 */
  stepZoom: (factor: number) => void
  /** 1 = 实际像素（内部转 stepZoom） */
  zoomTo: (target: number) => void
  pan: (x: number, y: number) => void
  panBy: (dx: number, dy: number) => void
}

const clampScale = (value: number) => Math.min(MAX_SCALE, Math.max(MIN_SCALE, value))
const easeOutCubic = (t: number) => 1 - (1 - t) ** 3

/** 模块级单例 rAF 帧句柄：全 store 同时至多一段缓动，直接操作先取消它 */
let glideHandle: number | null = null
function cancelGlide() {
  if (glideHandle !== null) {
    cancelAnimationFrame(glideHandle)
    glideHandle = null
  }
}

export const useCanvasView = create<CanvasViewState>((set, get) => {
  /** 从当前状态缓动到目标状态；直接操作经由 cancelGlide 接管 */
  const glideTo = (target: ViewTransform) => {
    cancelGlide()
    const from = get()
    if (
      from.scale === target.scale &&
      from.x === target.x &&
      from.y === target.y
    ) {
      set(target)
      return
    }
    const startX = from.x
    const startY = from.y
    const startScale = from.scale
    const startTime = performance.now()
    const tick = (now: number) => {
      const t = Math.min(1, (now - startTime) / GLIDE_MS)
      const e = easeOutCubic(t)
      if (t < 1) {
        set({
          x: startX + (target.x - startX) * e,
          y: startY + (target.y - startY) * e,
          scale: startScale + (target.scale - startScale) * e,
        })
        glideHandle = requestAnimationFrame(tick)
      } else {
        glideHandle = null
        set(target)
      }
    }
    glideHandle = requestAnimationFrame(tick)
  }

  return {
    x: 0,
    y: 0,
    scale: 1,
    viewportWidth: 0,
    viewportHeight: 0,
    setViewport: (width, height) => {
      const { viewportWidth, viewportHeight, x, y } = get()
      if (!viewportWidth || !viewportHeight || (viewportWidth === width && viewportHeight === height)) {
        set({ viewportWidth: width, viewportHeight: height })
        return
      }
      set({
        viewportWidth: width,
        viewportHeight: height,
        x: x + (width - viewportWidth) / 2,
        y: y + (height - viewportHeight) / 2,
      })
    },
    fit: (docWidth, docHeight, options) => {
      const { viewportWidth, viewportHeight, scale } = get()
      if (!viewportWidth || !viewportHeight || !docWidth || !docHeight) return
      const targetScale = clampScale(
        Math.min((viewportWidth / docWidth) * FIT_RATIO, (viewportHeight / docHeight) * FIT_RATIO, 1),
      )
      const target: ViewTransform = {
        scale: targetScale,
        x: (viewportWidth - docWidth * targetScale) / 2,
        y: (viewportHeight - docHeight * targetScale) / 2,
      }
      if (options?.animate === false || targetScale === scale) {
        cancelGlide()
        set(target)
        return
      }
      glideTo(target)
    },
    zoomByWheel: (delta, anchor) => {
      cancelGlide()
      const { x, y, scale, viewportWidth, viewportHeight } = get()
      const capped = Math.min(WHEEL_CAP, Math.max(-WHEEL_CAP, delta))
      const nextScale = clampScale(scale * Math.exp(-capped * WHEEL_GAIN))
      const ratio = nextScale / scale
      const pivot = anchor ?? { x: viewportWidth / 2, y: viewportHeight / 2 }
      set({
        scale: nextScale,
        x: pivot.x - (pivot.x - x) * ratio,
        y: pivot.y - (pivot.y - y) * ratio,
      })
    },
    stepZoom: (factor) => {
      const { x, y, scale, viewportWidth, viewportHeight } = get()
      const nextScale = clampScale(scale * factor)
      if (nextScale === scale) {
        cancelGlide()
        return
      }
      const ratio = nextScale / scale
      const pivot = { x: viewportWidth / 2, y: viewportHeight / 2 }
      glideTo({
        scale: nextScale,
        x: pivot.x - (pivot.x - x) * ratio,
        y: pivot.y - (pivot.y - y) * ratio,
      })
    },
    zoomTo: (target) => {
      get().stepZoom(clampScale(target) / get().scale)
    },
    pan: (x, y) => {
      cancelGlide()
      set({ x, y })
    },
    panBy: (dx, dy) => {
      cancelGlide()
      set({ x: get().x + dx, y: get().y + dy })
    },
  }
})
