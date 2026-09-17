/** 四张能力示意图：纯 CSS 绘制、零图片资源，只作视觉说明；对辅助技术整体隐藏，语义由卡片文本承载。 */

/** 一句话生成：2×2 候选宫格，其一选中带勾。 */
export function CandidateGridPreview() {
  return (
    <div
      aria-hidden="true"
      className="grid aspect-[16/10] grid-cols-2 gap-2 rounded-control bg-canvas p-2.5"
    >
      <div className="relative rounded-control border-2 border-brand bg-brand-soft">
        <span className="absolute right-1.5 top-1.5 flex h-4 w-4 items-center justify-center rounded-full bg-brand">
          <span className="h-1.5 w-2.5 -translate-y-px -rotate-45 border-b-2 border-r-2 border-paper" />
        </span>
      </div>
      <div className="rounded-control border border-line bg-paper/80" />
      <div className="rounded-control border border-line bg-paper/80" />
      <div className="rounded-control border border-line bg-paper/80" />
    </div>
  )
}

/** 主体级编辑：虚线选区 + 四角手柄 + 指令气泡。 */
export function SelectionPreview() {
  return (
    <div aria-hidden="true" className="relative aspect-[16/10] rounded-control bg-canvas">
      <div className="absolute left-[16%] top-[14%] h-[60%] w-[52%] border-2 border-dashed border-brand">
        <span className="absolute -left-1 -top-1 h-2 w-2 rounded-xs border border-brand bg-paper" />
        <span className="absolute -right-1 -top-1 h-2 w-2 rounded-xs border border-brand bg-paper" />
        <span className="absolute -bottom-1 -left-1 h-2 w-2 rounded-xs border border-brand bg-paper" />
        <span className="absolute -bottom-1 -right-1 h-2 w-2 rounded-xs border border-brand bg-paper" />
      </div>
      <div className="absolute bottom-[10%] left-[34%] rounded-control bg-ink px-2.5 py-1.5 text-[10px] leading-none text-paper shadow-control">
        把瓶子换成琥珀色
      </div>
    </div>
  )
}

/** 语义图层：文字·卖点 / 主体·商品 / 背景·场景 三层堆叠。 */
export function LayersPreview() {
  const layers = [
    { label: '文字 · 卖点', className: 'left-[8%] top-[10%] bg-paper' },
    { label: '主体 · 商品', className: 'left-[16%] top-[38%] bg-brand-soft' },
    { label: '背景 · 场景', className: 'left-[24%] top-[66%] bg-soft' },
  ]

  return (
    <div aria-hidden="true" className="relative aspect-[16/10] rounded-control bg-canvas">
      {layers.map((layer) => (
        <div
          key={layer.label}
          className={`absolute flex h-[24%] w-[64%] items-center rounded-control border border-line px-3 text-[10px] font-medium text-muted shadow-control ${layer.className}`}
        >
          {layer.label}
        </div>
      ))}
    </div>
  )
}

/** 物料包交付：1:1 / 4:5 / 9:16 三尺寸画框，主体不裁切。 */
export function SizesPreview() {
  const frames = [
    { label: '1:1', ratio: 'aspect-square' },
    { label: '4:5', ratio: 'aspect-[4/5]' },
    { label: '9:16', ratio: 'aspect-[9/16]' },
  ]

  return (
    <div
      aria-hidden="true"
      className="flex aspect-[16/10] items-center justify-center gap-3 rounded-control bg-canvas"
    >
      {frames.map((frame) => (
        <div
          key={frame.label}
          className={`flex h-[82%] ${frame.ratio} items-center justify-center rounded-control border-2 border-brand bg-paper text-[10px] font-medium text-brand-strong`}
        >
          {frame.label}
        </div>
      ))}
    </div>
  )
}
