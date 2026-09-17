/** 深色 CTA 面板：收束主行动，把访客带回首屏输入面板写下第一句需求。 */

export default function StartBanner({ onCta }: { onCta: () => void }) {
  return (
    <section className="mx-auto w-full max-w-5xl px-6 py-20">
      <div className="relative overflow-hidden rounded-panel bg-dark px-6 py-12 text-center shadow-panel sm:px-12">
        <div
          aria-hidden="true"
          className="pointer-events-none absolute -left-24 -top-24 h-64 w-64 rounded-full bg-brand/25 blur-3xl"
        />
        <div
          aria-hidden="true"
          className="pointer-events-none absolute -bottom-28 -right-16 h-64 w-64 rounded-full bg-accent/15 blur-3xl"
        />

        <h2 className="text-2xl font-semibold tracking-tight text-paper sm:text-3xl">
          第一句需求，现在就能写
        </h2>
        <p className="mx-auto mt-3 max-w-md text-sm leading-relaxed text-paper/70">
          从一句描述到可投放物料，中间不再需要任何设计工具。
        </p>
        <button
          type="button"
          onClick={onCta}
          className="mt-7 rounded-control bg-accent px-6 py-3 text-sm font-semibold text-ink shadow-control transition-colors hover:bg-accent/85"
        >
          写下第一句需求
        </button>
      </div>
    </section>
  )
}
