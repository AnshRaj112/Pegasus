/** User-facing labels for CSV delimiter tokens. */

export function isAutoDelimiter(delim) {
  const lower = String(delim ?? '').trim().toLowerCase()
  return !lower || lower === 'auto' || lower === 'infer' || lower === 'detect'
}

export function formatDelimiterForDisplay(delim) {
  const token = String(delim ?? '').trim()
  if (!token) return '—'
  const lower = token.toLowerCase()
  if (lower === 'auto' || lower === 'infer' || lower === 'detect') {
    return 'auto (detect from files)'
  }
  if (token === '\t' || lower === 'tab' || token === '\\t') return 'tab (\\t)'
  if (token === ',') return 'comma (,)'
  if (token === '|') return 'pipe (|)'
  if (token === ';') return 'semicolon (;)'
  if (token.length > 1) {
    return `"${token}" (${token.length}-character separator)`
  }
  return `"${token}"`
}
