/** Hero：光晕 + 网格底纹 + 标题关键词高亮 + 需求输入面板 + 场景 chips + 信任行。
 * 首屏元素自上而下交错浮现（40–440ms）；chips 只回填文案并聚焦，提交目的地由页面层决定。 */
import type { RefObject } from 'react'

import PromptComposer from './PromptComposer'

const EXAMPLES = [
  {
    label: '商品主图',
    prompt: '米白陶瓷马克杯，纯色背景柔和顶光，商品主体居中，出 1:1 主图',
  },
  {
    label: '场景氛围图',
    prompt: '同款马克杯摆在原木书桌上，午后窗光斜照、浅景深，出 4:5 场景图',
  },
  {
    label: '模特上身',
    prompt: '亚麻衬衫由模特上身，街道背景自然光、半身构图，出 4:5 模特图',
  },
  {
    label: '促销海报',
    prompt: '头戴式耳机为主体的促销海报，深色背景霓虹光效、顶部留标题位，出 1:1 海报',
  },
  {
    label: '多尺寸物料',
    prompt: '香薰蜡烛放在浴室台面，晨光氛围、主体保持完整，一次导出 1:1、4:5、9:16',
  },
]

const TRUST_ITEMS = ['无需设计经验', '支持 JPG·PNG·WebP', '1:1·4:5·9:16 一次导出']

const RISE_STAGGER = {
  badge: { animationDelay: '40ms' },
  title: { animationDelay: '120ms' },
  subcopy: { animationDelay: '200ms' },
  composer: { animationDelay: '280ms' },
  chips: { animationDelay: '360ms' },
  trust: { animationDelay: '440ms' },
} as const

type LandingHeroProps = {
  prompt: string
  onPromptChange: (value: string) => void
  onSubmit: () => void
  onAttach: () => void
  submitLabel: string
  placeholder: string
  composerInputRef: RefObject<HTMLTextAreaElement | null>
  onPickExample: (prompt: string) => void
}

export default function LandingHero({
  prompt,
  onPromptChange,
  onSubmit,
  onAttach,
  submitLabel,
  placeholder,
  composerInputRef,
  onPickExample,
}: LandingHeroProps) {
  return (
    <section className="relative bg-glow">
      <div aria-hidden="true" className="pointer-events-none absolute inset-0 bg-grid" />

      <div className="relative mx-auto flex w-full max-w-4xl flex-col items-center px-6 pb-16 pt-16 text-center sm:pt-20">
        <p
          className="animate-rise rounded-control bg-brand-soft px-3 py-1 text-sm text-brand-strong"
          style={RISE_STAGGER.badge}
        >
          面向电商运营与内容创作者
        </p>

        <h1
          className="animate-rise mt-5 text-3xl font-semibold leading-tight tracking-tight sm:text-4xl"
          style={RISE_STAGGER.title}
        >
          {/* 高亮块叠于关键词后方、覆盖整个字高——CJK 字身占满字框，只划中线会像删除线 */}
          <span className="relative inline-block">
            <span
              aria-hidden="true"
              className="absolute inset-x-[-6%] inset-y-[3%] -skew-x-6 bg-accent/60"
            />
            <span className="relative">一句话</span>
          </span>
          ，生成可直接投放的商品图
        </h1>

        <p
          className="animate-rise mt-4 max-w-xl text-base leading-relaxed text-muted"
          style={RISE_STAGGER.subcopy}
        >
          文生图起步，上传图片继续对话式编辑；抠图、换背景、局部修改与多尺寸导出自动串联，
          产出电商与营销物料。
        </p>

        <div className="animate-rise mt-8 w-full max-w-2xl" style={RISE_STAGGER.composer}>
          <PromptComposer
            value={prompt}
            onChange={onPromptChange}
            onSubmit={onSubmit}
            onAttach={onAttach}
            submitLabel={submitLabel}
            placeholder={placeholder}
            inputRef={composerInputRef}
          />
        </div>

        <div
          className="animate-rise mt-5 flex flex-wrap items-center justify-center gap-2"
          style={RISE_STAGGER.chips}
        >
          {EXAMPLES.map((example) => (
            <button
              key={example.label}
              type="button"
              onClick={() => onPickExample(example.prompt)}
              className="rounded-full border border-line-strong bg-paper/80 px-3.5 py-1.5 text-xs font-medium text-muted transition-colors hover:border-brand hover:text-brand-strong"
            >
              {example.label}
            </button>
          ))}
        </div>

        <ul
          className="animate-rise mt-6 flex flex-wrap items-center justify-center gap-x-5 gap-y-2 text-xs text-muted"
          style={RISE_STAGGER.trust}
        >
          {TRUST_ITEMS.map((item) => (
            <li key={item} className="flex items-center gap-1.5">
              <svg
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2.2"
                aria-hidden="true"
                className="h-3.5 w-3.5 text-success"
              >
                <path d="M5 12.5l4.5 4.5L19 7.5" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
              {item}
            </li>
          ))}
        </ul>
      </div>
    </section>
  )
}
