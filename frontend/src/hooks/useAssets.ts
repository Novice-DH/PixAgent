/** 素材钩子：本地前置校验是体验优化不是安全边界（服务端 probe 才是权威）；
 * 上传成功 invalidate 列表缓存，排序与一致性交给缓存失效机制。 */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { ACCEPTED_TYPES, assetsApi, MAX_UPLOAD_BYTES } from '@/api/assets'

export const ASSETS_KEY = ['assets'] as const

/** 返回错误文案（不合规不发请求）；合规返回 null。 */
export function checkFile(file: File): string | null {
  if (!ACCEPTED_TYPES.includes(file.type)) {
    return '仅支持 JPEG、PNG 或 WebP 图片'
  }
  if (file.size > MAX_UPLOAD_BYTES) {
    return '文件超过 20 MB 上限'
  }
  return null
}

export function useAssets() {
  return useQuery({
    queryKey: ASSETS_KEY,
    queryFn: () => assetsApi.list(),
  })
}

export function useUploadAsset() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: assetsApi.upload,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ASSETS_KEY })
    },
  })
}
