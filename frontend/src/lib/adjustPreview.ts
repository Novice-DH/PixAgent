/** 调色实时预览纯函数（前端）：与后端 app/edits/pixels.py `adjust` 语义对齐。
 *
 * ── 对齐契约（改一处必须两边同改）───────────────────────────────────────
 * 处理顺序两端一致：白平衡 → tone（阴影/高光）→ 亮度 → 对比度 → 自然饱和度
 * → 饱和度 → 晕影。语义常量共享：白平衡 28/20/12、tone 权重 64、晕影幂 1.6、
 * 对比度以整图平均灰度为轴心（PIL Contrast 语义，均值取自亮度之后的图）。
 * 灰度公式用 PIL L 模式整数系数 + 0x8000 进位：(r·19595 + g·38470 + b·7471 + 2^15) >> 16。
 * PIL 每个 blend 输出都钳回字节域——enhanced/合成/饱和度结果同样先钳再进下一阶段。
 * 逐像素对比验证（48×36 渐变图 9 组参数）：七组 maxΔ≤1；晕影 maxΔ=4 来自
 * 后端 256 低分辨率表 + 双线性放大的量化（同公式不同实现），视觉不可见。
 *
 * ── 与后端的已知现状差异（诚实预览，非缺陷）────────────────────────────
 * 1. 负向阴影/高光当前为 no-op：后端 _tone 的负 LUT 经 PIL point 钳为 0，
 *    delta=0 无效果——预览同样镜像此现状；后端修复负值路径时两处同改。
 * 2. sharpness 与 clarity 不参与预览（卷积运算每帧重算不现实），
 *    面板文案注明「应用后可见」——预览诚实分层，不做假预览。
 *
 * Konva 滤镜约定：返回的函数原地修改 ImageData；配合节点 cache({pixelRatio:0.6})
 * 把每帧预算压到屏幕分辨率量级。无 React 依赖。
 */

/** 参与实时预览的九参数（sharpness/clarity 明确不在列）。全部 −1..1、晕影 0..1。 */
export interface AdjustPreviewValues {
  brightness: number
  contrast: number
  highlights: number
  shadows: number
  temperature: number
  tint: number
  saturation: number
  vibrance: number
  vignette: number
}

export type AdjustPreviewKey = keyof AdjustPreviewValues

export const ADJUST_PREVIEW_KEYS = [
  'brightness',
  'contrast',
  'highlights',
  'shadows',
  'temperature',
  'tint',
  'saturation',
  'vibrance',
  'vignette',
] as const satisfies readonly AdjustPreviewKey[]

const clamp8 = (value: number) => (value < 0 ? 0 : value > 255 ? 255 : value)
/** PIL L 模式灰度：整数系数 + 0x8000 进位后右移 16 位（实测与 PIL convert("L") 逐值一致） */
const lumaOf = (r: number, g: number, b: number) =>
  (r * 19595 + g * 38470 + b * 7471 + 0x8000) >> 16

