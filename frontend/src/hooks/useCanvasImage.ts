/** 签名 URL → 位图：先带 crossOrigin 尝试可读像素的安全加载（滤镜预览的前提），
 * 失败降级普通加载并标记 safe=false——画面照常显示，但 tainted canvas 读像素会抛
 * SecurityError，故不挂滤镜。显示是底线、滤镜预览是增强，safe 一个布尔承载分级线。
 *
 * 换源保留上一张位图直至新图 onload（S11 对 S8「URL 变更返回空」的反转）：
 * 换当前图是低频显式动作，闪白比短暂残留旧图更伤；「解码期间误认」的风险
 * 由 URL 键控与加载完成时整体替换覆盖。卸载时摘除回调防止迟到的 setState。
 */
import { useEffect, useMemo, useState } from 'react'

export interface CanvasBitmap {
  element: HTMLImageElement
  /** crossOrigin 加载成功 = 像素可读，滤镜预览可用 */
  safe: boolean
}

interface DecodedBitmap extends CanvasBitmap {
  url: string
}

export function useCanvasImage(url: string | null): CanvasBitmap | null {
  const [decoded, setDecoded] = useState<DecodedBitmap | null>(null)

  useEffect(() => {
    if (!url) return
    let cancelled = false
    let current: HTMLImageElement | null = null

    const load = (withCrossOrigin: boolean) => {
      const element = new window.Image()
      current = element
      if (withCrossOrigin) element.crossOrigin = 'anonymous'
      element.onload = () => {
        if (!cancelled) setDecoded({ url, element, safe: withCrossOrigin })
      }
      element.onerror = () => {
        // 签名 URL 未配 CORS 时 crossOrigin 加载直接失败——降级普通加载保显示
        if (withCrossOrigin && !cancelled) load(false)
      }
      element.src = url
    }

    load(true)
    return () => {
      cancelled = true
      if (current) current.onload = null
    }
  }, [url])

  return useMemo(
    () => (decoded ? { element: decoded.element, safe: decoded.safe } : null),
    [decoded],
  )
}
