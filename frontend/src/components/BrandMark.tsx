/** 品牌标识单点：ink 底 + accent 双层图层符号；全站唯一品牌图形定义，sm/md 两档，文字可选。 */

const SIZES = {
  sm: { box: 'h-8 w-8', glyph: 'h-4 w-4' },
  md: { box: 'h-11 w-11', glyph: 'h-5.5 w-5.5' },
} as const

export default function BrandMark({
  size = 'md',
  withText = false,
}: {
  size?: keyof typeof SIZES
  withText?: boolean
}) {
  const { box, glyph } = SIZES[size]

  return (
    <span className="inline-flex items-center gap-2.5">
      <span className={`flex ${box} shrink-0 items-center justify-center rounded-control bg-ink`}>
        <svg viewBox="0 0 24 24" fill="none" aria-hidden="true" className={glyph}>
          {/* 图层隐喻：顶层实面 + 底层描边，对应「主体 / 背景」分层编辑 */}
          <path d="M12 4.5l7.5 4L12 12.5l-7.5-4 7.5-4Z" fill="var(--color-accent)" />
          <path
            d="M4.5 14l7.5 4 7.5-4"
            stroke="var(--color-accent)"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
            opacity="0.62"
          />
          <circle cx="18.75" cy="4.5" r="1.5" fill="var(--color-accent)" />
        </svg>
      </span>
      {withText && <span className="text-base font-semibold tracking-tight">AI 修图智能体</span>}
    </span>
  )
}
