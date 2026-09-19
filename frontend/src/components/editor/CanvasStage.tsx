/** 画布舞台：按 LayerDocument 渲染（image 层），交互=平移缩放 + 图层点选 + 裁剪框 + 前后对比。
 * 几何与服务端拍平共享同一模型：中心原点（x + width/2、offsetX = width/2）——
 * 旋转绕图层中心、负缩放镜像，两端必须逐像素一致，否则所见非所得。
 * 视图状态来自 canvasView store；裁剪/对比瞬态来自 editorUi store。 */
import { useEffect, useRef } from 'react'
import type Konva from 'konva'
import type { KonvaEventObject } from 'konva/lib/Node'
import { Group, Image as KonvaImage, Layer, Line, Rect, Stage, Transformer } from 'react-konva'

import type { LayerDocument } from '@/api/sessions'
import { useCanvasImage } from '@/hooks/useCanvasImage'
import { useElementSize } from '@/hooks/useElementSize'
import { ZOOM_STEP, useCanvasView } from '@/stores/canvasView'
import { useEditorUi, type CropRect as NormalizedCropRect } from '@/stores/editorUi'

interface CanvasStageProps {
  sessionId: string
  document: LayerDocument
  imageUrl: string | null
  /** 对比模式"前"侧位图（previous_document 的当前资产） */
  previousImageUrl: string | null
}

const MIN_CROP_PX = 32 // 与后端 MIN_CROP 一致：裁出更小的画布后续链路不接受

