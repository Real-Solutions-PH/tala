// Silero VAD in the browser (@ricky0123/vad-web). Model, worklet and onnxruntime wasm are served from
// /vad/ (copied there by scripts/copy-vad.ts). Thresholds are starting points; Task 20 tunes them.
import { useEffect, useRef, useState } from 'react'

export const VAD_BASE = '/vad/'
export const VAD_TUNING = {
  positiveSpeechThreshold: 0.6,
  negativeSpeechThreshold: 0.45,
  minSpeechMs: 300,
  redemptionMs: 500,
}
/** While Kapiling speaks, only a clearly louder voice counts, so she does not interrupt herself. */
export const VAD_WHILE_SPEAKING = { positiveSpeechThreshold: 0.8, negativeSpeechThreshold: 0.65 }

export type VadStatus = 'loading' | 'ready' | 'denied'

type Callbacks = {
  onSpeechStart: () => void
  onSpeechEnd: (samples: Float32Array) => void
  onMisfire?: () => void
}

type Vad = { start(): Promise<void>; destroy(): Promise<void>; setOptions(o: Record<string, number>): void }

export function useVad(cb: Callbacks, speaking: boolean, enabled = true): VadStatus {
  const [status, setStatus] = useState<VadStatus>('loading')
  const cbRef = useRef(cb)
  cbRef.current = cb
  const vadRef = useRef<Vad | null>(null)

  useEffect(() => {
    if (!enabled) return
    let dead = false
    let vad: Vad | null = null
    ;(async () => {
      try {
        const { MicVAD } = await import('@ricky0123/vad-web')
        vad = await MicVAD.new({
          model: 'v5',
          baseAssetPath: VAD_BASE,
          // Vite dev refuses a module import from public/, so dev loads ort from node_modules; builds use /vad/.
          onnxWASMBasePath: import.meta.env.DEV ? '/node_modules/onnxruntime-web/dist/' : VAD_BASE,
          ...VAD_TUNING,
          getStream: () => navigator.mediaDevices.getUserMedia({
            audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true, autoGainControl: true },
          }),
          onSpeechStart: () => cbRef.current.onSpeechStart(),
          onSpeechEnd: (audio: Float32Array) => cbRef.current.onSpeechEnd(audio),
          onVADMisfire: () => cbRef.current.onMisfire?.(),
        }) as unknown as Vad
        if (dead) { void vad.destroy(); return }
        vadRef.current = vad
        await vad.start()
        setStatus('ready')
      } catch {
        if (!dead) setStatus('denied')
      }
    })()
    return () => { dead = true; vadRef.current = null; void vad?.destroy() }
  }, [enabled])

  useEffect(() => {
    vadRef.current?.setOptions(speaking ? VAD_WHILE_SPEAKING : {
      positiveSpeechThreshold: VAD_TUNING.positiveSpeechThreshold,
      negativeSpeechThreshold: VAD_TUNING.negativeSpeechThreshold,
    })
  }, [speaking])

  return status
}
