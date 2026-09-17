/** 图片拖拽/点击上传区：拖入态高亮、错误就地显示、选择后重置 input（同一文件可重复选择）。 */
import { useRef, useState } from 'react'

import { checkFile } from '@/hooks/useAssets'

interface ImageDropzoneProps {
  disabled?: boolean
  onFile: (file: File) => void
}

export default function ImageDropzone({ disabled = false, onFile }: ImageDropzoneProps) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [dragging, setDragging] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const acceptFile = (file: File | undefined) => {
    if (!file || disabled) return
    const problem = checkFile(file)
    if (problem) {
      setError(problem)
      return
    }
    setError(null)
    onFile(file)
  }

  return (
    <div>
      <div
        role="button"
        tabIndex={0}
        aria-disabled={disabled}
        onClick={() => !disabled && inputRef.current?.click()}
        onKeyDown={(event) => {
          if (!disabled && (event.key === 'Enter' || event.key === ' ')) {
            inputRef.current?.click()
          }
        }}
        onDragOver={(event) => {
          event.preventDefault()
          if (!disabled) setDragging(true)
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(event) => {
          event.preventDefault()
          setDragging(false)
          acceptFile(event.dataTransfer.files[0])
        }}
        className={`flex cursor-pointer flex-col items-center justify-center gap-2 rounded-card border-2 border-dashed px-6 py-10 text-center transition-colors ${
          dragging
            ? 'border-brand bg-brand-soft'
            : 'border-line-strong bg-paper hover:border-brand hover:bg-soft'
        } ${disabled ? 'cursor-not-allowed opacity-60' : ''}`}
      >
        <span className="text-sm font-medium text-ink">
          {disabled ? '正在上传…' : '拖拽图片到这里，或点击选择文件'}
        </span>
        <span className="text-xs text-muted">支持 JPEG / PNG / WebP，不超过 20 MB</span>
      </div>

      {error && (
        <p role="alert" className="mt-2 text-sm text-danger">
          {error}
        </p>
      )}

      <input
        ref={inputRef}
        type="file"
        accept="image/jpeg,image/png,image/webp"
        className="hidden"
        onChange={(event) => {
          acceptFile(event.target.files?.[0])
          event.target.value = '' // 重置后同一文件可重复选择
        }}
      />
    </div>
  )
}