/** 九项全 0 → null（画布据此跳过滤镜与缓存）；否则返回单趟滤镜函数。 */
export function toAdjustPreview(
  values: Partial<Record<AdjustPreviewKey, number>> | null | undefined,
): ((imageData: ImageData) => void) | null {
  if (!values) return null
  const v = {} as AdjustPreviewValues
  let any = false
  for (const key of ADJUST_PREVIEW_KEYS) {
    const value = values[key] ?? 0
    v[key] = value
    if (value !== 0) any = true
  }
  if (!any) return null

  return (imageData: ImageData) => {
    const { data, width, height } = imageData
    const pixelCount = width * height

    // ---- 白平衡通道 LUT（后端 _white_balance：R+28t、G−20·tint、B−28t+12·tint）----
    const wbR = new Uint8ClampedArray(256)
    const wbG = new Uint8ClampedArray(256)
    const wbB = new Uint8ClampedArray(256)
    for (let level = 0; level < 256; level += 1) {
      wbR[level] = clamp8(level + 28 * v.temperature)
      wbG[level] = clamp8(level - 20 * v.tint)
      wbB[level] = clamp8(level + (-28 * v.temperature + 12 * v.tint))
    }

    // ---- tone 增量 LUT（后端 _tone：权重 64，按 luma 索引；负值钳 0 镜像后端现状）----
    const shadowsLut = new Int16Array(256)
    const highlightsLut = new Int16Array(256)
    for (let level = 0; level < 256; level += 1) {
      shadowsLut[level] =
        v.shadows > 0 ? Math.round((v.shadows * (255 - level)) / 255 * 64) : 0
      highlightsLut[level] =
        v.highlights > 0 ? Math.round((v.highlights * level) / 255 * 64) : 0
    }

    // ---- 第一趟：白平衡 + tone（先阴影后高光，各自基于当前 luma）----
    for (let i = 0; i < pixelCount; i += 1) {
      const offset = i * 4
      let r = wbR[data[offset]!]
      let g = wbG[data[offset + 1]!]
      let b = wbB[data[offset + 2]!]
      if (v.shadows > 0) {
        const delta = shadowsLut[lumaOf(r, g, b)]!
        r = clamp8(r + delta)
        g = clamp8(g + delta)
        b = clamp8(b + delta)
      }
      if (v.highlights > 0) {
        const delta = highlightsLut[lumaOf(r, g, b)]!
        r = clamp8(r + delta)
        g = clamp8(g + delta)
        b = clamp8(b + delta)
      }
      data[offset] = r
      data[offset + 1] = g
      data[offset + 2] = b
    }

    // ---- 第二趟：亮度；随后统计均值——PIL 的对比度轴心取自亮度之后的图 ----
    const brightness = 1 + v.brightness
    const contrast = 1 + v.contrast
    const saturation = 1 + v.saturation
    let lumaSum = 0
    if (v.brightness !== 0) {
      for (let i = 0; i < pixelCount; i += 1) {
        const offset = i * 4
        data[offset] = clamp8(data[offset]! * brightness)
        data[offset + 1] = clamp8(data[offset + 1]! * brightness)
        data[offset + 2] = clamp8(data[offset + 2]! * brightness)
      }
    }
    for (let i = 0; i < pixelCount; i += 1) {
      const offset = i * 4
      lumaSum += lumaOf(data[offset]!, data[offset + 1]!, data[offset + 2]!)
    }
    // PIL ImageEnhance.Contrast 的轴心：int(均值)，截断取整
    const mean = Math.floor(lumaSum / pixelCount)

    // ---- 第三趟：对比度 → 自然饱和度 → 饱和度 → 晕影 ----
    const cx = (width - 1) / 2
    const cy = (height - 1) / 2
    const corner = Math.SQRT2
    for (let i = 0; i < pixelCount; i += 1) {
      const offset = i * 4
      // 亮度已在第二趟应用；对比度后钳回字节域——PIL 的 vibrance/饱和度以该字节图为输入
      let r = data[offset]!
      let g = data[offset + 1]!
      let b = data[offset + 2]!
      // 对比度绕整图均值灰度拉伸（PIL Contrast：mean + (c − mean) × factor）
      r = clamp8(mean + (r - mean) * contrast)
      g = clamp8(mean + (g - mean) * contrast)
      b = clamp8(mean + (b - mean) * contrast)
      if (v.vibrance !== 0) {
        // 逐像素灰心饱和 + chroma 反比掩码（PIL _vibrance：已鲜艳色少加）。
        // PIL 每个 blend 输出都是字节图——enhanced 先钳位再参与合成
        const gray = lumaOf(r, g, b)
        const enhancedR = clamp8(gray + (r - gray) * (1 + v.vibrance))
        const enhancedG = clamp8(gray + (g - gray) * (1 + v.vibrance))
        const enhancedB = clamp8(gray + (b - gray) * (1 + v.vibrance))
        const chroma = Math.max(r, g, b) - Math.min(r, g, b)
        const mask = (Math.abs(v.vibrance) * (255 - chroma)) / 255
        r = clamp8(enhancedR * mask + r * (1 - mask))
        g = clamp8(enhancedG * mask + g * (1 - mask))
        b = clamp8(enhancedB * mask + b * (1 - mask))
      }
      if (v.saturation !== 0) {
        const gray = lumaOf(r, g, b)
        r = clamp8(gray + (r - gray) * saturation)
        g = clamp8(gray + (g - gray) * saturation)
        b = clamp8(gray + (b - gray) * saturation)
      }
      if (v.vignette !== 0) {
        // 径向暗角：对角归一 t、幂 1.6（后端 _radial_mask 同式，逐像素直算等价其 256 表放大）
        const x = i % width
        const y = (i - x) / width
        const dx = (x - cx) / cx
        const dy = (y - cy) / cy
        const t = Math.sqrt(dx * dx + dy * dy) / corner
        const factor = Math.max(0, 1 - v.vignette * t ** 1.6)
        r *= factor
        g *= factor
        b *= factor
      }
      data[offset] = clamp8(r)
      data[offset + 1] = clamp8(g)
      data[offset + 2] = clamp8(b)
    }
  }
}
