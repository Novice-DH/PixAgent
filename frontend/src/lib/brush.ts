/** 笔刷常量单点：radius 与画布像素宽的换算唯一来源。
 * 前端显式传 radius 给服务端（addStroke），预览线宽与服务端遮罩同源同宽——
 * 两端各算一遍但共用同一公式与常量，漂移只可能来自改这里不改后端。 */

/** 笔刷粗细（相对画布短边比例），与后端 SelectIn.radius 默认值一致。 */
export const BRUSH_RADIUS = 0.03

/** 笔刷画布像素宽：max(2, min(w,h) × radius)——与后端 rasterize_strokes 同一公式。 */
export function brushWidth(docWidth: number, docHeight: number): number {
  return Math.max(2, Math.floor(Math.min(docWidth, docHeight) * BRUSH_RADIUS))
}
