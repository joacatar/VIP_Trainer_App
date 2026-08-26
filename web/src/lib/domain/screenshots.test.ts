import { describe, expect, it } from 'vitest'
import {
  isScreenshotFilename,
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
