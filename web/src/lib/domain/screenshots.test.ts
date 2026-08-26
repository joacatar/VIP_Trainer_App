import { describe, expect, it } from 'vitest'
import {
  extractClipboardImages,
  isScreenshotFilename,
  pastedImageFilename,
  sanitizeFilename,
  screenshotStoragePath,
  validateScreenshotFilename,
} from '@/lib/domain/screenshots'

describe('sanitizeFilename', () => {
  it('replaces spaces and strips unsafe characters', () => {
    expect(sanitizeFilename('My Screenshot (1).png')).toBe('My_Screenshot_1.png')
  })

  it('falls back to upload.bin when nothing survives', () => {
    expect(sanitizeFilename('///???')).toBe('upload.bin')
  })
})

describe('isScreenshotFilename / validateScreenshotFilename', () => {
  it('accepts the allowed image extensions case-insensitively', () => {
    expect(isScreenshotFilename('shot.PNG')).toBe(true)
    expect(isScreenshotFilename('shot.jpeg')).toBe(true)
    expect(isScreenshotFilename('shot.pdf')).toBe(false)
  })

  it('throws for a disallowed extension', () => {
    expect(() => validateScreenshotFilename('notes.pdf')).toThrow()
  })
})

describe('screenshotStoragePath', () => {
  it('matches the Python screenshot_storage_path layout', () => {
    expect(
      screenshotStoragePath({
        ownerUserId: 'trainee-uuid',
        caseId: 'case-uuid',
        threadId: 'thread-uuid',
        filename: 'My Screenshot.png',
      }),
    ).toBe('trainee-uuid/case-uuid/screenshots/thread-uuid/My_Screenshot.png')
  })
})

describe('pastedImageFilename / extractClipboardImages', () => {
  it('builds a collision-resistant png name by default', () => {
    expect(pastedImageFilename('image/png', 2)).toMatch(
      /^screenshot_\d+_2\.png$/,
    )
    expect(pastedImageFilename('image/jpeg', 1)).toMatch(/\.jpg$/)
  })

  it('reads images from clipboard items', () => {
    const blob = new Blob([new Uint8Array([1, 2, 3])], { type: 'image/png' })
    const file = new File([blob], 'clip.png', { type: 'image/png' })
    const item = {
      type: 'image/png',
      getAsFile: () => file,
    }
    const data = {
      items: [item],
      files: [] as unknown as FileList,
    } as unknown as DataTransfer
    const out = extractClipboardImages(data, 1)
    expect(out).toHaveLength(1)
    expect(out[0].type).toBe('image/png')
    expect(out[0].name).toMatch(/^screenshot_\d+_1\.png$/)
  })

  it('falls back to clipboard files when items are empty', () => {
    const blob = new Blob([new Uint8Array([9])], { type: 'image/png' })
    const file = new File([blob], 'from-files.png', { type: 'image/png' })
    const data = {
      items: [] as unknown as DataTransferItemList,
      files: [file] as unknown as FileList,
    } as unknown as DataTransfer
    const out = extractClipboardImages(data, 3)
    expect(out).toHaveLength(1)
    expect(out[0].name).toMatch(/^screenshot_\d+_3\.png$/)
  })
})
