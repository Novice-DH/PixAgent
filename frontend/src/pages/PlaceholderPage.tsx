interface PlaceholderPageProps {
  title: string
  description: string
}

/** 占位页：只传达"该功能在后续期次实现"。 */
export default function PlaceholderPage({ title, description }: PlaceholderPageProps) {
  return (
    <section className="flex min-h-[60vh] flex-col items-center justify-center gap-3 px-6 text-center">
      <h1 className="text-3xl font-semibold tracking-tight">{title}</h1>
      <p className="max-w-md text-sm text-muted">{description}</p>
      <span className="rounded-control bg-soft px-3 py-1 text-xs text-faint shadow-control">
        后续期次实现
      </span>
    </section>
  )
}
