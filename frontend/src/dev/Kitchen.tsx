// Design-system preview ("kitchen sink"). Dev-only route /dev/kitchen; never part of the production bundle.
import { useState, type ReactNode } from 'react'
import {
  BookOpen, Camera, CircleCheck, CreditCard, FileText, HeartPulse, IdCard, Mic, Pill, Plus,
  Siren, TriangleAlert,
} from 'lucide-react'
import { Mark, type MarkState } from '../brand/Mark'
import { Badge } from '../components/Badge'
import { Button } from '../components/Button'
import { Card } from '../components/Card'
import { Chip } from '../components/Chip'
import { Disclaimer } from '../components/Disclaimer'
import { EmptyState } from '../components/EmptyState'
import { ErrorState } from '../components/ErrorState'
import { Sheet } from '../components/Sheet'
import { Skeleton } from '../components/Skeleton'
import { useToast } from '../components/Toast'
import { formatDate, formatNumber, translate, useLang, useT } from '../i18n'

const STATES: MarkState[] = ['idle', 'listening', 'thinking', 'speaking']

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section style={{ display: 'grid', gap: 'var(--s-3)' }}>
      <h2 className="small muted" style={{ fontFamily: 'var(--font-body)', fontWeight: 700, letterSpacing: '0.04em', textTransform: 'uppercase' }}>{title}</h2>
      {children}
    </section>
  )
}

const row = { display: 'flex', flexWrap: 'wrap', gap: 'var(--s-2)', alignItems: 'center' } as const

