import { useId, useState } from 'react'
import { Check, Pencil, Trash2 } from 'lucide-react'
import type { Observation } from '../../api/types'
import { Button } from '../../components/Button'
import { useToast } from '../../components/Toast'
import { formatDate, useLang, useT } from '../../i18n'
import { useLock } from '../lock/useLock'
import { useConfirmObservations, useRejectObservation, type ObservationEdit } from './api'
import { num } from './trend'
import './records.css'

type Row = { obs: Observation; value: string; unit: string; date: string; editing: boolean }

const toRow = (obs: Observation): Row => ({
  obs, value: obs.value != null ? String(obs.value) : obs.value_text ?? '', unit: obs.unit ?? '', date: obs.date, editing: false,
})
const badValue = (r: Row) => r.obs.value != null && (r.value.trim() === '' || !Number.isFinite(Number(r.value)))
const changed = (r: Row) => r.value !== toRow(r.obs).value || r.unit !== (r.obs.unit ?? '') || r.date !== r.obs.date

function RowView({ row, onChange, onRemove }: { row: Row; onChange: (r: Row) => void; onRemove: () => void }) {
  const t = useT()
  const [lang] = useLang()
  const id = useId()
  const bad = badValue(row)
  const shown = row.obs.value != null && !bad ? num(Number(row.value), lang) : row.value
  return (
    <li className="review-row">
      <p className="review-row__label">{row.obs.label}</p>
      {row.editing ? (
        <div className="review-row__fields">
          <label className="field">
            <span>{t('records.fieldValue')}</span>
            <input className="input" inputMode="decimal" value={row.value} aria-invalid={bad || undefined}
              aria-describedby={bad ? `${id}-err` : undefined} onChange={e => onChange({ ...row, value: e.target.value })} />
          </label>
          <label className="field">
            <span>{t('records.fieldUnit')}</span>
            <input className="input" value={row.unit} onChange={e => onChange({ ...row, unit: e.target.value })} />
          </label>
          <label className="field">
            <span>{t('records.fieldDate')}</span>
            <input className="input" type="date" value={row.date} onChange={e => onChange({ ...row, date: e.target.value })} />
          </label>
          {bad && <p className="field__error" id={`${id}-err`}>{t('records.notANumber')}</p>}
        </div>
      ) : (
        <p className="review-row__value">
          <span className="num">{shown}</span> {row.unit} <span className="small muted">· <time dateTime={row.date}>{row.date ? formatDate(row.date, lang) : ''}</time></span>
        </p>
      )}
      <div className="review-row__actions">
        {row.editing
          ? <button type="button" className="mini mini--on" disabled={bad || !row.date} onClick={() => onChange({ ...row, editing: false })}><Check aria-hidden="true" strokeWidth={2.5} />{t('records.doneRow')}</button>
          : <button type="button" className="mini" onClick={() => onChange({ ...row, editing: true })}><Pencil aria-hidden="true" strokeWidth={2} />{t('records.editRow')}</button>}
        <button type="button" className="mini" onClick={onRemove}><Trash2 aria-hidden="true" strokeWidth={2} />{t('records.removeRow')}</button>
      </div>
    </li>
  )
}

/**
 * Values Kapiling read from a document wait here as "proposed" until the person says they are right.
 * Only confirmed values reach the health summary and the charts (the server filters them too).
 */
export function ReviewExtraction({ documentId, proposed }: { documentId: number; proposed: Observation[] }) {
  const t = useT()
  const toast = useToast()
  const titleId = useId()
  const { profileId } = useLock()
  const confirm = useConfirmObservations(documentId, profileId)
  const reject = useRejectObservation(documentId)
  const [rows, setRows] = useState<Row[]>(() => proposed.map(toRow))
  const [removing, setRemoving] = useState(0)
  const [done, setDone] = useState(false)

  // Optimistic: the row leaves at once; if the server does not delete it (any error, including 404/405 before
  // the endpoint exists) it returns to its place and we say so. It is never reported removed unless it was.
  const order = (r: Row) => proposed.findIndex(o => o.id === r.obs.id)
  const remove = (row: Row) => {
    setRows(rs => rs.filter(r => r.obs.id !== row.obs.id))
    setRemoving(n => n + 1)
    reject.mutate(row.obs.id, {
      onSuccess: () => toast(t('records.removed')),
      onError: () => {
        setRows(rs => [...rs, row].sort((a, b) => order(a) - order(b)))
        toast(t('records.removeFailed'), 'error')
      },
      onSettled: () => setRemoving(n => n - 1),
    })
  }

  if (done || proposed.length === 0) return null

  const invalid = rows.some(r => badValue(r) || !r.date)
  const save = () => {
    const edits: Record<number, ObservationEdit> = {}
    for (const r of rows) {
      if (changed(r)) edits[r.obs.id] = { value: r.obs.value != null ? Number(r.value) : null, unit: r.unit.trim() || null, date: r.date }
    }
    const ids = rows.map(r => r.obs.id)
    if (ids.length === 0) { setDone(true); toast(t('records.allRemoved')); return } // nothing left to confirm
    confirm.mutate({ ids, edits }, {
      onSuccess: () => { setDone(true); toast(t('records.confirmed')) },
      onError: () => toast(t('toasts.failed'), 'error'),
    })
  }

  return (
    <section className="review" aria-labelledby={titleId}>
      <h2 id={titleId} className="review__title">{t('records.reviewTitle')}</h2>
      <p className="sub">{t('records.reviewBody')}</p>
      <span className="chip-s c-warn review__chip">{t('records.proposedChip')}</span>
      <ul className="review__list">
        {rows.map(r => (
          <RowView key={r.obs.id} row={r}
            onChange={next => setRows(rs => rs.map(x => (x.obs.id === next.obs.id ? next : x)))}
            onRemove={() => remove(r)} />
        ))}
      </ul>
      <Button size="lg" block icon={Check} loading={confirm.isPending} disabled={invalid || removing > 0} onClick={save}>{t('records.confirmAll')}</Button>
    </section>
  )
}
