/** 素材卡片：懒加载缩略图 + 透明底角标 + 解码元数据。
 * 传入 onSelect 时整卡可点（创作页用于建会话进编辑器）；展示组件不持有路由跳转。 */
import type { Asset } from '@/api/assets'
import { formatBytes, formatDateTime } from '@/lib/format'

interface AssetCardProps {
  asset: Asset
  onSelect?: (asset: Asset) => void
}

export default function AssetCard({ asset, onSelect }: AssetCardProps) {
  const body = (
    <>
      <div className="relative bg-canvas">
        <img
          src={asset.url}
          alt={`素材 ${asset.image_format} ${asset.width}×${asset.height}`}
          loading="lazy"
          className="aspect-[4/3] w-full object-contain"
        />
        {asset.has_alpha && (
          <span className="absolute left-2 top-2 rounded-control bg-brand-soft px-2 py-0.5 text-xs font-medium text-brand-strong">
            透明底
          </span>
        )}
      </div>
      <figcaption className="flex flex-col gap-0.5 px-3 py-2 text-xs text-muted">
        <span className="text-ink">
          {asset.width}×{asset.height}
        </span>
        <span>
          {asset.image_format} · {formatBytes(asset.size_bytes)}
        </span>
        <span>{formatDateTime(asset.created_at)}</span>
      </figcaption>
    </>
  )

  if (onSelect) {
    return (
      <button
        type="button"
        title="点击选用这张素材"
        onClick={() => onSelect(asset)}
        className="block w-full overflow-hidden rounded-card border border-line bg-paper text-left shadow-card transition-[border-color,transform] duration-150 hover:border-brand active:scale-[0.99]"
      >
        {body}
      </button>
    )
  }

  return (
    <figure className="overflow-hidden rounded-card border border-line bg-paper shadow-card">
      {body}
    </figure>
  )
}
