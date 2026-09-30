import { useMemo, useState } from 'react'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { RULES, SAMPLE_VALUES, TEMPLATES, placeholdersOf, renderTemplate } from '../templates'

/**
 * 메일발송 — 초안. 발송 백엔드가 없으므로 템플릿 편집은 화면 안에서만 유지되고 저장되지 않는다.
 */
export default function NotificationPage() {
  return (
    <div className="space-y-4 p-6">
      <div className="flex flex-wrap items-center gap-2">
        <h1 className="text-2xl font-bold">메일발송</h1>
        <Badge variant="outline" className="border-amber-300 bg-amber-50 text-amber-900">초안 — 발송 기능 미연결</Badge>
      </div>
      <p className="text-sm text-muted-foreground">
        내부회계관리제도 업무 알림의 표준 템플릿·발송 규칙·발송 이력을 관리합니다.
      </p>
      <Tabs defaultValue="templates" className="space-y-4">
        <TabsList>
          <TabsTrigger value="templates">템플릿</TabsTrigger>
          <TabsTrigger value="rules">발송 규칙</TabsTrigger>
          <TabsTrigger value="history">발송 이력</TabsTrigger>
        </TabsList>
        <TabsContent value="templates"><TemplatesTab /></TabsContent>
        <TabsContent value="rules"><RulesTab /></TabsContent>
        <TabsContent value="history"><HistoryTab /></TabsContent>
      </Tabs>
    </div>
  )
}

function TemplatesTab() {
  const [selectedId, setSelectedId] = useState(TEMPLATES[0].id)
  // 편집본은 화면 상태에만 둔다(저장 API 없음).
  const [edits, setEdits] = useState<Record<string, { subject: string; body: string }>>({})
  const [values, setValues] = useState<Record<string, string>>(SAMPLE_VALUES)

  const base = TEMPLATES.find((t) => t.id === selectedId) ?? TEMPLATES[0]
  const current = edits[base.id] ?? { subject: base.subject, body: base.body }
  const keys = useMemo(() => placeholdersOf(current.subject + '\n' + current.body), [current.subject, current.body])
  const update = (patch: Partial<{ subject: string; body: string }>) =>
    setEdits((e) => ({ ...e, [base.id]: { ...current, ...patch } }))

  return (
    <div className="grid gap-4 lg:grid-cols-[220px_1fr_1fr]">
      <Card>
        <CardHeader className="pb-2"><CardTitle className="text-base">표준 템플릿</CardTitle></CardHeader>
        <CardContent className="p-2">
          <ul className="space-y-1">
            {TEMPLATES.map((t) => (
              <li key={t.id}>
                <button
                  type="button"
                  onClick={() => setSelectedId(t.id)}
                  className={`w-full rounded-md px-3 py-2 text-left text-sm hover:bg-muted ${t.id === base.id ? 'bg-muted font-semibold' : ''}`}
                >
                  <span className="mr-2 text-xs text-muted-foreground">{t.category}</span>
                  {t.name}
                  {edits[t.id] && <span className="ml-1 text-xs text-amber-700">(수정됨)</span>}
                </button>
              </li>
            ))}
          </ul>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="flex items-center justify-between text-base">
            {base.name}
            {edits[base.id] && (
              <button
                type="button"
                className="text-xs font-normal text-muted-foreground underline"
                onClick={() => setEdits((e) => { const n = { ...e }; delete n[base.id]; return n })}
              >
                원래대로
              </button>
            )}
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="space-y-1">
            <Label htmlFor="tpl-subject">제목</Label>
            <Input id="tpl-subject" value={current.subject} onChange={(e) => update({ subject: e.target.value })} />
          </div>
          <div className="space-y-1">
            <Label htmlFor="tpl-body">본문</Label>
            <Textarea id="tpl-body" rows={12} value={current.body} onChange={(e) => update({ body: e.target.value })} />
          </div>
          <p className="text-xs text-muted-foreground">
            치환자: {'{{담당자}}'}, {'{{통제코드}}'}, {'{{통제명}}'}, {'{{기한}}'}, {'{{회계연도}}'}, {'{{미비점코드}}'}, {'{{심각도}}'}, {'{{재무제표}}'}, {'{{링크}}'}, {'{{발신자}}'}
            <br />편집 내용은 저장되지 않습니다(초안).
          </p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-2"><CardTitle className="text-base">미리보기 (샘플 값)</CardTitle></CardHeader>
        <CardContent className="space-y-3">
          <div className="grid grid-cols-2 gap-2">
            {keys.map((k) => (
              <div key={k} className="space-y-0.5">
                <Label className="text-xs text-muted-foreground" htmlFor={`v-${k}`}>{k}</Label>
                <Input
                  id={`v-${k}`}
                  className="h-8 text-sm"
                  value={values[k] ?? ''}
                  onChange={(e) => setValues((v) => ({ ...v, [k]: e.target.value }))}
                />
              </div>
            ))}
          </div>
          <div className="rounded-md border bg-muted/30 p-3">
            <p className="border-b pb-2 text-sm font-semibold">{renderTemplate(current.subject, values)}</p>
            <pre className="mt-2 whitespace-pre-wrap break-words font-sans text-sm">{renderTemplate(current.body, values)}</pre>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}

function RulesTab() {
  const nameOf = (id: string) => TEMPLATES.find((t) => t.id === id)?.name ?? id
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-base">발송 규칙 (샘플)</CardTitle>
        <p className="text-sm text-muted-foreground">
          업무 상태 전환·기한을 트리거로 자동 발송하는 규칙 예시입니다. 규칙 저장·스케줄러는 아직 없습니다.
        </p>
      </CardHeader>
      <CardContent>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[640px] text-sm">
            <thead>
              <tr className="border-b text-left text-muted-foreground">
                <th className="py-2 pr-3 font-medium">트리거</th>
                <th className="py-2 pr-3 font-medium">템플릿</th>
                <th className="py-2 pr-3 font-medium">수신자(역할)</th>
                <th className="py-2 pr-3 font-medium">시점</th>
                <th className="py-2 font-medium">상태</th>
              </tr>
            </thead>
            <tbody>
              {RULES.map((r) => (
                <tr key={r.trigger} className="border-b last:border-0">
                  <td className="py-2 pr-3">{r.trigger}</td>
                  <td className="py-2 pr-3">{nameOf(r.templateId)}</td>
                  <td className="py-2 pr-3">{r.recipients}</td>
                  <td className="py-2 pr-3">{r.timing}</td>
                  <td className="py-2"><Badge variant="secondary">미연결</Badge></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </CardContent>
    </Card>
  )
}

function HistoryTab() {
  return (
    <Card>
      <CardContent className="py-10 text-center">
        <p className="font-medium">발송 이력이 없습니다.</p>
        <p className="mt-2 text-sm text-muted-foreground">
          메일 발송 기능(SMTP·발송 큐)이 아직 연결되지 않았습니다. 연결 후에는 발송 일시·수신자·템플릿·결과(성공/실패)가 여기에 기록됩니다.
        </p>
      </CardContent>
    </Card>
  )
}
