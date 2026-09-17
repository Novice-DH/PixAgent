/** 页脚：品牌标识 + 一句话说明。 */
import BrandMark from '@/components/BrandMark'

export default function LandingFooter() {
  return (
    <footer className="border-t border-line bg-paper">
      <div className="mx-auto flex w-full max-w-5xl flex-col items-center justify-between gap-3 px-6 py-6 text-sm text-muted sm:flex-row">
        <BrandMark size="sm" withText />
        <p>一句话，生成可直接投放的商品图</p>
      </div>
    </footer>
  )
}
