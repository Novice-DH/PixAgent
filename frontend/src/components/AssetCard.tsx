/** 素材卡片：懒加载缩略图 + 透明底角标 + 解码元数据。 */
import type { Asset } from '@/api/assets'
import { formatBytes, formatDateTime } from '@/lib/format'

export default function AssetCard({ asset }: { asset: Asset }) {
  return (
    <figure className="overflow-hidden rounded-card border border-line bg-paper shadow-card">
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
    </figure>
  )
}
