import { useState } from 'react'
import { Plus } from 'lucide-react'
import { Button } from '../../components/Button'
import { DisplayTitle } from '../../components/DisplayTitle'
import { useT } from '../../i18n'
import { HealthSummary } from './HealthSummary'
import { Timeline } from './Timeline'
import { UploadSheet } from './UploadSheet'
import './records.css'

/** Talaan: the health summary, the add-a-result button and the history. */
export function RecordsPage() {
  const t = useT()
  const [adding, setAdding] = useState(false)
  return (
    <div className="page records">
      <DisplayTitle>{t('records.title')}</DisplayTitle>
      <HealthSummary />
      <Button size="lg" block icon={Plus} className="btn--cta" onClick={() => setAdding(true)}>{t('records.addResult')}</Button>
      <Timeline />
      <UploadSheet open={adding} onClose={() => setAdding(false)} />
    </div>
  )
}
