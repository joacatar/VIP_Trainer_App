import { useEffect, useMemo } from 'react'

/** Thumbnail row for File objects staged for upload but not saved yet —
 * used below the "Raise correction" textarea between pasting/choosing
 * screenshots and actually submitting them. */
export function ImageAttachments({
  files,
  onRemove,
}: {
  files: File[]
  onRemove: (index: number) => void
}) {
  // Derived during render, not via setState-in-effect — the effect below
  // only handles the one real side effect, revoking the blob URLs once
  // React is done with this render's set.
  const urls = useMemo(() => files.map((f) => URL.createObjectURL(f)), [files])
  useEffect(() => {
    return () => {
      for (const url of urls) URL.revokeObjectURL(url)
    }
  }, [urls])

  if (files.length === 0) return null

  return (
    <div className="mt-2 flex flex-wrap gap-2">
      {files.map((file, i) => (
        <div
          key={`${file.name}-${file.lastModified}-${i}`}
          className="group relative h-20 w-28 overflow-hidden rounded-md border border-border bg-surface-2"
        >
          {urls[i] ? (
            <img
              src={urls[i]}
              alt={file.name}
              className="h-full w-full object-cover"
            />
          ) : null}
          <button
            type="button"
            onClick={() => onRemove(i)}
            aria-label={`Remove ${file.name}`}
            className="absolute right-1 top-1 flex h-5 w-5 items-center justify-center rounded-full bg-black/70 text-xs leading-none text-white hover:bg-black/90"
          >
            ×
          </button>
        </div>
      ))}
    </div>
  )
}
