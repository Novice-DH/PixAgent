/** 签名 URL → 位图：解码完成才返回。
 * 按 URL 键派生：URL 变更期间返回空（避免新图解码期间残留上一张）；
 * 卸载时摘除 onload 防止迟到的 setState。 */
import { useEffect, useState } from 'react'

export function useCanvasImage(url: string | null): HTMLImageElement | null {
  const [decoded, setDecoded] = useState<{ url: string; image: HTMLImageElement } | null>(null)

  useEffect(() => {
    if (!url) return
    const element = new window.Image()
    let cancelled = false
    element.onload = () => {
      if (!cancelled) setDecoded({ url, image: element })
    }
    element.src = url
    return () => {
      cancelled = true
      element.onload = null
    }
  }, [url])

  return decoded && decoded.url === url ? decoded.image : null
}
