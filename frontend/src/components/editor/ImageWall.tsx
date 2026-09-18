/** 图片墙：64px 缩略图横向滚动，kind 中文角标，当前图 brand 描边。
 * 点击发起 PATCH 切换；pending 或当前项禁用——切换不覆盖任何已有内容，只是换 current。 */
import type { WallAsset } from '@/api/sessions'
import { KIND_LABELS } from '@/api/sessions'

interface ImageWallProps {
  wall: WallAsset[]
  currentAssetId: string
  disabled?: boolean
  onSwitch: (assetId: string) => void
}

export default function ImageWall({ wall, currentAssetId, disabled = false, onSwitch }: ImageWallProps) {
  return (
    <div className="flex shrink-0 items-center gap-2 overflow-x-auto border-t border-line bg-paper px-4 py-2">
      <span className="shrink-0 text-xs font-medium text-muted">图片墙</span>
      {wall.map(({ position, asset }) => {
        const current = asset.id === currentAssetId
        return (
          <button
            key={asset.id}
            type="button"
            disabled={disabled || current}
            aria-pressed={current}
            aria-label={`切换到图片 ${position}（${KIND_LABELS[asset.kind] ?? asset.kind}）`}
            onClick={() => onSwitch(asset.id)}
            className={`relative h-16 w-16 shrink-0 overflow-hidden rounded-control border-2 bg-canvas transition-colors disabled:cursor-default ${
              current ? 'border-brand' : 'border-transparent hover:border-line-strong'
            }`}
          >
            <img
              src={asset.url}
              alt=""
              aria-hidden="true"
              loading="lazy"
              className="h-full w-full object-cover"
            />
            <span className="absolute left-1 top-1 rounded-sm bg-ink/70 px-1 text-[10px] font-medium text-paper">
              {KIND_LABELS[asset.kind] ?? asset.kind}
            </span>
          </button>
        )
      })}
    </div>
  )
}
