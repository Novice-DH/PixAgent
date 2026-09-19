/** 选区 mutation：select 成功写 store、clear 成功清 store，失败 danger toast；
 * addPoint 的 append = 同 revision 已有选区；addStroke 显式带 radius（BRUSH_RADIUS
 * 单点在 lib/brush，预览线宽与服务端遮罩同源同宽）；busy 合并供画布手势禁用。
 * revision 变化的 effect 调 dropStaleSelection——撤销/切图/重做后本地立即作废，
 * 不等服务端 409（双端判据是同一个 revision，没有一致性风险）。 */
import { useMutation } from '@tanstack/react-query'
import { useEffect } from 'react'

import type { SelectInput } from '@/api/sessions'
import { sessionsApi } from '@/api/sessions'
import { BRUSH_RADIUS } from '@/lib/brush'
import { errorMessage } from '@/hooks/useAuth'
import { toast } from '@/stores/toasts'
import { useEditorUi } from '@/stores/editorUi'

export function useSelection(sessionId: string | undefined, revision: number | undefined) {
  const setSelection = useEditorUi((state) => state.setSelection)
  const dropStaleSelection = useEditorUi((state) => state.dropStaleSelection)
  const selection = useEditorUi((state) => state.selection)

  const select = useMutation({
    mutationFn: ({ input }: { input: SelectInput }) => {
      if (!sessionId) return Promise.reject(new Error('未选择会话'))
      return sessionsApi.select(sessionId, input)
    },
    onSuccess: (result) => {
      setSelection({
        revision: result.revision,
        maskId: result.mask.id,
        maskUrl: result.mask.url,
        markers: result.markers,
      })
    },
    onError: (error) => {
      toast(errorMessage(error) ?? '建立选区失败，请重试', 'danger')
    },
  })

  const clear = useMutation({
    mutationFn: () => {
      if (!sessionId) return Promise.reject(new Error('未选择会话'))
      return sessionsApi.clearSelection(sessionId)
    },
    onSuccess: () => {
      setSelection(null)
    },
    onError: (error) => {
      toast(errorMessage(error) ?? '清除选区失败', 'danger')
    },
  })

  // 双端同步作废：revision 变化（撤销/切图/重做）→ 本地选区立即失效
  useEffect(() => {
    if (revision !== undefined) {
      dropStaleSelection(revision)
    }
  }, [revision, dropStaleSelection])

  const busy = select.isPending || clear.isPending

  const addPoint = (x: number, y: number) => {
    if (!sessionId || revision === undefined || busy) return
    const append = selection?.revision === revision
    select.mutate({ input: { revision, points: [{ x, y }], append } })
  }

  const addStroke = (stroke: { x: number; y: number }[]) => {
    if (!sessionId || revision === undefined || busy || stroke.length === 0) return
    select.mutate({ input: { revision, strokes: [stroke], radius: BRUSH_RADIUS } })
  }

  const clearSelection = () => {
    if (clear.isPending) return
    clear.mutate()
  }

  return { selection, busy, addPoint, addStroke, clearSelection }
}