export default function Kitchen() {
  const t = useT()
  const [lang, setLang] = useLang()
  const toast = useToast()
  const [loading, setLoading] = useState(false)
  const [filter, setFilter] = useState<'all' | 'labs' | 'visits'>('all')
  const [sheet, setSheet] = useState(false)
  const [state, setState] = useState<MarkState>('listening')

  return (
    <div className="standalone">
      <main style={{ flex: 1, width: '100%', maxWidth: 640, margin: '0 auto', padding: 'var(--s-5) var(--s-4) var(--s-7)', display: 'grid', gap: 'var(--s-6)' }}>
        <div style={{ display: 'grid', gap: 'var(--s-2)' }}>
          <h1>{t('common.appName')}</h1>
          <p className="muted">{t('common.tagline')}</p>
          <div style={row} role="group" aria-label={t('common.language')}>
            <Chip selected={lang === 'tl'} onClick={() => { setLang('tl'); toast(translate('tl', 'toasts.languageChanged')) }}>{t('common.tagalog')}</Chip>
            <Chip selected={lang === 'en'} onClick={() => { setLang('en'); toast(translate('en', 'toasts.languageChanged')) }}>{t('common.english')}</Chip>
          </div>
        </div>

        <Section title="Mark and Usap">
          <Card style={{ display: 'grid', gap: 'var(--s-4)' }}>
            <div style={{ ...row, gap: 'var(--s-5)', alignItems: 'flex-end' }}>
              <Mark size={16} /><Mark size={24} /><Mark size={32} /><Mark size={64} /><Mark size={112} eyes state={state} />
            </div>
            <div style={row}>
              {STATES.map(s => <Chip key={s} selected={state === s} onClick={() => setState(s)}>{s}</Chip>)}
            </div>
            <p className="muted">{t(`voice.${state === 'idle' ? 'holdToTalk' : state}`)}</p>
          </Card>
        </Section>

        <Section title="Buttons">
          <div style={{ display: 'grid', gap: 'var(--s-3)' }}>
            <Button size="lg" block icon={Mic}>{t('chat.talk')}</Button>
            <div style={row}>
              <Button icon={Camera}>{t('common.takePhoto')}</Button>
              <Button variant="secondary" icon={Plus}>{t('common.add')}</Button>
              <Button variant="ghost">{t('common.cancel')}</Button>
            </div>
            <div style={row}>
              <Button variant="danger" icon={Siren}>{t('emergency.button')}</Button>
              <Button loading={loading} onClick={() => { setLoading(true); setTimeout(() => { setLoading(false); toast(t('toasts.saved')) }, 1500) }}>{t('common.save')}</Button>
              <Button disabled>{t('common.next')}</Button>
            </div>
          </div>
        </Section>

        <Section title="Badges">
          <div style={row}>
            <Badge tone="ok" icon={CircleCheck}>{t('meds.taken')}</Badge>
            <Badge tone="warn" icon={TriangleAlert}>{t('meds.refillSoon', { n: 5 })}</Badge>
            <Badge tone="danger" icon={HeartPulse}>{t('fields.allergies')}: Penicillin</Badge>
            <Badge tone="info">{t('blocks.high')}</Badge>
          </div>
        </Section>

        <Section title="Chips">
          <div className="chip-row">
            <Chip icon={IdCard}>{t('chat.chipPhilhealth')}</Chip>
            <Chip icon={Pill}>{t('chat.chipMeds')}</Chip>
            <Chip icon={FileText}>{t('chat.chipLatest')}</Chip>
            <Chip icon={BookOpen}>{t('chat.chipForm')}</Chip>
          </div>
          <div className="chip-row">
            <Chip selected={filter === 'all'} onClick={() => setFilter('all')}>{t('records.all')}</Chip>
            <Chip selected={filter === 'labs'} onClick={() => setFilter('labs')}>{t('records.labs')}</Chip>
            <Chip selected={filter === 'visits'} onClick={() => setFilter('visits')}>{t('records.visits')}</Chip>
          </div>
        </Section>

        <Section title="Card, numbers and dates">
          <Card style={{ display: 'grid', gap: 'var(--s-2)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', gap: 'var(--s-3)', flexWrap: 'wrap' }}>
              <h3>FBS</h3>
              <Badge tone="warn" icon={TriangleAlert}>{t('blocks.high')}</Badge>
            </div>
            <p><span className="num" style={{ fontSize: 'var(--fs-2xl)', fontFamily: 'var(--font-head)', fontWeight: 700 }}>{formatNumber(132, lang)}</span> <span className="muted">mg/dL</span></p>
            <p className="muted small">{t('blocks.refRange', { range: '70–100' })} · <time dateTime="2026-03-02">{formatDate('2026-03-02', lang)}</time></p>
          </Card>
        </Section>

        <Section title="Toast">
          <div style={row}>
            <Button variant="secondary" onClick={() => toast(t('toasts.medTaken', { name: 'Metformin 500 mg' }))}>{t('meds.markTaken')}</Button>
            <Button variant="secondary" onClick={() => toast(t('toasts.failed'), 'error')}>{t('errors.title')}</Button>
          </div>
        </Section>

        <Section title="Sheet">
          <div><Button variant="secondary" icon={CreditCard} onClick={() => setSheet(true)}>{t('cards.showNurse')}</Button></div>
          <Sheet open={sheet} onClose={() => setSheet(false)} title={t('cards.philhealth')}>
            <p className="muted">{t('cards.emptyBody')}</p>
          </Sheet>
        </Section>

        <Section title="Skeleton">
          <Card style={{ display: 'grid', gap: 'var(--s-3)' }} aria-busy="true" aria-label={t('common.loading')}>
            <Skeleton width="55%" height={26} />
            <Skeleton height={18} />
            <Skeleton width="80%" height={18} />
          </Card>
        </Section>

        <Section title="Empty state">
          <Card><EmptyState icon={FileText} title={t('records.emptyTitle')} body={t('records.emptyBody')}
            action={{ label: t('records.addRecord'), icon: Camera, onClick: () => toast(t('toasts.recordAdded')) }} /></Card>
        </Section>

        <Section title="Error state">
          <Card><ErrorState message="errors.offline" onRetry={() => toast(t('common.loading'))} /></Card>
        </Section>

        <Section title="Safety">
          <Disclaimer />
          <Card flat><p>{t('safety.refusal.medication')}</p></Card>
        </Section>
      </main>

    </div>
  )
}
