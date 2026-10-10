// Turns a failed request into catalogue text. The backend sends i18n keys such as "errors.fileTooLarge" as
// its `detail`; anything we do not have copy for falls back to a plain-words message.
import { ApiError } from '../../api/client'
import { en } from '../../i18n/en'
import type { Key } from '../../i18n'

export function errorKey(err: unknown, fallback: Key = 'errors.generic'): Key {
  if (err instanceof ApiError) {
    const m = err.detail?.match(/^errors\.(\w+)$/)
    if (m && m[1] in en.errors) return err.detail as Key
    if (err.status === 404) return 'errors.notFound'
    return fallback
  }
  if (err instanceof TypeError) return 'errors.offline' // fetch itself failed: the laptop is unreachable
  return fallback
}
