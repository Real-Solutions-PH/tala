import { useRef, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { EllipsisVertical, MessageSquarePlus, Pencil, Trash2 } from 'lucide-react'
import { api } from '../../api/client'
import { keys, useConversations } from '../../api/queries'
import type { ConversationItem } from '../../api/types'
import { Button } from '../../components/Button'
import { Sheet } from '../../components/Sheet'
import { Skeleton } from '../../components/Skeleton'
import { useToast } from '../../components/Toast'
import { formatDate, useLang, useT, type Lang } from '../../i18n'
import { ConfirmSheet } from '../settings/ConfirmSheet'

type Props = {
  open: boolean; onClose: () => void; profileId: number | null; current?: string
  onOpen: (id: string) => void; onNew: () => void; onDeleted: (id: string) => void
}

function relative(iso: string, lang: Lang, t: ReturnType<typeof useT>): string {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return ''
  const day = (x: Date) => new Date(x.getFullYear(), x.getMonth(), x.getDate()).getTime()
  const diff = Math.round((day(new Date()) - day(d)) / 86_400_000)
  if (diff <= 0) return t('common.today')
  if (diff === 1) return t('common.yesterday')
  if (diff < 7) return new Intl.RelativeTimeFormat(lang === 'tl' ? 'fil' : 'en', { numeric: 'auto' }).format(-diff, 'day')
  return formatDate(d, lang)
}

export function HistoryDrawer({ open, onClose, profileId, current, onOpen, onNew, onDeleted }: Props) {
  const t = useT()
  const [lang] = useLang()
  const toast = useToast()
  const qc = useQueryClient()
  const list = useConversations(open ? profileId : null)
  const [menu, setMenu] = useState<string | null>(null)
  const [renaming, setRenaming] = useState<{ id: string; title: string } | null>(null)
  const [deleting, setDeleting] = useState<ConversationItem | null>(null)
  const [busy, setBusy] = useState(false)
  const press = useRef<ReturnType<typeof setTimeout> | null>(null)
  const longPressed = useRef(false)

  const items = [...(list.data ?? [])].sort((a, b) => (a.updated < b.updated ? 1 : a.updated > b.updated ? -1 : 0))
  const refresh = () => qc.invalidateQueries({ queryKey: keys.conversations(profileId) })

  const rename = async () => {
    if (!renaming || !renaming.title.trim()) return
    setBusy(true)
    try {
      await api.send('PATCH', `/conversations/${renaming.id}`, { title: renaming.title.trim() })
      toast(t('chat.renamed'))
      setRenaming(null)
      setMenu(null)
      void refresh()
      void qc.invalidateQueries({ queryKey: keys.conversation(renaming.id) })
    } catch {
      toast(t('chat.renameFailed'), 'error')
    } finally {
      setBusy(false)
    }
  }

  const remove = async () => {
    if (!deleting) return
    setBusy(true)
    try {
      await api.send('DELETE', `/conversations/${deleting.id}`)
      toast(t('chat.deleted'))
      onDeleted(deleting.id)
      setDeleting(null)
      setMenu(null)
      void refresh()
    } catch {
      toast(t('chat.deleteFailed'), 'error')
    } finally {
      setBusy(false)
    }
  }

  const startPress = (id: string) => {
    longPressed.current = false
    press.current = setTimeout(() => { longPressed.current = true; setMenu(id) }, 550)
  }
  const endPress = () => { if (press.current) clearTimeout(press.current); press.current = null }

  return (
    <Sheet open={open} onClose={onClose} title={t('chat.history')}>
      <div className="history">
        <Button variant="primary" block icon={MessageSquarePlus} onClick={onNew}>{t('chat.newChat')}</Button>
        {list.isPending && profileId != null && open ? (
          <div className="history__loading"><Skeleton height={56} /><Skeleton height={56} /><Skeleton height={56} /></div>
        ) : items.length === 0 ? (
          <p className="history__empty">{t('chat.noHistory')}</p>
        ) : (
          <ul className="history__list">
            {items.map(c => {
              const title = c.title || t('chat.untitled')
              return (
                <li key={c.id} className="history__item">
                  {renaming?.id === c.id ? (
                    <form className="history__rename" onSubmit={e => { e.preventDefault(); void rename() }}>
                      <label className="history__field">
                        <span className="history__label">{t('chat.renameLabel')}</span>
                        <input className="history__input" value={renaming.title} autoFocus
                          onChange={e => setRenaming({ id: c.id, title: e.target.value })} />
                      </label>
                      <div className="history__rename-actions">
                        <Button type="submit" loading={busy}>{t('common.save')}</Button>
                        <Button variant="secondary" onClick={() => setRenaming(null)}>{t('common.cancel')}</Button>
                      </div>
                    </form>
                  ) : (
                    <>
                      <div className="history__row">
                        <button type="button" className="history__open" aria-current={c.id === current || undefined}
                          onPointerDown={() => startPress(c.id)} onPointerUp={endPress} onPointerLeave={endPress}
                          onContextMenu={e => { e.preventDefault(); setMenu(c.id) }}
                          onClick={() => { if (!longPressed.current) onOpen(c.id) }}>
                          <span className="history__title">{title}</span>
                          <span className="history__date">{relative(c.updated, lang, t)}</span>
                        </button>
                        <button type="button" className="history__menu" aria-label={t('chat.menu', { title })} aria-expanded={menu === c.id}
                          onClick={() => setMenu(m => (m === c.id ? null : c.id))}>
                          <EllipsisVertical aria-hidden="true" />
                        </button>
                      </div>
                      {menu === c.id && (
                        <div className="history__actions">
                          <Button variant="secondary" icon={Pencil} onClick={() => setRenaming({ id: c.id, title: c.title })}>{t('chat.rename')}</Button>
                          <Button variant="danger" icon={Trash2} onClick={() => setDeleting(c)}>{t('common.delete')}</Button>
                        </div>
                      )}
                    </>
                  )}
                </li>
              )
            })}
          </ul>
        )}
      </div>
      <ConfirmSheet open={!!deleting} title={t('chat.deleteTitle')} body={t('chat.deleteBody', { title: deleting?.title || t('chat.untitled') })}
        confirmLabel={t('chat.deleteConfirm')} busy={busy} onConfirm={remove} onClose={() => setDeleting(null)} />
    </Sheet>
  )
}
