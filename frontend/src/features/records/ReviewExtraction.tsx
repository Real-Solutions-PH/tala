import { useId, useState } from 'react'
import { Check, Pencil, X } from 'lucide-react'
import type { Observation } from '../../api/types'
import { Button } from '../../components/Button'
import { Card } from '../../components/Card'
import { useToast } from '../../components/Toast'
import { formatDate, useLang, useT } from '../../i18n'
import { useLock } from '../lock/useLock'
import { useConfirmObservations, type ObservationEdit } from './api'
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
          ? <Button variant="secondary" icon={Check} disabled={bad || !row.date} onClick={() => onChange({ ...row, editing: false })}>{t('records.doneRow')}</Button>
          : <Button variant="secondary" icon={Pencil} onClick={() => onChange({ ...row, editing: true })}>{t('records.editRow')}</Button>}
        <Button variant="ghost" icon={X} onClick={onRemove}>{t('records.removeRow')}</Button>
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
  const [rows, setRows] = useState<Row[]>(() => proposed.map(toRow))
  const [done, setDone] = useState(false)

  if (done || proposed.length === 0) return null

  const invalid = rows.some(r => badValue(r) || !r.date)
  const save = () => {
    const edits: Record<number, ObservationEdit> = {}
    for (const r of rows) {
      if (changed(r)) edits[r.obs.id] = { value: r.obs.value != null ? Number(r.value) : null, unit: r.unit.trim() || null, date: r.date }
    }
    const ids = rows.map(r => r.obs.id)
    confirm.mutate({ ids, edits }, {
      onSuccess: () => { setDone(true); toast(t(ids.length ? 'records.confirmed' : 'records.allRemoved')) },
      onError: () => toast(t('toasts.failed'), 'error'),
    })
  }

  return (
    <Card as="section" className="review" aria-labelledby={titleId}>
      <h2 id={titleId} className="review__title">{t('records.reviewTitle')}</h2>
      <p className="muted">{t('records.reviewBody')}</p>
      <ul className="review__list">
        {rows.map((r, i) => (
          <RowView key={r.obs.id} row={r}
            onChange={next => setRows(rs => rs.map((x, j) => (j === i ? next : x)))}
            onRemove={() => setRows(rs => rs.filter((_, j) => j !== i))} />
        ))}
      </ul>
      <Button size="lg" block icon={Check} loading={confirm.isPending} disabled={invalid} onClick={save}>{t('records.confirmAll')}</Button>
    </Card>
  )
}
