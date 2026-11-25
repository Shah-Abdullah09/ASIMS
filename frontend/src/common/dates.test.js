import { afterEach, expect, test, vi } from 'vitest'
import { todayIso } from './dates.js'

afterEach(() => vi.useRealTimers())

test("today is the university's date, whatever the browser's time zone", () => {
  vi.useFakeTimers()
  vi.setSystemTime(new Date('2026-11-25T22:30:00Z')) // 03:30 on 26 Nov in Pakistan
  expect(todayIso()).toBe('2026-11-26')
  vi.setSystemTime(new Date('2026-11-25T18:30:00Z')) // 23:30 on 25 Nov in Pakistan
  expect(todayIso()).toBe('2026-11-25')
})