export default function CanvasStage({
  sessionId,
  document: doc,
  imageUrl,
  previousImageUrl,
}: CanvasStageProps) {
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
  const previousBitmap = useCanvasImage(previousImageUrl)
  const fitKeyRef = useRef<string | null>(null)

  const cropOpen = useEditorUi((state) => state.cropOpen)
  const cropRatio = useEditorUi((state) => state.cropRatio)
  const cropRect = useEditorUi((state) => state.cropRect)
  const setCropRect = useEditorUi((state) => state.setCropRect)
  const compareOpen = useEditorUi((state) => state.compareOpen)
  const compareAt = useEditorUi((state) => state.compareAt)
  const setCompareAt = useEditorUi((state) => state.setCompareAt)
  const selectedLayerId = useEditorUi((state) => state.selectedLayerId)
  const selectLayer = useEditorUi((state) => state.selectLayer)

  // 交互互斥：裁剪禁平移与缩放；对比禁平移
  const stageDraggable = !cropOpen && !compareOpen

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
    if (cropOpen) return // 裁剪模式禁用缩放
    const pointer = event.target.getStage()?.getPointerPosition()
    if (!pointer) return
    const factor = event.evt.deltaY < 0 ? ZOOM_STEP : 1 / ZOOM_STEP
    zoomBy(factor, pointer)
  }

  const syncPan = (event: KonvaEventObject<DragEvent>) => {
    pan(event.target.x(), event.target.y())
  }

  const handleLayerClick = (layerId: string) => {
    if (!cropOpen && !compareOpen) selectLayer(layerId)
  }

  // ---- 裁剪框几何：编辑态以像素矩形工作，提交前归一化 ----
  const docX = x
  const docY = y
  const docW = doc.width * scale
  const docH = doc.height * scale
  const cropPixel = cropRect
    ? {
        x: docX + cropRect.x * docW,
        y: docY + cropRect.y * docH,
        width: cropRect.width * docW,
        height: cropRect.height * docH,
      }
    : null

  const cropFrameRef = useRef<Konva.Rect | null>(null)
  const transformerRef = useRef<Konva.Transformer | null>(null)

  // Transformer 挂载与比例锁定（锁定纵横比 = 比例非自由）
  useEffect(() => {
    const transformer = transformerRef.current
    if (!transformer) return
    if (cropOpen && cropFrameRef.current) {
      transformer.nodes([cropFrameRef.current])
      transformer.keepRatio(cropRatio !== 'free')
      transformer.getLayer()?.batchDraw()
    } else {
      transformer.nodes([])
    }
  }, [cropOpen, cropRatio, cropPixel?.x, cropPixel?.y, cropPixel?.width, cropPixel?.height])

  // transformEnd：把 scale 折算回宽高并归一，钳回画布边界 + MIN_CROP 下限
  const handleCropTransformEnd = () => {
    const node = cropFrameRef.current
    if (!node) return
    const widthPx = Math.max(MIN_CROP_PX, node.width() * node.scaleX())
    const heightPx = Math.max(MIN_CROP_PX, node.height() * node.scaleY())
    const px = Math.min(Math.max(node.x(), docX), docX + docW - widthPx)
    const py = Math.min(Math.max(node.y(), docY), docY + docH - heightPx)
    node.scaleX(1)
    node.scaleY(1)
    const normalized: NormalizedCropRect = {
      x: (px - docX) / docW,
      y: (py - docY) / docH,
      width: Math.min(widthPx / docW, 1 - (px - docX) / docW),
      height: Math.min(heightPx / docH, 1 - (py - docY) / docH),
    }
    setCropRect(normalized)
  }

  const handleCropDragEnd = (event: KonvaEventObject<DragEvent>) => {
    const node = event.target
    if (!cropPixel) return
    const px = Math.min(Math.max(node.x(), docX), docX + docW - cropPixel.width)
    const py = Math.min(Math.max(node.y(), docY), docY + docH - cropPixel.height)
    node.position({ x: px, y: py })
    setCropRect({
      x: (px - docX) / docW,
      y: (py - docY) / docH,
      width: cropRect!.width,
      height: cropRect!.height,
    })
  }

  // 对比分割线的屏内像素坐标
  const splitX = docX + compareAt * docW
  const shade = 'rgba(15, 18, 16, 0.55)'

  return (
    <div ref={containerRef} className="relative h-full w-full overflow-hidden bg-canvas">
      {size.width > 0 && size.height > 0 && (
        <Stage
          width={size.width}
          height={size.height}
          draggable={stageDraggable}
          onWheel={handleWheel}
          onDragMove={syncPan}
          onDragEnd={syncPan}
        >
          {/* 裁剪/对比打开时内容层不响应事件，交互全部让给裁剪框 */}
          <Layer listening={!cropOpen && !compareOpen}>
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
                // 中心原点渲染：与服务端拍平同一几何（旋转绕图层中心、负缩放镜像）
                if (!bitmap) return null
                return (
                  <KonvaImage
                    key={layer.id}
                    image={bitmap}
                    x={x + (layer.transform.x + layer.width / 2) * scale}
                    y={y + (layer.transform.y + layer.height / 2) * scale}
                    offsetX={layer.width / 2}
                    offsetY={layer.height / 2}
                    width={layer.width}
                    height={layer.height}
                    scaleX={layer.transform.scale_x}
                    scaleY={layer.transform.scale_y}
                    rotation={layer.transform.rotation}
                    opacity={layer.opacity}
                    onClick={() => handleLayerClick(layer.id)}
                    onTap={() => handleLayerClick(layer.id)}
                    stroke={selectedLayerId === layer.id ? '#8fbf4d' : undefined}
                    strokeWidth={selectedLayerId === layer.id ? 1.5 / scale : 0}
                  />
                )
              })}
          </Layer>

          {/* 对比模式：左右分屏双文档，底部滑杆拖动分割线 */}
          {compareOpen && previousBitmap && (
            <Layer listening={false}>
              <Group clipX={docX} clipY={docY} clipWidth={splitX - docX} clipHeight={docH}>
                <KonvaImage image={previousBitmap} x={docX} y={docY} width={docW} height={docH} />
              </Group>
              <Group
                clipX={splitX}
                clipY={docY}
                clipWidth={docX + docW - splitX}
                clipHeight={docH}
              >
                {bitmap && (
                  <KonvaImage image={bitmap} x={docX} y={docY} width={docW} height={docH} />
                )}
              </Group>
              <Line
                points={[splitX, docY, splitX, docY + docH]}
                stroke="#d9ff6e"
                strokeWidth={2}
              />
            </Layer>
          )}

          {/* 裁剪模式：四块半透明遮罩 + 虚线框（拖动/缩放，rotate 关闭） */}
          {cropOpen && cropPixel && (
            <Layer listening>
              <Rect x={docX} y={docY} width={docW} height={cropPixel.y - docY} fill={shade} />
              <Rect
                x={docX}
                y={cropPixel.y + cropPixel.height}
                width={docW}
                height={docY + docH - (cropPixel.y + cropPixel.height)}
                fill={shade}
              />
              <Rect x={docX} y={cropPixel.y} width={cropPixel.x - docX} height={cropPixel.height} fill={shade} />
              <Rect
                x={cropPixel.x + cropPixel.width}
                y={cropPixel.y}
                width={docX + docW - (cropPixel.x + cropPixel.width)}
                height={cropPixel.height}
                fill={shade}
              />
              <Rect
                ref={cropFrameRef}
                x={cropPixel.x}
                y={cropPixel.y}
                width={cropPixel.width}
                height={cropPixel.height}
                draggable
                onDragEnd={handleCropDragEnd}
                onTransformEnd={handleCropTransformEnd}
                fill="rgba(0,0,0,0.01)"
                stroke="#d9ff6e"
                strokeWidth={1.5}
                dash={[6, 4]}
              />
              <Transformer
                ref={transformerRef}
                rotateEnabled={false}
                flipEnabled={false}
                anchorSize={8}
                anchorCornerRadius={2}
                borderStroke="#d9ff6e"
                boundBoxFunc={(_oldBox, newBox) => ({
                  ...newBox,
                  width: Math.max(MIN_CROP_PX, newBox.width),
                  height: Math.max(MIN_CROP_PX, newBox.height),
                })}
              />
            </Layer>
          )}
        </Stage>
      )}

      {compareOpen && (
        <input
          type="range"
          min={0}
          max={1}
          step={0.01}
          value={compareAt}
          aria-label="对比分割线"
          onChange={(event) => setCompareAt(Number(event.target.value))}
          className="absolute bottom-4 left-1/2 w-3/5 max-w-96 -translate-x-1/2 accent-brand"
        />
      )}
    </div>
  )
}
