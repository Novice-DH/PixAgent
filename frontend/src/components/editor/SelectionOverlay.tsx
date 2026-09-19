/** 选区叠加形状（由 CanvasStage 的常驻 <Layer listening={false}> 直接挂载——
 * react-konva 19 要求容器节点在元素树上是 Stage 的直接子级，组件只出形状）：
 * 遮罩图 0.45 透明铺满画布（消费服务端 overlay 资产，前端不重复实现遮罩渲染）
 * + draft 笔迹（宽 = brushWidth 画布坐标、圆角连接；多于 2 点闭合并半透明填充
 * ——预览即服务端将生成的面积语义）+ markers 序号徽标。Stage 无 scale 变换
 * （S11 纪律），形状按屏幕像素绘制即天然屏幕恒定——任何缩放下徽标尺寸不变，
 * 与裁剪手柄同一约定。 */
import { Circle, Group, Image as KonvaImage, Line, Text } from 'react-konva'

import type { SelectionMarker } from '@/stores/editorUi'
import type { StrokePoint } from '@/hooks/useSelectStroke'
import { useCanvasImage } from '@/hooks/useCanvasImage'

interface SelectionOverlayProps {
  maskUrl: string
  markers: SelectionMarker[]
  /** 笔刷拖动期笔迹（归一化坐标），松手后为 null */
  draft: StrokePoint[] | null
  docWidth: number
  docHeight: number
  viewX: number
  viewY: number
  scale: number
  /** 笔刷宽度（画布坐标），来自 lib/brush.brushWidth */
  brushPx: number
}

const MASK_COLOR = '#5f98ad'
const MARKER_RADIUS = 11

export default function SelectionOverlay({
  maskUrl,
  markers,
  draft,
  docWidth,
  docHeight,
  viewX,
  viewY,
  scale,
  brushPx,
}: SelectionOverlayProps) {
  const bitmap = useCanvasImage(maskUrl)
  const toScreen = (point: { x: number; y: number }): [number, number] => [
    viewX + point.x * docWidth * scale,
    viewY + point.y * docHeight * scale,
  ]

  return (
    <>
      {bitmap?.element && (
        <KonvaImage
          image={bitmap.element}
          x={viewX}
          y={viewY}
          width={docWidth * scale}
          height={docHeight * scale}
          opacity={0.45}
        />
      )}
      {draft && draft.length > 0 && (() => {
        const points = draft.flatMap(toScreen)
        return (
          <>
            {draft.length > 2 && (
              <Line points={points} closed fill={`${MASK_COLOR}40`} />
            )}
            <Line
              points={points}
              stroke={`${MASK_COLOR}cc`}
              strokeWidth={brushPx * scale}
              lineCap="round"
              lineJoin="round"
            />
          </>
        )
      })()}
      {markers.map((marker) => {
        const [cx, cy] = toScreen(marker)
        return (
          <Group key={marker.index} x={cx} y={cy}>
            <Circle radius={MARKER_RADIUS} fill={MASK_COLOR} stroke="#ffffff" strokeWidth={1.5} />
            <Text
              text={String(marker.index)}
              width={MARKER_RADIUS * 2}
              height={MARKER_RADIUS * 2}
              x={-MARKER_RADIUS}
              y={-MARKER_RADIUS}
              align="center"
              verticalAlign="middle"
              fontSize={12}
              fontStyle="bold"
              fill="#ffffff"
            />
          </Group>
        )
      })}
    </>
  )
}
