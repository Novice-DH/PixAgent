/** 四步交付条：描述需求 → 挑选方向 → 局部精修 → 导出物料。 */

const STEPS = [
  {
    title: '描述需求',
    description: '用一句话说清商品、场景与想要的氛围。',
  },
  {
    title: '挑选方向',
    description: '四个候选里选最贴近心意的版本。',
  },
  {
    title: '局部精修',
    description: '圈住细节继续改，选区之外不动。',
  },
  {
    title: '导出物料',
    description: '1:1、4:5、9:16 一次出全套。',
  },
]

export default function DeliverySteps() {
  return (
    <section className="border-y border-line bg-soft">
      <div className="mx-auto w-full max-w-5xl px-6 py-14">
        <h2 className="text-center text-2xl font-semibold tracking-tight sm:text-3xl">
          四步，从描述到上线
        </h2>
        <ol className="mt-8 grid gap-6 sm:grid-cols-2 md:grid-cols-4">
          {STEPS.map((step, index) => (
            <li key={step.title} className="flex flex-col gap-2">
              <span className="flex h-8 w-8 items-center justify-center rounded-full bg-brand text-sm font-semibold text-paper">
                {index + 1}
              </span>
              <h3 className="text-sm font-medium">{step.title}</h3>
              <p className="text-sm leading-relaxed text-muted">{step.description}</p>
            </li>
          ))}
        </ol>
      </div>
    </section>
  )
}
