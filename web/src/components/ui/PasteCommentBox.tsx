import {
  useCallback,
  useId,
  useRef,
  useState,
  type ChangeEvent,
  type ClipboardEvent,
  type DragEvent,
  type ReactNode,
} from 'react'
import { ImageAttachments } from '@/components/ui/ImageAttachments'
import { extractClipboardImages } from '@/lib/domain/screenshots'

/**
 * Jira-style comment box — type text and paste/drop/upload screenshots in
 * the same field. Mirrors Streamlit's `comment_box` / paste_image.py UX so
 * trainers don't have to hunt for a separate upload control.
 */
export function PasteCommentBox({
  value,
  onChange,
  images,
  onImagesChange,
  placeholder = 'Write a comment… Paste screenshots here with Ctrl+V / Cmd+V',
  rows = 4,
  disabled = false,
  footer,
}: {
  value: string
  onChange: (next: string) => void
  images: File[]
  onImagesChange: (next: File[]) => void
  placeholder?: string
  rows?: number
  disabled?: boolean
  footer?: ReactNode
}) {
  const inputId = useId()
  const fileRef = useRef<HTMLInputElement>(null)
  const [dragOver, setDragOver] = useState(false)
  const [status, setStatus] = useState('')

  const appendImages = useCallback(
    (incoming: File[], source: 'paste' | 'upload' | 'drop') => {
      if (incoming.length === 0) return
      onImagesChange([...images, ...incoming])
      const noun = incoming.length === 1 ? 'screenshot' : 'screenshots'
      if (source === 'paste') {
        setStatus(`Pasted ${incoming.length} ${noun}. Keep typing if needed.`)
      } else if (source === 'drop') {
        setStatus(`Dropped ${incoming.length} ${noun}.`)
      } else {
        setStatus(`Attached ${incoming.length} ${noun}.`)
      }
    },
    [images, onImagesChange],
  )

  function onPaste(e: ClipboardEvent<HTMLTextAreaElement>) {
    const extracted = extractClipboardImages(
      e.clipboardData,
      images.length + 1,
    )
    if (extracted.length === 0) return
    e.preventDefault()
    appendImages(extracted, 'paste')
  }

  function onDrop(e: DragEvent<HTMLDivElement>) {
    e.preventDefault()
    setDragOver(false)
    if (disabled) return
    const files = Array.from(e.dataTransfer.files).filter((f) =>
      f.type.startsWith('image/'),
    )
    appendImages(files, 'drop')
  }

  function onFileChange(e: ChangeEvent<HTMLInputElement>) {
    const files = Array.from(e.target.files ?? [])
    appendImages(files, 'upload')
    e.target.value = ''
  }

  return (
    <div
      className={`rounded-lg border bg-surface p-3 shadow-sm transition ${
        dragOver
          ? 'border-primary ring-2 ring-primary/25'
          : 'border-border focus-within:border-primary focus-within:ring-2 focus-within:ring-primary/20'
      } ${disabled ? 'opacity-60' : ''}`}
      onDragOver={(e) => {
        e.preventDefault()
        if (!disabled) setDragOver(true)
      }}
      onDragLeave={() => setDragOver(false)}
      onDrop={onDrop}
    >
      <textarea
        rows={rows}
        disabled={disabled}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onPaste={onPaste}
        placeholder={placeholder}
        className="w-full resize-y border-0 bg-transparent text-sm text-text outline-none placeholder:text-muted"
      />

      <ImageAttachments
        files={images}
        onRemove={(i) => {
          onImagesChange(images.filter((_, idx) => idx !== i))
          setStatus(
            images.length <= 1
              ? ''
              : `${images.length - 1} screenshot(s) attached`,
          )
        }}
      />

      <div className="mt-2 flex flex-wrap items-center justify-between gap-2">
        <div className="flex flex-wrap items-center gap-3">
          <label
            htmlFor={inputId}
            className={`text-xs font-medium text-primary ${
              disabled ? 'pointer-events-none opacity-50' : 'cursor-pointer hover:underline'
            }`}
          >
            Upload screenshots
          </label>
          <input
            id={inputId}
            ref={fileRef}
            type="file"
            accept="image/png,image/jpeg,image/webp,image/gif"
            multiple
            disabled={disabled}
            className="hidden"
            onChange={onFileChange}
          />
          <span className="text-xs text-muted">
            or paste with Ctrl+V / Cmd+V · drag & drop
          </span>
        </div>
        {footer}
      </div>

      <p className="mt-1 min-h-[1.1em] text-xs text-muted" aria-live="polite">
        {status ||
          (images.length > 0
            ? `${images.length} screenshot${images.length === 1 ? '' : 's'} attached`
            : '')}
      </p>
    </div>
  )
}
