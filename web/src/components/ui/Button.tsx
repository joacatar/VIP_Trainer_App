import type { ButtonHTMLAttributes, ReactNode } from 'react'

const variants = {
  primary:
    'bg-primary text-primary-fg hover:opacity-90 disabled:opacity-50',
  secondary:
    'bg-surface text-text border border-border hover:bg-surface-2 disabled:opacity-50',
  danger: 'bg-danger text-white hover:opacity-90 disabled:opacity-50',
  ghost: 'bg-transparent text-muted hover:text-text hover:bg-surface-2',
} as const

export function Button({
  variant = 'primary',
  className = '',
  children,
  type = 'button',
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: keyof typeof variants
  children: ReactNode
}) {
  return (
    <button
      type={type}
      className={`inline-flex items-center justify-center gap-2 rounded-md px-3.5 py-2 text-sm font-medium transition ${variants[variant]} ${className}`}
      {...props}
    >
      {children}
    </button>
  )
}
