/** 笔刷笔迹收集：ref 累积坐标 + draft state 驱动实时渲染（SelectionOverlay 画预览）。
 * end() 返回完整笔迹并清空——提交与清场的单一出口；cancel 供中断兜底。 */
import { useRef, useState } from 'react'

export interface StrokePoint {
  x: number
  y: number
}

export function useSelectStroke() {
  const pointsRef = useRef<StrokePoint[]>([])
  const [draft, setDraft] = useState<StrokePoint[] | null>(null)

  const begin = (point: StrokePoint) => {
    pointsRef.current = [point]
    setDraft([point])
  }

  const extend = (point: StrokePoint) => {
    pointsRef.current = [...pointsRef.current, point]
    setDraft([...pointsRef.current])
  }

  const end = (): StrokePoint[] | null => {
    const stroke = pointsRef.current
    pointsRef.current = []
    setDraft(null)
    return stroke.length > 0 ? stroke : null
  }

  const cancel = () => {
    pointsRef.current = []
    setDraft(null)
  }

  return { draft, begin, extend, end, cancel }
}
