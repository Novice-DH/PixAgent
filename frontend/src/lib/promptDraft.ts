/** 需求草稿：只活当前标签页（sessionStorage）；隐私模式等不可写场景静默降级，绝不阻塞主流程。 */

const DRAFT_KEY = 'retouch:prompt-draft'

/** 读取草稿；键缺失或存储不可用时返回空串。 */
export function readPromptDraft(): string {
  try {
    return sessionStorage.getItem(DRAFT_KEY) ?? ''
  } catch {
    return ''
  }
}

/** 写入草稿：先 trim；空值视为清除。写入失败静默放弃。 */
export function writePromptDraft(value: string): void {
  const trimmed = value.trim()
  try {
    if (trimmed) {
      sessionStorage.setItem(DRAFT_KEY, trimmed)
    } else {
      sessionStorage.removeItem(DRAFT_KEY)
    }
  } catch {
    // 草稿丢失不影响提交跳转主流程
  }
}
