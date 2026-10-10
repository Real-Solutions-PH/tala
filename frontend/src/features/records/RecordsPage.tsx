import { useState } from 'react'
import { Camera } from 'lucide-react'
import { DisplayTitle } from '../../components/DisplayTitle'
import { useT } from '../../i18n'
import { HealthSummary } from './HealthSummary'
import { Timeline } from './Timeline'
import { UploadSheet } from './UploadSheet'
import './records.css'

/** Talaan: the add-a-result tile, the health summary and the history. */
export function RecordsPage() {
  const t = useT()
  const [adding, setAdding] = useState(false)
  return (
    <div className="page records">
      <DisplayTitle>{t('records.title')}</DisplayTitle>
      {/* After the prototype's "Scan a record": a dashed blue tile with a camera, a title and one line of help. */}
      <button type="button" className="scanbtn" aria-label={t('records.addResult')} aria-describedby="scan-sub" onClick={() => setAdding(true)}>
        <Camera aria-hidden="true" strokeWidth={2} />
        <span><b>{t('records.addResult')}</b><span id="scan-sub">{t('records.addResultSub')}</span></span>
      </button>
      <HealthSummary />
      <Timeline />
      <UploadSheet open={adding} onClose={() => setAdding(false)} />
    </div>
  )
}
