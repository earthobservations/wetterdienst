import { expect } from '@playwright/test'

/**
 * Room for the rounding of a layout: Firefox measured a 44 px chip as 43.99999237 px (GH-3968). A hundredth of a pixel
 * is far below what a pointer can tell, and far above the rounding, so a target of 43 px still fails.
 */
export const SUB_PIXEL_PX = 0.01

/** Whether a measured size reaches `min` px, allowing for the sub-pixel rounding of the layout */
export function reachesPx(value: number, min: number): boolean {
  return value >= min - SUB_PIXEL_PX
}

/** Asserts that a measured size of a target is `min` px or more (WCAG 2.5.8 asks 24, the app's own measure is 44) */
export function expectAtLeastPx(value: number, min: number, message?: string): void {
  expect(reachesPx(value, min), `${message ? `${message}: ` : ''}${value} px is less than ${min} px`).toBe(true)
}
