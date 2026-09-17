/** 创作页：上传入口 + 历史素材墙。生成本身是下一期——本期只有上传与素材墙。 */
import { errorMessage } from '@/hooks/useAuth'
import { useAssets, useUploadAsset } from '@/hooks/useAssets'

import AssetCard from '@/components/AssetCard'
import ImageDropzone from '@/components/ImageDropzone'

export default function CreatePage() {
  const assetsQuery = useAssets()
  const upload = useUploadAsset()

  const assets = assetsQuery.data ?? []

  return (
    <div className="mx-auto flex w-full max-w-5xl flex-col gap-8 px-6 py-8">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">创作</h1>
        <p className="mt-1 text-sm text-muted">上传商品图片，为后续生成与编辑准备素材。</p>
      </header>

      <section>
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
            还没有素材——上传第一张图片，开始你的创作。
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
