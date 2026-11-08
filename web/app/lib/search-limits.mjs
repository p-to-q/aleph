export const MAX_SEARCH_TARGET_CHARS = 4096
export const MAX_SEARCH_OUTPUT_CHARS = 8192

/** Count Unicode code points, stopping once an oversized input is detected. */
export function countUnicodeCodePoints(text, stopAfter = Infinity) {
  let count = 0
  for (const _character of text) {
    count += 1
    if (count > stopAfter) return count
  }
  return count
}
