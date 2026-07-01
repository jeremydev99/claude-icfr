import { type ClassValue, clsx } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function formatDate(dateStr: string | null | undefined): string {
  if (!dateStr) return '—'
  const datePart = dateStr.slice(0, 10)
  if (!/^\d{4}-\d{2}-\d{2}$/.test(datePart)) return '—'
  return datePart
}
