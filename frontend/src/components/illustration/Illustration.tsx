import { cn } from '@/lib/utils'
import { SLOTS, type IllustrationSlot } from './manifest'

// 생성 이미지 — 파일이 있으면 그 슬롯에 쓰인다. 없으면 아래 대체 그래픽.
const FILES = import.meta.glob('/src/assets/illustrations/*.webp', { eager: true, query: '?url', import: 'default' }) as Record<string, string>

export function illustrationUrl(slot: IllustrationSlot): string | null {
  return FILES[`/src/assets/illustrations/${slot}.webp`] ?? null
}

/**
 * 일러스트 한 장. 이미지가 아직 없으면 브랜드 그라데이션 위에 은은한 격자·광원을 그린 대체 그래픽을 보여준다
 * (빈 자리나 깨진 이미지 아이콘이 보이지 않게). 장식 이미지라 스크린리더에는 alt 만 읽힌다.
 */
export default function Illustration({ slot, className, eager }: { slot: IllustrationSlot; className?: string; eager?: boolean }) {
  const url = illustrationUrl(slot)
  const spec = SLOTS[slot]
  if (url) {
    return (
      <img
        src={url}
        alt={spec.alt}
        loading={eager ? 'eager' : 'lazy'}
        decoding="async"
        draggable={false}
        className={cn('select-none object-contain', !spec.dark && 'mix-blend-multiply', className)}
      />
    )
  }
  return (
    <div role="img" aria-label={spec.alt} className={cn('relative overflow-hidden rounded-2xl', className)}>
      <div className="absolute inset-0 bg-gradient-to-br from-brand-from/15 via-accent to-brand-to/15" />
      <svg className="absolute inset-0 h-full w-full text-primary/10" aria-hidden="true">
        <defs>
          <pattern id={`grid-${slot}`} width="24" height="24" patternUnits="userSpaceOnUse">
            <path d="M24 0H0V24" fill="none" stroke="currentColor" strokeWidth="1" />
          </pattern>
        </defs>
        <rect width="100%" height="100%" fill={`url(#grid-${slot})`} />
      </svg>
      <div className="absolute -right-8 -top-8 h-32 w-32 rounded-full bg-brand-to/25 blur-2xl" />
      <div className="absolute -bottom-10 -left-6 h-36 w-36 rounded-full bg-brand-from/20 blur-2xl" />
    </div>
  )
}
