import { Card } from '@/components/ui'
import { useLanguage } from '@/i18n'

interface DynEqBand {
  freq_lo: number; freq_hi: number; threshold_db: number; ratio: number
  gain_db: number; mode: string; enabled: boolean
}

interface EqNode {
  hz: number; gain_db: number; q: number; type: string; enabled: boolean
}

interface Props {
  dynEqEnabled: boolean; setDynEqEnabled: (v: boolean) => void
  dynEqMix: number; setDynEqMix: (v: number) => void
  dynEqBands: DynEqBand[]; setDynEqBands: (v: DynEqBand[]) => void

  msEqEnabled: boolean; setMsEqEnabled: (v: boolean) => void
  msMidNodes: EqNode[]; setMsMidNodes: (v: EqNode[]) => void
  msSideNodes: EqNode[]; setMsSideNodes: (v: EqNode[]) => void

  trEnabled: boolean; setTrEnabled: (v: boolean) => void
  trMix: number; setTrMix: (v: number) => void
  trAttack: number; setTrAttack: (v: number) => void
  trSustain: number; setTrSustain: (v: number) => void

  scEnabled: boolean; setScEnabled: (v: boolean) => void
  scTrigger: string; setScTrigger: (v: string) => void
  scAmount: number; setScAmount: (v: number) => void
  scAttack: number; setScAttack: (v: number) => void
  scRelease: number; setScRelease: (v: number) => void
  scMix: number; setScMix: (v: number) => void

  deessEnabled: boolean; setDeessEnabled: (v: boolean) => void
  deessFreq: number; setDeessFreq: (v: number) => void
  deessThreshold: number; setDeessThreshold: (v: number) => void
  deessMaxReduction: number; setDeessMaxReduction: (v: number) => void
  deessMode: 'split' | 'wide'; setDeessMode: (v: 'split' | 'wide') => void
  deessMix: number; setDeessMix: (v: number) => void
}

const Toggle = ({ enabled, onToggle }: { enabled: boolean; onToggle: () => void }) => (
  <button type="button" onClick={onToggle}
    className={`text-xs px-2 py-0.5 rounded-md transition-colors ${
      enabled ? 'bg-violet-500/20 text-violet-300 border border-violet-400/30'
              : 'bg-white/5 text-white/40 border border-white/10'
    }`}>
    {enabled ? 'ON' : 'OFF'}
  </button>
)

