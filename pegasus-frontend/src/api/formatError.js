/** User-facing text for API / validation job errors. */

const LEGACY_JOB_MESSAGES = {
  'source and target are empty':
    'Both source and target files are empty (no data rows).',
}

/**
 * Turn a failed validation job `error` / `message` field into plain text.
 * Strips Python-style wrappers such as ValidationBadRequestError('…').
 */
export function formatJobError(raw, { fallback = 'Validation job failed' } = {}) {
  if (raw == null || raw === '') return fallback

  let text = String(raw).trim()

  const quoted = text.match(/^[\w.]+Error\((['"])(.*)\1\)$/)
  if (quoted) {
    text = quoted[2]
  } else {
    const bare = text.match(/^[\w.]+Error\((.+)\)$/)
    if (bare) text = bare[1].trim()
  }

  return LEGACY_JOB_MESSAGES[text] ?? text
}
