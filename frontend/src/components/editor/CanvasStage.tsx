/** 画布舞台：按 LayerDocument 渲染（image 层），交互=平移缩放 + 图层点选 + 裁剪框 + 前后对比。
 * 几何与服务端拍平共享同一模型：中心原点（x + width/2、offsetX = width/2）——
 * 旋转绕图层中心、负缩放镜像，两端必须逐像素一致，否则所见非所得。
 * 对比模式按"前"侧文档的变换与画幅渲染（双 DocumentLayer），不是简单拉伸原始位图。
 * 视图状态来自 canvasView store；裁剪/对比瞬态与拖动期预览来自 editorUi store。
 *
 * 输入语义（S11）：滚轮/双指=平移，⌘/Ctrl+滚轮与触控板捏合=指针锚缩放（夹取+指数
 * 统一格率），双击=适应；Stage 不做 scale 变换（缩放由各渲染方重算屏幕几何），
 * 所以裁剪手柄/描边/虚线/分割线手柄天然为屏幕恒定尺寸。
 */
import { useEffect, useMemo, useRef } from 'react'
import type Konva from 'konva'
import type { KonvaEventObject } from 'konva/lib/Node'
import { Circle, Group, Image as KonvaImage, Layer, Line, Rect, Stage, Transformer } from 'react-konva'

import type { Layer as DocumentLayer, LayerDocument } from '@/api/sessions'
import { toAdjustPreview } from '@/lib/adjustPreview'
import { useCanvasImage } from '@/hooks/useCanvasImage'
import { useElementSize } from '@/hooks/useElementSize'
import { useCanvasView } from '@/stores/canvasView'
import { useEditorUi, type CropRect as NormalizedCropRect, type LayerPreview } from '@/stores/editorUi'

interface CanvasStageProps {
  sessionId: string
  document: LayerDocument
  /** 对比模式"前"侧文档：按它的变换与画幅渲染（null = 无前文档，对比禁用） */
  previousDocument: LayerDocument | null
  /** asset_id → 签名 URL（图片墙现算，前端只消费） */
  resolveAssetUrl: (assetId: string | null) => string | null
}

const MIN_CROP_PX = 32 // 与后端 MIN_CROP 一致：裁出更小的画布后续链路不接受

/** 单图层渲染：中心原点 + transform 四要素 + opacity——与服务端拍平同一几何。
 * 拖动期预览：layerPreview 命中该层则覆盖对应渲染值（scale 保留翻转符号）；
 * adjustFilters 非 null 且位图 safe（像素可读）时挂逐像素滤镜并按 0.6 像素比缓存。 */
function TransformedLayerImage({
  layer,
  url,
  viewX,
  viewY,
  scale,
  selected = false,
  listening = true,
  previewFilters = null,
  layerPreview,
  onSelect,
}: {
  layer: DocumentLayer
  url: string | null
  viewX: number
  viewY: number
  scale: number
  selected?: boolean
  listening?: boolean
  previewFilters?: ((imageData: ImageData) => void)[] | null
  layerPreview?: LayerPreview | null
  onSelect?: () => void
}) {
  const bitmap = useCanvasImage(url)
  const imageRef = useRef<Konva.Image | null>(null)

  // 预览只命中对应图层；scale 为绝对幅值，翻转方向由文档值的符号保留
  const preview = layerPreview && layerPreview.id === layer.id ? layerPreview : null
  const previewScale = preview?.scale
  const scaleX =
    previewScale !== undefined
      ? Math.sign(layer.transform.scale_x || 1) * previewScale
      : layer.transform.scale_x
  const scaleY =
    previewScale !== undefined
      ? Math.sign(layer.transform.scale_y || 1) * previewScale
      : layer.transform.scale_y
  const opacity = preview?.opacity ?? layer.opacity
  const rotation = preview?.rotation ?? layer.transform.rotation

  // 滤镜走命令式挂载：filters 数组引用稳定，节点缓存只在滤镜/位图/选中态变化时重建
  useEffect(() => {
    const node = imageRef.current
    if (!node || !bitmap) return
    const filters = previewFilters && bitmap.safe ? previewFilters : []
    node.filters(filters)
    if (filters.length > 0) {
      node.cache({ pixelRatio: 0.6 })
    } else {
      node.clearCache()
    }
    node.getLayer()?.batchDraw()
  }, [previewFilters, bitmap, selected])

  if (!bitmap) return null
  return (
    <KonvaImage
      ref={imageRef}
      image={bitmap.element}
      x={viewX + (layer.transform.x + layer.width / 2) * scale}
      y={viewY + (layer.transform.y + layer.height / 2) * scale}
      offsetX={layer.width / 2}
      offsetY={layer.height / 2}
      width={layer.width}
      height={layer.height}
      scaleX={scaleX}
      scaleY={scaleY}
      rotation={rotation}
      opacity={opacity}
      listening={listening}
      onClick={onSelect}
      onTap={onSelect}
      stroke={selected ? '#8fbf4d' : undefined}
      strokeWidth={selected ? 1.5 / scale : 0}
    />
  )
}