export function DspChainCard(p: Props) {
  const { t } = useLanguage()

  return (
    <Card className="p-5">
      <h3 className="mb-1 text-sm font-semibold text-white">{t('mix.dspProcessing')}</h3>
      <p className="mb-3 text-xs text-white/45">{t('mix.dspProcessingDesc')}</p>

      <div className="space-y-4">
        {/* Dynamic EQ */}
        <div className="rounded-xl border border-white/10 bg-black/30 p-3">
          <div className="flex items-center gap-2 mb-2">
            <Toggle enabled={p.dynEqEnabled} onToggle={() => p.setDynEqEnabled(!p.dynEqEnabled)} />
            <span className="text-xs font-medium text-white/70">{t('mix.dynamicEq')}</span>
            <label className="ml-auto flex items-center gap-1 text-[10px] text-white/40">
              {t('mix.dryWet')}
              <input type="range" min={0} max={1} step={0.01} value={p.dynEqMix}
                onChange={(e) => p.setDynEqMix(Number(e.target.value))} disabled={!p.dynEqEnabled} className="w-16 accent-violet-500" />
              <span className="font-mono text-white/50 w-7">{Math.round(p.dynEqMix * 100)}%</span>
            </label>
          </div>
          {p.dynEqEnabled && (
            <div className="space-y-1.5">
              {p.dynEqBands.map((b, i) => (
                <div key={i} className="flex items-center gap-1.5 text-[10px]">
                  <button type="button" onClick={() => {
                    const n = [...p.dynEqBands]; n[i] = { ...n[i], enabled: !n[i].enabled }; p.setDynEqBands(n)
                  }} className={b.enabled ? 'text-violet-400' : 'text-white/20'}>
                    {b.enabled ? '●' : '○'}
                  </button>
                  <input type="number" value={b.freq_lo} onChange={(e) => {
                    const n = [...p.dynEqBands]; n[i] = { ...n[i], freq_lo: Number(e.target.value) }; p.setDynEqBands(n)
                  }} disabled={!p.dynEqEnabled} className="w-14 rounded bg-black/40 px-1 py-0.5 text-center font-mono text-white/70 border border-white/10" />
                  <span className="text-white/30">–</span>
                  <input type="number" value={b.freq_hi} onChange={(e) => {
                    const n = [...p.dynEqBands]; n[i] = { ...n[i], freq_hi: Number(e.target.value) }; p.setDynEqBands(n)
                  }} disabled={!p.dynEqEnabled} className="w-14 rounded bg-black/40 px-1 py-0.5 text-center font-mono text-white/70 border border-white/10" />
                  <span className="text-white/30">Th</span>
                  <input type="number" value={b.threshold_db} onChange={(e) => {
                    const n = [...p.dynEqBands]; n[i] = { ...n[i], threshold_db: Number(e.target.value) }; p.setDynEqBands(n)
                  }} disabled={!p.dynEqEnabled} className="w-12 rounded bg-black/40 px-1 py-0.5 text-center font-mono text-white/70 border border-white/10" />
                  <span className="text-white/30">R</span>
                  <input type="number" value={b.ratio} step={0.1} onChange={(e) => {
                    const n = [...p.dynEqBands]; n[i] = { ...n[i], ratio: Number(e.target.value) }; p.setDynEqBands(n)
                  }} disabled={!p.dynEqEnabled} className="w-12 rounded bg-black/40 px-1 py-0.5 text-center font-mono text-white/70 border border-white/10" />
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Mid/Side EQ */}
        <div className="rounded-xl border border-white/10 bg-black/30 p-3">
          <div className="flex items-center gap-2 mb-2">
            <Toggle enabled={p.msEqEnabled} onToggle={() => p.setMsEqEnabled(!p.msEqEnabled)} />
            <span className="text-xs font-medium text-white/70">{t('mix.midsideEq')}</span>
          </div>
          {p.msEqEnabled && (
            <div className="grid grid-cols-2 gap-3">
              <div>
                <span className="text-[10px] text-white/40">{t('mix.mid')}</span>
                {p.msMidNodes.map((n, i) => (
                  <div key={i} className="flex items-center gap-1 text-[10px] mt-1">
                    <input type="number" value={n.hz} onChange={(e) => {
                      const next = [...p.msMidNodes]; next[i] = { ...next[i], hz: Number(e.target.value) }; p.setMsMidNodes(next)
                    }} disabled={!p.msEqEnabled} className="w-14 rounded bg-black/40 px-1 py-0.5 text-center font-mono text-white/70 border border-white/10" />
                    <input type="number" value={n.gain_db} step={0.5} onChange={(e) => {
                      const next = [...p.msMidNodes]; next[i] = { ...next[i], gain_db: Number(e.target.value) }; p.setMsMidNodes(next)
                    }} disabled={!p.msEqEnabled} className="w-12 rounded bg-black/40 px-1 py-0.5 text-center font-mono text-white/70 border border-white/10" />
                    <span className="text-white/30">dB</span>
                  </div>
                ))}
              </div>
              <div>
                <span className="text-[10px] text-white/40">{t('mix.side')}</span>
                {p.msSideNodes.map((n, i) => (
                  <div key={i} className="flex items-center gap-1 text-[10px] mt-1">
                    <input type="number" value={n.hz} onChange={(e) => {
                      const next = [...p.msSideNodes]; next[i] = { ...next[i], hz: Number(e.target.value) }; p.setMsSideNodes(next)
                    }} disabled={!p.msEqEnabled} className="w-14 rounded bg-black/40 px-1 py-0.5 text-center font-mono text-white/70 border border-white/10" />
                    <input type="number" value={n.gain_db} step={0.5} onChange={(e) => {
                      const next = [...p.msSideNodes]; next[i] = { ...next[i], gain_db: Number(e.target.value) }; p.setMsSideNodes(next)
                    }} disabled={!p.msEqEnabled} className="w-12 rounded bg-black/40 px-1 py-0.5 text-center font-mono text-white/70 border border-white/10" />
                    <span className="text-white/30">dB</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Transient Shaper */}
        <div className="rounded-xl border border-white/10 bg-black/30 p-3">
          <div className="flex items-center gap-2 mb-2">
            <Toggle enabled={p.trEnabled} onToggle={() => p.setTrEnabled(!p.trEnabled)} />
            <span className="text-xs font-medium text-white/70">{t('mix.transientShaper')}</span>
          </div>
          {p.trEnabled && (
            <div className="flex items-center gap-4">
              <label className="flex-1 space-y-1">
                <span className="text-[10px] text-white/40">{t('mix.attack')}</span>
                <input type="range" min={-12} max={12} step={0.5} value={p.trAttack}
                  onChange={(e) => p.setTrAttack(Number(e.target.value))} disabled={!p.trEnabled} className="w-full accent-violet-500" />
                <span className="block text-center font-mono text-[10px] text-white/50">
                  {p.trAttack > 0 ? '+' : ''}{p.trAttack.toFixed(1)} dB
                </span>
              </label>
              <label className="flex-1 space-y-1">
                <span className="text-[10px] text-white/40">{t('mix.sustain')}</span>
                <input type="range" min={-12} max={12} step={0.5} value={p.trSustain}
                  onChange={(e) => p.setTrSustain(Number(e.target.value))} disabled={!p.trEnabled} className="w-full accent-violet-500" />
                <span className="block text-center font-mono text-[10px] text-white/50">
                  {p.trSustain > 0 ? '+' : ''}{p.trSustain.toFixed(1)} dB
                </span>
              </label>
              <label className="flex-1 space-y-1">
                <span className="text-[10px] text-white/40">{t('mix.dryWet')}</span>
                <input type="range" min={0} max={1} step={0.01} value={p.trMix}
                  onChange={(e) => p.setTrMix(Number(e.target.value))} disabled={!p.trEnabled} className="w-full accent-violet-500" />
                <span className="block text-center font-mono text-[10px] text-white/50">
                  {Math.round(p.trMix * 100)}%
                </span>
              </label>
            </div>
          )}
        </div>

        {/* Sidechain Compression */}
        <div className="rounded-xl border border-white/10 bg-black/30 p-3">
          <div className="flex items-center gap-2 mb-2">
            <Toggle enabled={p.scEnabled} onToggle={() => p.setScEnabled(!p.scEnabled)} />
            <span className="text-xs font-medium text-white/70">{t('mix.sidechain')}</span>
          </div>
          {p.scEnabled && (
            <div className="space-y-2">
              <div className="flex items-center gap-3">
                <label className="flex-1">
                  <span className="text-[10px] text-white/40">{t('mix.scTrigger')}</span>
                  <select value={p.scTrigger} onChange={(e) => p.setScTrigger(e.target.value)}
                    className="mt-0.5 w-full rounded bg-black/40 px-2 py-1 text-xs text-white/70 border border-white/10">
                    <option value="kick">Kick</option>
                    <option value="snare">Snare</option>
                    <option value="hats">Hats</option>
                  </select>
                </label>
                <label className="flex-1">
                  <span className="text-[10px] text-white/40">{t('mix.amount')}</span>
                  <input type="number" value={p.scAmount} step={0.5} min={-12} max={0}
                    onChange={(e) => p.setScAmount(Number(e.target.value))}
                    className="mt-0.5 w-full rounded bg-black/40 px-2 py-1 text-center font-mono text-xs text-white/70 border border-white/10" />
                </label>
                <label className="flex-1">
                  <span className="text-[10px] text-white/40">{t('mix.dryWet')}</span>
                  <input type="range" min={0} max={1} step={0.01} value={p.scMix}
                    onChange={(e) => p.setScMix(Number(e.target.value))} disabled={!p.scEnabled} className="mt-1 w-full accent-violet-500" />
                  <span className="block text-center font-mono text-[10px] text-white/50">
                    {Math.round(p.scMix * 100)}%
                  </span>
                </label>
              </div>
            </div>
          )}
        </div>

        {/* De-Esser */}
        <div className="rounded-xl border border-white/10 bg-black/30 p-3">
          <div className="flex items-center gap-2 mb-2">
            <Toggle enabled={p.deessEnabled} onToggle={() => p.setDeessEnabled(!p.deessEnabled)} />
            <span className="text-xs font-medium text-white/70">{t('mix.deesser')}</span>
          </div>
          {p.deessEnabled && (
            <div className="space-y-2">
              <div className="flex items-center gap-3">
                <label className="flex-1">
                  <span className="text-[10px] text-white/40">{t('mix.deessFreq')} (Hz)</span>
                  <input type="number" value={p.deessFreq} step={100} min={2000} max={12000}
                    onChange={(e) => p.setDeessFreq(Number(e.target.value))}
                    className="mt-0.5 w-full rounded bg-black/40 px-2 py-1 text-center font-mono text-xs text-white/70 border border-white/10" />
                </label>
                <label className="flex-1">
                  <span className="text-[10px] text-white/40">{t('mix.deessThreshold')} (dB)</span>
                  <input type="number" value={p.deessThreshold} step={1} min={-40} max={0}
                    onChange={(e) => p.setDeessThreshold(Number(e.target.value))}
                    className="mt-0.5 w-full rounded bg-black/40 px-2 py-1 text-center font-mono text-xs text-white/70 border border-white/10" />
                </label>
                <label className="flex-1">
                  <span className="text-[10px] text-white/40">{t('mix.deessReduction')} (dB)</span>
                  <input type="number" value={p.deessMaxReduction} step={1} min={1} max={24}
                    onChange={(e) => p.setDeessMaxReduction(Number(e.target.value))}
                    className="mt-0.5 w-full rounded bg-black/40 px-2 py-1 text-center font-mono text-xs text-white/70 border border-white/10" />
                </label>
                <label className="flex-1">
                  <span className="text-[10px] text-white/40">{t('mix.deessMode')}</span>
                  <select value={p.deessMode} onChange={(e) => p.setDeessMode(e.target.value as 'split' | 'wide')}
                    className="mt-0.5 w-full rounded bg-black/40 px-2 py-1 text-xs text-white/70 border border-white/10">
                    <option value="split">{t('mix.deessSplit')}</option>
                    <option value="wide">{t('mix.deessWide')}</option>
                  </select>
                </label>
                <label className="flex-1">
                  <span className="text-[10px] text-white/40">{t('mix.dryWet')}</span>
                  <input type="range" min={0} max={1} step={0.01} value={p.deessMix}
                    onChange={(e) => p.setDeessMix(Number(e.target.value))} className="mt-1 w-full accent-violet-500" />
                  <span className="block text-center font-mono text-[10px] text-white/50">
                    {Math.round(p.deessMix * 100)}%
                  </span>
                </label>
              </div>
            </div>
          )}
        </div>
      </div>
    </Card>
  )
}
