import { useT } from '../../i18n'
import type { TurnTiming } from './usapSession'

const STAGES = ['speech_end', 'stt_done', 'gate_done', 'first_token', 'first_sentence', 'first_tts', 'first_audio_sent', 'done']

/** Laptop-only waterfall of the last 10 turns: one bar per stage, from CUSTOM timing stamps. */
export function TimingPanel({ timings }: { timings: TurnTiming[] }) {
  const t = useT()
  if (!timings.length) return null
  const max = Math.max(1, ...timings.flatMap(x => [...Object.values(x.stamps), x.firstAudioMs ?? 0]))
  return (
    <section className="usap-timing" aria-label={t('voice.timingTitle')}>
      <h2 className="usap-timing__title">{t('voice.timingTitle')}</h2>
      <ol className="usap-timing__list">
        {timings.map(turn => {
          const entries = Object.entries(turn.stamps).sort((a, b) => a[1] - b[1])
          return (
            <li key={turn.turn} className="usap-timing__row">
              <div className="usap-timing__track">
                {entries.map(([name, ms], i) => {
                  const from = i === 0 ? 0 : entries[i - 1][1]
                  return (
                    <span key={name} className={`usap-timing__bar usap-timing__bar--${STAGES.indexOf(name) % 4}`}
                      style={{ left: `${(from / max) * 100}%`, width: `${Math.max(0.5, ((ms - from) / max) * 100)}%` }}
                      title={`${name}: ${Math.round(ms)} ms`} />
                  )
                })}
              </div>
              <span className="usap-timing__ms">
                {turn.firstAudioMs != null ? `${(turn.firstAudioMs / 1000).toFixed(2)} s` : '–'}
              </span>
            </li>
          )
        })}
      </ol>
    </section>
  )
}
