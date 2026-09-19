/** 编辑器瞬态 UI store（zustand，纯瞬态不持久化）：图层选择、裁剪框、对比、右栏面板、
 * 拖动期实时预览。只放"刷新即忘"的界面状态——画布文档与视图缩放分属服务端与
 * canvasView，绝不混入。预览是渲染态不落数据：文档回传新值即撤。 */
import { create } from 'zustand'

export type EditorPanel = 'layers' | 'adjust' | 'background' | 'expand' | null

/** 调色拖动期预览：九参数当前值（与 lib/adjustPreview 对齐，sharpness/clarity 不参与） */
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

/** 图层变换拖动期预览：命中 id 的层用这些值覆盖渲染（scale 为绝对幅值，翻转由文档符号提供） */
export interface LayerPreview {
  id: string
  opacity?: number
  scale?: number
  rotation?: number
}

/** 裁剪比例：free 为自由框，其余锁定纵横比（与后端 Ratio 对齐）。 */
export type CropRatio = 'free' | '1:1' | '4:5' | '9:16' | '16:9'

export interface CropRect {
  x: number
  y: number
  width: number
  height: number
}

export const CROP_RATIOS: readonly Exclude<CropRatio, 'free'>[] = ['1:1', '4:5', '9:16', '16:9']

/** 按比例在画布内居中适配初始框；自由比例内缩 8%。返回归一化矩形。 */
export function initialCropRect(ratio: CropRatio, docWidth: number, docHeight: number): CropRect {
  if (ratio === 'free') {
    return { x: 0.08, y: 0.08, width: 0.84, height: 0.84 }
  }
  const [w, h] = ratio.split(':').map(Number) as [number, number]
  const target = w / h
  const canvasAspect = docWidth / docHeight
  let width = 1
  let height = 1
  if (canvasAspect > target) {
    width = target / canvasAspect
  } else {
    height = canvasAspect / target
  }
  return {
    x: (1 - width) / 2,
    y: (1 - height) / 2,
    width,
    height,
  }
}

interface EditorUiState {
  selectedLayerId: string | null
  cropOpen: boolean
  cropRatio: CropRatio
  cropRect: CropRect | null
  compareOpen: boolean
  /** 分割线位置（0–1，默认居中） */
  compareAt: number
  panel: EditorPanel
  adjustPreview: AdjustPreviewValues | null
  layerPreview: LayerPreview | null
  selectLayer: (id: string | null) => void
  openCrop: (docWidth: number, docHeight: number) => void
  setCropRatio: (ratio: CropRatio, docWidth: number, docHeight: number) => void
  setCropRect: (rect: CropRect) => void
  closeCrop: () => void
  openCompare: () => void
  setCompareAt: (at: number) => void
  closeCompare: () => void
  setPanel: (panel: EditorPanel) => void
  setAdjustPreview: (values: AdjustPreviewValues | null) => void
  setLayerPreview: (preview: LayerPreview | null) => void
}

export const useEditorUi = create<EditorUiState>((set) => ({
  selectedLayerId: null,
  cropOpen: false,
  cropRatio: 'free',
  cropRect: null,
  compareOpen: false,
  compareAt: 0.5,
  panel: 'layers',
  adjustPreview: null,
  layerPreview: null,
  selectLayer: (id) => set({ selectedLayerId: id }),
  openCrop: (docWidth, docHeight) =>
    set((state) => ({
      // 裁剪与对比互斥：开一个关另一个
      cropOpen: true,
      compareOpen: false,
      panel: state.panel,
      cropRatio: state.cropOpen ? state.cropRatio : 'free',
      cropRect: initialCropRect(state.cropOpen ? state.cropRatio : 'free', docWidth, docHeight),
    })),
  setCropRatio: (ratio, docWidth, docHeight) =>
    // 锁定纵横比切换时重置框：新比例重新居中适配
    set({ cropRatio: ratio, cropRect: initialCropRect(ratio, docWidth, docHeight) }),
  setCropRect: (rect) => set({ cropRect: rect }),
  closeCrop: () => set({ cropOpen: false, cropRect: null }),
  openCompare: () => set((state) => ({ compareOpen: true, cropOpen: false, panel: state.panel })),
  setCompareAt: (at) => set({ compareAt: Math.min(1, Math.max(0, at)) }),
  closeCompare: () => set({ compareOpen: false }),
  setPanel: (panel) =>
    set((state) => ({ panel: state.panel === panel ? null : panel, cropOpen: false, compareOpen: false })),
  setAdjustPreview: (values) => set({ adjustPreview: values }),
  setLayerPreview: (preview) => set({ layerPreview: preview }),
}))