export default function CanvasStage({
  sessionId,
  document: doc,
  previousDocument,
  resolveAssetUrl,
}: CanvasStageProps) {
  const [containerRef, size] = useElementSize<HTMLDivElement>()
  // 视图状态按字段订阅：缓动每帧 set，选择器订阅是动画不卡整树的前提
  const x = useCanvasView((state) => state.x)
  const y = useCanvasView((state) => state.y)
  const scale = useCanvasView((state) => state.scale)
  const setViewport = useCanvasView((state) => state.setViewport)
  const fit = useCanvasView((state) => state.fit)
  const zoomByWheel = useCanvasView((state) => state.zoomByWheel)
  const panBy = useCanvasView((state) => state.panBy)
  const pan = useCanvasView((state) => state.pan)
  const fitKeyRef = useRef<string | null>(null)
  const fitSessionRef = useRef<string | null>(null)

  const cropOpen = useEditorUi((state) => state.cropOpen)
  const cropRatio = useEditorUi((state) => state.cropRatio)
  const cropRect = useEditorUi((state) => state.cropRect)
  const setCropRect = useEditorUi((state) => state.setCropRect)
  const compareOpen = useEditorUi((state) => state.compareOpen)
  const compareAt = useEditorUi((state) => state.compareAt)
  const setCompareAt = useEditorUi((state) => state.setCompareAt)
  const selectedLayerId = useEditorUi((state) => state.selectedLayerId)
  const selectLayer = useEditorUi((state) => state.selectLayer)
  const adjustPreviewValues = useEditorUi((state) => state.adjustPreview)
  const layerPreview = useEditorUi((state) => state.layerPreview)

  // 滤镜数组 useMemo：数值不变保持同一引用，节点缓存不重建
  const adjustFilters = useMemo<((imageData: ImageData) => void)[] | null>(
    () => {
      const filter = toAdjustPreview(adjustPreviewValues)
      return filter ? [filter] : null
    },
    [adjustPreviewValues],
  )

  // 交互互斥：裁剪禁平移与缩放；对比禁平移
  const stageDraggable = !cropOpen && !compareOpen

  useEffect(() => {
    setViewport(size.width, size.height)
  }, [size.width, size.height, setViewport])

  // 自动适应按形状串去重（只含画幅，视口变化由 setViewport 中心锚定吸收）：
  // 新进会话 = 首次落位不动画；同会话画幅变化 = 平滑归位
  useEffect(() => {
    if (!size.width || !size.height) return
    const key = `${sessionId}:${doc.width}x${doc.height}`
    if (fitKeyRef.current === key) return
    const sessionChanged = fitSessionRef.current !== sessionId
    fitKeyRef.current = key
    fitSessionRef.current = sessionId
    fit(doc.width, doc.height, { animate: !sessionChanged })
  }, [sessionId, doc.width, doc.height, size.width, size.height, fit])

  const handleWheel = (event: KonvaEventObject<WheelEvent>) => {
    event.evt.preventDefault()
    if (cropOpen) return // 裁剪模式禁用缩放与平移
    // 触控板捏合被浏览器报成 ctrlKey 滚轮事件，正好落进缩放分支
    if (event.evt.ctrlKey || event.evt.metaKey) {
      const pointer = event.target.getStage()?.getPointerPosition()
      if (!pointer) return
      zoomByWheel(event.evt.deltaY, pointer)
    } else if (!compareOpen) {
      panBy(-event.evt.deltaX, -event.evt.deltaY)
    }
  }

  // 只消费 Stage 自身的拖拽（平移）：裁剪框/对比手柄的 dragmove 会冒泡到 Stage，
  // 不加守卫会把视图原点写成子节点坐标（画布瞬移）
  const syncPan = (event: KonvaEventObject<DragEvent>) => {
    if (event.target !== event.target.getStage()) return
    pan(event.target.x(), event.target.y())
  }

  const handleLayerClick = (layerId: string) => {
    if (!cropOpen && !compareOpen) selectLayer(layerId)
  }

  const imageLayers = doc.layers.filter((layer) => layer.visible && layer.kind === 'image')

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

  // 拖动进行中实时夹取在画布内：越界立即弹回，不等松手
  const handleCropDragMove = (event: KonvaEventObject<DragEvent>) => {
    const node = event.target
    if (!cropPixel) return
    const px = Math.min(Math.max(node.x(), docX), docX + docW - cropPixel.width)
    const py = Math.min(Math.max(node.y(), docY), docY + docH - cropPixel.height)
    if (node.x() !== px || node.y() !== py) {
      node.position({ x: px, y: py })
    }
  }

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

  // 对比分割线的屏内像素坐标；圆点手柄在画布内拖动改分割位置
  const splitX = docX + compareAt * docW
  const handleY = docY + docH / 2
  const shade = 'rgba(15, 18, 16, 0.55)'

  return (
    <div
      ref={containerRef}
      className={`relative h-full w-full overflow-hidden bg-canvas ${
        cropOpen || compareOpen ? '' : 'cursor-grab active:cursor-grabbing'
      }`}
    >
      {size.width > 0 && size.height > 0 && (
        <Stage
          width={size.width}
          height={size.height}
          draggable={stageDraggable}
          onWheel={handleWheel}
          onDragMove={syncPan}
          onDragEnd={syncPan}
          onDblClick={() => {
            if (!cropOpen) fit(doc.width, doc.height)
          }}
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
            {imageLayers.map((layer) => (
              <TransformedLayerImage
                key={layer.id}
                layer={layer}
                url={resolveAssetUrl(layer.asset_id)}
                viewX={x}
                viewY={y}
                scale={scale}
                selected={selectedLayerId === layer.id}
                previewFilters={adjustFilters}
                layerPreview={layerPreview}
                onSelect={() => handleLayerClick(layer.id)}
              />
            ))}
          </Layer>

          {/* 对比模式：左半按"前"侧文档渲染（白底 + 各图层变换），右半露出当前画布；
            分割线与圆点手柄画在画布内，手柄拖动改变分割位置 */}
          {compareOpen && previousDocument && (
            <Layer>
              <Group listening={false} clipX={docX} clipY={docY} clipWidth={splitX - docX} clipHeight={docH}>
                <Rect
                  x={docX}
                  y={docY}
                  width={previousDocument.width * scale}
                  height={previousDocument.height * scale}
                  fill="#ffffff"
                />
                {previousDocument.layers
                  .filter((layer) => layer.visible && layer.kind === 'image')
                  .map((layer) => (
                    <TransformedLayerImage
                      key={layer.id}
                      layer={layer}
                      url={resolveAssetUrl(layer.asset_id)}
                      viewX={x}
                      viewY={y}
                      scale={scale}
                      listening={false}
                    />
                  ))}
              </Group>
              <Line
                points={[splitX, docY, splitX, docY + docH]}
                stroke="#d9ff6e"
                strokeWidth={2}
                listening={false}
              />
              <Circle
                x={splitX}
                y={handleY}
                radius={7}
                fill="#d9ff6e"
                stroke="#171917"
                strokeWidth={1.5}
                draggable
                dragBoundFunc={(position) => ({
                  x: Math.min(docX + docW, Math.max(docX, position.x)),
                  y: handleY,
                })}
                onDragMove={(event) => setCompareAt((event.target.x() - docX) / docW)}
                onMouseEnter={(event) => {
                  const container = event.target.getStage()?.container()
                  if (container) container.style.cursor = 'ew-resize'
                }}
                onMouseLeave={(event) => {
                  const container = event.target.getStage()?.container()
                  if (container) container.style.cursor = ''
                }}
              />
            </Layer>
          )}

          {/* 裁剪模式：四块半透明遮罩 + 虚线框（拖动/缩放，rotate 关闭）。
            手柄/描边/虚线以屏幕像素绘制（Stage 无 scale 变换），任何缩放下尺寸恒定 */}
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
              <Rect
                x={docX}
                y={cropPixel.y}
                width={cropPixel.x - docX}
                height={cropPixel.height}
                fill={shade}
              />
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
                onDragMove={handleCropDragMove}
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
                // 拖角缩放实时夹取：边界与 MIN_CROP 同步生效，越界立即停住；
                // 锁定比例时以更受限的一轴恢复纵横比，避免触界后比例被打破
                boundBoxFunc={(_oldBox, newBox) => {
                  let width = Math.min(docW, Math.max(MIN_CROP_PX, newBox.width))
                  let height = Math.min(docH, Math.max(MIN_CROP_PX, newBox.height))
                  if (cropRatio !== 'free') {
                    const [ratioW, ratioH] = cropRatio.split(':').map(Number) as [number, number]
                    const target = ratioW / ratioH
                    if (width / height > target) {
                      width = height * target
                    } else {
                      height = width / target
                    }
                  }
                  const boxX = Math.min(Math.max(newBox.x, docX), docX + docW - width)
                  const boxY = Math.min(Math.max(newBox.y, docY), docY + docH - height)
                  return { ...newBox, x: boxX, y: boxY, width, height }
                }}
              />
            </Layer>
          )}
        </Stage>
      )}
    </div>
  )
}
