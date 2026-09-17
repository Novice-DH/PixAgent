/** 能力展示：区块头 + 四张能力卡（纯 CSS 示意图 + 方向要点）。 */
import { CandidateGridPreview, LayersPreview, SelectionPreview, SizesPreview } from './previews'

const CAPABILITIES = [
  {
    title: '一句话生成',
    description: '描述商品与场景，一次给出四个候选方向，挑最合适的一张继续打磨。',
    preview: <CandidateGridPreview />,
  },
  {
    title: '主体级编辑',
    description: '圈住主体提需求，改动约束在选区内，背景与构图不受牵连。',
    preview: <SelectionPreview />,
  },
  {
    title: '语义图层',
    description: '主体、背景、文字自动分层，改错一步随时回到上一版。',
    preview: <LayersPreview />,
  },
  {
    title: '物料包交付',
    description: '1:1 主图、4:5 详情、9:16 封面一次导出，主体始终不裁切。',
    preview: <SizesPreview />,
  },
]

export default function CapabilityShowcase() {
  return (
    <section className="mx-auto w-full max-w-5xl px-6 pb-20">
      <div className="mb-8 max-w-2xl">
        <p className="text-sm font-medium text-brand-strong">能力</p>
        <h2 className="mt-1.5 text-2xl font-semibold tracking-tight sm:text-3xl">
          从一句话，到一套可投放的物料
        </h2>
        <p className="mt-2 text-sm leading-relaxed text-muted">
          生成的每一步都围绕商品图的真实工作流：先出方向，再改细节，最后按渠道出全套尺寸。
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        {CAPABILITIES.map((capability) => (
          <article
            key={capability.title}
            className="flex flex-col gap-4 rounded-card border border-line bg-paper p-5 shadow-card"
          >
            {capability.preview}
            <div>
              <h3 className="text-base font-medium">{capability.title}</h3>
              <p className="mt-1 text-sm leading-relaxed text-muted">{capability.description}</p>
            </div>
          </article>
        ))}
      </div>
    </section>
  )
}
