/** Port of files.py's screenshot naming/path rules — kept in sync so a
 * screenshot uploaded from the React app lands in the exact same Storage
 * layout the Streamlit app already reads (and vice versa). */

export const SCREENSHOT_EXTENSIONS = ['.png', '.jpg', '.jpeg', '.webp', '.gif']

export function sanitizeFilename(filename: string): string {
  const base = filename.split(/[/\\]/).pop()?.trim().replace(/ /g, '_') ?? ''
  const cleaned = base.replace(/[^A-Za-z0-9._-]/g, '')
  return cleaned || 'upload.bin'
}

export function isScreenshotFilename(filename: string): boolean {
  const lowered = filename.toLowerCase()
  return SCREENSHOT_EXTENSIONS.some((ext) => lowered.endsWith(ext))
}

export function validateScreenshotFilename(filename: string): string {
  if (!isScreenshotFilename(filename)) {
    throw new Error(
      `Screenshot must end with ${SCREENSHOT_EXTENSIONS.join(', ')} (got "${filename}")`,
    )
  }
  return sanitizeFilename(filename)
}

/** Mirrors files.py's screenshot_storage_path — stored under the trainee's
 * own auth-user folder (not the trainer's) so the existing case-files
 * storage RLS policy, which reads that folder segment as the owner, keeps
 * working unchanged. */
export function screenshotStoragePath(opts: {
  ownerUserId: string
  caseId: string
  threadId: string
  filename: string
}): string {
  const safeName = validateScreenshotFilename(opts.filename)
  return `${opts.ownerUserId}/${opts.caseId}/screenshots/${opts.threadId}/${safeName}`
}

/** Turns a pasted-image filename collision-resistant, matching the
 * `screenshot_${timestamp}_${n}.${ext}` pattern paste_image.py generates
 * for clipboard images (which never carry a real filename). */
export function pastedImageFilename(mimeType: string, n: number): string {
  const ext = mimeType.includes('jpeg')
    ? 'jpg'
    : mimeType.includes('webp')
      ? 'webp'
      : mimeType.includes('gif')
        ? 'gif'
        : 'png'
  return `screenshot_${Date.now()}_${n}.${ext}`
}

/**
 * Pull image files out of a clipboard / drag DataTransfer.
 * macOS Safari often puts images in `files` instead of `items` — check both,
 * same as Streamlit's paste_image.js which reads clipboard items then falls
 * back.
 */
export function extractClipboardImages(
  data: DataTransfer | null | undefined,
  startIndex = 1,
): File[] {
  if (!data) return []
  const images: File[] = []
  const seen = new Set<string>()

  const push = (file: File, mime: string) => {
    const key = `${file.size}:${mime}:${file.lastModified}`
    if (seen.has(key)) return
    seen.add(key)
    images.push(
      new File([file], pastedImageFilename(mime, startIndex + images.length), {
        type: mime || file.type || 'image/png',
      }),
    )
  }

  if (data.items) {
    for (const item of Array.from(data.items)) {
      if (!item.type.startsWith('image/')) continue
      const file = item.getAsFile()
      if (file) push(file, item.type)
    }
  }

  if (images.length === 0 && data.files?.length) {
    for (const file of Array.from(data.files)) {
      if (!file.type.startsWith('image/')) continue
      push(file, file.type)
    }
  }

  return images
}

