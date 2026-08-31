import type { ReactNode, ButtonHTMLAttributes } from 'react'

export function Card({
  children,
  className = '',
}: {
  children: ReactNode
  className?: string
}) {
  return (
    <div
      className={`rounded-2xl border border-white/[0.09] bg-[#11121c]/75 p-5 shadow-[0_8px_32px_rgba(0,0,0,0.45)] backdrop-blur-2xl transition-all duration-200 ${className}`}
    >
      {children}
    </div>
  )
}

export function SectionTitle({
  title,
  subtitle,
  right,
}: {
  title: string
  subtitle?: string
  right?: ReactNode
}) {
  return (
    <div className="mb-5 flex items-end justify-between gap-4 border-b border-white/[0.06] pb-4">
      <div>
        <h2 className="text-xl font-bold tracking-tight text-white flex items-center gap-2">
          {title}
        </h2>
        {subtitle && (
          <p className="mt-1 text-sm text-white/50">{subtitle}</p>
        )}
      </div>
      {right}
    </div>
  )
}

type ButtonVariant = 'primary' | 'ghost' | 'outline'

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant
}

export function Button({
  variant = 'primary',
  className = '',
  ...props
}: ButtonProps) {
  const base =
    'inline-flex items-center justify-center gap-2 rounded-xl px-4 py-2 text-sm font-semibold transition-all duration-200 disabled:cursor-not-allowed disabled:opacity-40 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-violet-400 active:scale-[0.98]'
  const styles = {
    primary:
      'bg-gradient-to-r from-violet-600 via-fuchsia-600 to-pink-600 text-white hover:brightness-110 shadow-[0_0_20px_rgba(168,85,247,0.4)] hover:shadow-[0_0_25px_rgba(217,70,239,0.6)] border border-white/20',
    ghost: 'text-white/70 hover:bg-white/[0.08] hover:text-white',
    outline:
      'border border-white/15 bg-white/[0.03] text-white/90 hover:border-violet-400/60 hover:bg-violet-500/10 hover:shadow-[0_0_15px_rgba(139,92,246,0.25)]',
  }[variant]
  return <button className={`${base} ${styles} ${className}`} {...props} />
}

export function Badge({
  children,
  tone = 'neutral',
  className = '',
}: {
  children: ReactNode
  tone?: 'neutral' | 'violet' | 'green' | 'amber' | 'red'
  className?: string
}) {
  const tones = {
    neutral: 'border-white/15 bg-white/[0.05] text-white/70',
    violet: 'border-violet-400/40 bg-violet-500/15 text-violet-300 shadow-[0_0_10px_rgba(167,139,250,0.2)]',
    green: 'border-emerald-400/40 bg-emerald-500/15 text-emerald-300 shadow-[0_0_10px_rgba(52,211,153,0.2)]',
    amber: 'border-amber-400/40 bg-amber-500/15 text-amber-300 shadow-[0_0_10px_rgba(251,191,36,0.2)]',
    red: 'border-red-400/40 bg-red-500/15 text-red-300 shadow-[0_0_10px_rgba(248,113,113,0.2)]',
  }[tone]
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-xs font-semibold ${tones} ${className}`}
    >
      {children}
    </span>
  )
}

export function Slider({
  label,
  value,
  min,
  max,
  step = 0.5,
  unit = '',
  onChange,
  format,
}: {
  label: string
  value: number
  min: number
  max: number
  step?: number
  unit?: string
  onChange: (v: number) => void
  format?: (v: number) => string
}) {
  return (
    <label className="block select-none">
      <span className="mb-1 flex items-center justify-between text-xs text-white/55">
        <span>{label}</span>
        <span className="font-mono text-white/80">
          {format ? format(value) : `${value > 0 && min < 0 ? '+' : ''}${value}${unit}`}
        </span>
      </span>
      <input
        type="range"
        className="slider"
        value={value}
        min={min}
        max={max}
        step={step}
        onChange={(e) => onChange(Number(e.target.value))}
      />
    </label>
  )
}

export function Spinner({ className = '' }: { className?: string }) {
  return (
    <span
      className={`inline-block h-4 w-4 animate-spin rounded-full border-2 border-white/25 border-t-violet-300 ${className}`}
      role="status"
      aria-label="Loading"
    />
  )
}

export function EmptyState({
  icon,
  message,
  hint,
}: {
  icon?: ReactNode
  message: string
  hint?: string
}) {
  return (
    <Card className="flex flex-col items-center justify-center gap-3 px-8 py-16 text-center">
      {icon && <div className="text-white/20">{icon}</div>}
      <p className="text-sm font-medium text-white/60">{message}</p>
      {hint && <p className="max-w-md text-xs leading-relaxed text-white/35">{hint}</p>}
    </Card>
  )
}
