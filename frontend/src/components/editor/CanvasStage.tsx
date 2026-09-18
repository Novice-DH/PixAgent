/** 画布舞台：按 LayerDocument 只读渲染（骨架期只画 image 层），交互只有平移与缩放。
 * 视图状态来自 canvasView store——按字段订阅（整店订阅 + effect 写回会无限循环）；
 * 文档状态来自服务端——两套"缩放"严格分离。 */
import { useEffect, useRef } from 'react'
import type { KonvaEventObject } from 'konva/lib/Node'
import { Image as KonvaImage, Layer, Rect, Stage } from 'react-konva'

import type { LayerDocument } from '@/api/sessions'
import { useCanvasImage } from '@/hooks/useCanvasImage'
import { useElementSize } from '@/hooks/useElementSize'
import { ZOOM_STEP, useCanvasView } from '@/stores/canvasView'

interface CanvasStageProps {
  sessionId: string
  document: LayerDocument
  imageUrl: string | null
}

export default function CanvasStage({ sessionId, document: doc, imageUrl }: CanvasStageProps) {
  const [containerRef, size] = useElementSize<HTMLDivElement>()
  // 视图状态按字段订阅：动作引用稳定，数值变化才重渲染
  const x = useCanvasView((state) => state.x)
  const y = useCanvasView((state) => state.y)
  const scale = useCanvasView((state) => state.scale)
  const setViewport = useCanvasView((state) => state.setViewport)
  const fit = useCanvasView((state) => state.fit)
  const zoomBy = useCanvasView((state) => state.zoomBy)
  const pan = useCanvasView((state) => state.pan)
  const bitmap = useCanvasImage(imageUrl)
  const fitKeyRef = useRef<string | null>(null)

  useEffect(() => {
    setViewport(size.width, size.height)
  }, [size.width, size.height, setViewport])

  // 自动适应按形状串去重：只有"新进会话 / 画幅变化 / 视口初始化"重置视图；
  // 窗口 resize 不重适应——ResizeObserver 连发回调时，一次多余的重适应
  // 就会把用户手动倍率清零，代价不对等
  useEffect(() => {
    if (!size.width || !size.height) return
    const key = `${sessionId}:${doc.width}x${doc.height}`
    if (fitKeyRef.current === key) return
    fitKeyRef.current = key
    fit(doc.width, doc.height)
  }, [sessionId, doc.width, doc.height, size.width, size.height, fit])

  const handleWheel = (event: KonvaEventObject<WheelEvent>) => {
    event.evt.preventDefault()
    const pointer = event.target.getStage()?.getPointerPosition()
    if (!pointer) return
    const factor = event.evt.deltaY < 0 ? ZOOM_STEP : 1 / ZOOM_STEP
    zoomBy(factor, pointer)
  }

  const syncPan = (event: KonvaEventObject<DragEvent>) => {
    pan(event.target.x(), event.target.y())
  }

  return (
    <div ref={containerRef} className="h-full w-full overflow-hidden bg-canvas">
      {size.width > 0 && size.height > 0 && (
        <Stage
          width={size.width}
          height={size.height}
          draggable
          onWheel={handleWheel}
          onDragMove={syncPan}
          onDragEnd={syncPan}
        >
          {/* 交互全部在 Stage 层（拖拽/滚轮），内容层不响应事件 */}
          <Layer listening={false}>
            <Rect
              x={x}
              y={y}
              width={doc.width * scale}
              height={doc.height * scale}
              fill="#ffffff"
              shadowColor="#1a1f1a"
              shadowOpacity={0.18}
              shadowBlur={28}
              shadowOffsetY={10}
            />
            {doc.layers
              .filter((layer) => layer.visible && layer.kind === 'image')
              .map((layer) => {
                // 骨架期单底图：位图就是当前资产；后续多图层在此按 asset→bitmap 映射扩展
                if (!bitmap) return null
                return (
                  <KonvaImage
                    key={layer.id}
                    image={bitmap}
                    x={x + layer.transform.x * scale}
                    y={y + layer.transform.y * scale}
                    width={layer.width * layer.transform.scale_x * scale}
                    height={layer.height * layer.transform.scale_y * scale}
                  />
                )
              })}
          </Layer>
        </Stage>
      )}
    </div>
  )
}
