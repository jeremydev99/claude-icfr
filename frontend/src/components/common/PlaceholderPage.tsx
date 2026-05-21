import { Construction } from 'lucide-react'

interface PlaceholderPageProps {
  title: string
  description: string
}

export default function PlaceholderPage({ title, description }: PlaceholderPageProps) {
  return (
    <div className="p-6">
      <div className="mb-6">
        <h1 className="text-2xl font-semibold">{title}</h1>
        <p className="mt-2 text-muted-foreground">{description}</p>
      </div>
      <div className="flex flex-col items-center justify-center rounded-lg border border-dashed p-12">
        <Construction className="h-12 w-12 text-muted-foreground" />
        <p className="mt-4 text-sm text-muted-foreground">준비중입니다 — Phase 1에서 구현 예정입니다.</p>
      </div>
    </div>
  )
}
