/** 落地页：组装层——持有登录态、入口决策与草稿状态；展示组件只接回调。
 * 主 CTA 不再强制注册模式：「免费开始」指向 /auth 默认登录页（对认证期行为的显式替代）。 */
import { useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import CapabilityShowcase from '@/components/landing/CapabilityShowcase'
import DeliverySteps from '@/components/landing/DeliverySteps'
import LandingFooter from '@/components/landing/LandingFooter'
import LandingHeader from '@/components/landing/LandingHeader'
import LandingHero from '@/components/landing/LandingHero'
import StartBanner from '@/components/landing/StartBanner'
import { useCurrentUser } from '@/hooks/useAuth'
import { readPromptDraft, writePromptDraft } from '@/lib/promptDraft'

const COMPOSER_PLACEHOLDER =
  '描述你的商品与场景，例如：把这款白瓷茶具放到原木茶席上，晨光侧逆光，出 1:1 主图'

export default function LandingPage() {
  const { data: user, isPending } = useCurrentUser()
  const navigate = useNavigate()
  // 挂载时回填上次提交留下的草稿
  const [prompt, setPrompt] = useState(readPromptDraft)
  const composerInputRef = useRef<HTMLTextAreaElement>(null)

  // 入口决策在页面层：登录态决定提交按钮文案与跳转目的地
  const entry = user ? { label: '进入工作台', to: '/create' } : { label: '免费开始', to: '/auth' }

  const handleSubmit = () => {
    writePromptDraft(prompt)
    navigate(entry.to)
  }

  // 「上传商品图」占位交互：带去工作台已有的上传素材墙
  const handleAttach = () => navigate('/create')

  const handlePickExample = (example: string) => {
    setPrompt(example)
    composerInputRef.current?.focus()
  }

  const handleBannerCta = () => {
    const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    composerInputRef.current?.scrollIntoView({ behavior: reduceMotion ? 'auto' : 'smooth', block: 'center' })
    composerInputRef.current?.focus({ preventScroll: true })
  }

  return (
    <div className="flex min-h-screen flex-col">
      <LandingHeader user={user ?? null} isPending={isPending} />

      <main className="flex-1">
        <LandingHero
          prompt={prompt}
          onPromptChange={setPrompt}
          onSubmit={handleSubmit}
          onAttach={handleAttach}
          submitLabel={entry.label}
          placeholder={COMPOSER_PLACEHOLDER}
          composerInputRef={composerInputRef}
          onPickExample={handlePickExample}
        />
        <CapabilityShowcase />
        <DeliverySteps />
        <StartBanner onCta={handleBannerCta} />
      </main>

      <LandingFooter />
    </div>
  )
}
