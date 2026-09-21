import { Link } from 'react-router-dom'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'

interface Props {
  title: string
  description: string
  /** 이미 있는 엔드포인트. 붙일 때 어디를 보면 되는지 화면에 남겨 둔다. */
  endpoints: string[]
  note?: string
}

/**
 * "화면 미구현, API 있음" 자리 (B-2).
 *
 * **"준비중"과 구분해서 적는다** — 붙이기만 하면 되는 것과 아무것도 없는 것은 남은 일의
 * 크기가 다르다. 대시보드 배지 `api` 와 같은 구분이다.
 */
export default function ApiOnlyPlaceholder({ title, description, endpoints, note }: Props) {
  return (
    <div className="p-6">
      <div className="mb-4 flex items-center gap-3">
        <h1 className="text-2xl font-semibold">{title}</h1>
        <Badge variant="secondary">API 있음 · 화면 미구현</Badge>
      </div>
      <p className="mb-4 text-sm text-muted-foreground">{description}</p>

      <Card className="max-w-2xl">
        <CardHeader>
          <CardTitle className="text-base">이미 있는 API</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          <ul className="space-y-1">
            {endpoints.map((e) => (
              <li key={e} className="font-mono text-xs text-muted-foreground">
                {e}
              </li>
            ))}
          </ul>
          {note && <p className="pt-2 text-xs text-muted-foreground">{note}</p>}
          <p className="pt-2 text-xs text-muted-foreground">
            현황은 <Link to="/dashboard" className="underline">대시보드</Link>에서 볼 수 있습니다.
          </p>
        </CardContent>
      </Card>
    </div>
  )
}
