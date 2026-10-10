import { ApiError } from '../../api/client'
import { translate, type Key } from '../../i18n'

/** An i18n key from an API error, when the server sent one we have words for. */
export function errorKey(e: unknown, fallback: Key = 'toasts.failed'): Key {
  const d = e instanceof ApiError ? e.detail : null
  return d && /^(settings|lock|errors|profile)\.\w+$/.test(d) && translate('en', d as Key) !== d ? d as Key : fallback
}
