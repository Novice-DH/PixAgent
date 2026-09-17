/** 创作页：生成表单置顶（消费落地页草稿）+ 已有图片上传 + 素材墙。
 * 提交成功后清空草稿并跳转候选页——任务入口就是这次跳转。 */
import { useNavigate } from 'react-router-dom'

import AssetCard from '@/components/AssetCard'
import GenerateForm from '@/components/GenerateForm'
import ImageDropzone from '@/components/ImageDropzone'
import { errorMessage } from '@/hooks/useAuth'
import { useAssets, useUploadAsset } from '@/hooks/useAssets'
import { useGenerate } from '@/hooks/useRun'
import { readPromptDraft, writePromptDraft } from '@/lib/promptDraft'

export default function CreatePage() {
  const navigate = useNavigate()
  const assetsQuery = useAssets()
  const upload = useUploadAsset()
  const generate = useGenerate()

  const assets = assetsQuery.data ?? []

  return (
    <div className="mx-auto flex w-full max-w-5xl flex-col gap-8 px-6 py-8">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">创作</h1>
        <p className="mt-1 text-sm text-muted">一句话生成商品图，或上传已有图片继续编辑。</p>
      </header>

      <section>
        <GenerateForm
          defaultPrompt={readPromptDraft()}
          pending={generate.isPending}
          onSubmit={(input) =>
            generate.mutate(input, {
              onSuccess: (run) => {
                if (!run) return
                // 提交成功：草稿已消费即清空，任务入口是候选页跳转
                writePromptDraft('')
                navigate(`/candidates/${run.id}`)
              },
            })
          }
        />
        {generate.error && (
          <p role="alert" className="mt-2 text-sm text-danger">
            {errorMessage(generate.error)}
          </p>
        )}
      </section>

      <section>
        <h2 className="mb-3 text-base font-medium">上传已有图片</h2>
        <ImageDropzone disabled={upload.isPending} onFile={(file) => upload.mutate(file)} />
        {upload.error && (
          <p role="alert" className="mt-2 text-sm text-danger">
            {errorMessage(upload.error)}
          </p>
        )}
        {upload.isSuccess && (
          <p className="mt-2 text-sm text-success">上传成功，已加入素材墙。</p>
        )}
      </section>

      <section className="flex flex-col gap-4">
        <h2 className="text-base font-medium">历史素材</h2>

        {assetsQuery.isPending && <p className="text-sm text-muted">正在加载素材…</p>}

        {!assetsQuery.isPending && assets.length === 0 && (
          <p className="rounded-card border border-dashed border-line-strong px-6 py-10 text-center text-sm text-muted">
            先描述画面或上传一张图片
          </p>
        )}

        {assets.length > 0 && (
          <div className="grid grid-cols-2 gap-4 md:grid-cols-3 lg:grid-cols-4">
            {assets.map((asset) => (
              <AssetCard key={asset.id} asset={asset} />
            ))}
          </div>
        )}
      </section>
    </div>
  )
}
