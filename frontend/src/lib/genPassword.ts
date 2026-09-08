/**
 * Generate a strong, Migadu-acceptable password: 16 chars mixing upper,
 * lower, digits and a few safe symbols, guaranteed to contain at least
 * one of each class so it clears strength checks. Uses crypto.getRandomValues.
 */
export function genPassword(length = 16): string {
  const upper = 'ABCDEFGHJKLMNPQRSTUVWXYZ'   // no I/O to avoid confusion
  const lower = 'abcdefghijkmnpqrstuvwxyz'   // no l
  const digits = '23456789'                  // no 0/1
  const symbols = '-_.!@#'
  const all = upper + lower + digits + symbols
  const pick = (set: string) => set[Math.floor((crypto.getRandomValues(new Uint32Array(1))[0] / 2 ** 32) * set.length)]
  const out: string[] = [pick(upper), pick(lower), pick(digits), pick(symbols)]
  while (out.length < length) out.push(pick(all))
  // Fisher–Yates shuffle so the guaranteed chars aren't always in front
  for (let i = out.length - 1; i > 0; i--) {
    const j = Math.floor((crypto.getRandomValues(new Uint32Array(1))[0] / 2 ** 32) * (i + 1))
    ;[out[i], out[j]] = [out[j], out[i]]
  }
  return out.join('')
}
