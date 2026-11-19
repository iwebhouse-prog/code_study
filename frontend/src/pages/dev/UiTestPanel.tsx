import type { ReactNode } from 'react'
import { Button, type ButtonProps } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'

const TAILWIND_CLASSES = [
  { name: 'bg-blue-500', css: 'background-color: #3b82f6', meaning: '배경을 파란색으로 칠합니다.' },
  { name: 'text-white', css: 'color: #ffffff', meaning: '글자를 흰색으로 만듭니다.' },
  { name: 'p-4', css: 'padding: 1rem', meaning: '네 방향 안쪽 여백을 16px 줍니다.' },
  { name: 'rounded-lg', css: 'border-radius: 0.5rem', meaning: '모서리를 8px 둥글게 만듭니다.' },
]

const VARIANTS: NonNullable<ButtonProps['variant']>[] = ['default', 'outline', 'ghost']

const CARDS = ['카드 1', '카드 2', '카드 3']

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section aria-label={title} className="space-y-3 rounded-lg border p-4">
      <h2 className="text-lg font-semibold">{title}</h2>
      {children}
    </section>
  )
}

// Development-only panel on /dev-test for checking Tailwind and shadcn/ui.
export default function UiTestPanel() {
  return (
    <div className="mt-8 space-y-6">
      <Section title="Tailwind 클래스 테스트">
        <div data-testid="tailwind-sample" className="rounded-lg bg-blue-500 p-4 text-white">
          이 상자에 네 클래스가 모두 적용되어 있습니다.
        </div>
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="border-b">
              <th className="py-2 pr-4">클래스</th>
              <th className="py-2 pr-4">적용되는 CSS</th>
              <th className="py-2">설명</th>
            </tr>
          </thead>
          <tbody>
            {TAILWIND_CLASSES.map(({ name, css, meaning }) => (
              <tr key={name} className="border-b">
                <td className="py-2 pr-4 font-mono">{name}</td>
                <td className="py-2 pr-4 font-mono">{css}</td>
                <td className="py-2">{meaning}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Section>

      <Section title="shadcn/ui 버튼 테스트">
        <div className="flex gap-2">
          {VARIANTS.map((variant) => (
            <Button key={variant} variant={variant} onClick={() => window.alert(variant)}>
              {variant}
            </Button>
          ))}
        </div>
      </Section>

      <Section title="반응형 디자인 테스트">
        <p className="text-sm text-muted-foreground">
          모바일 1열, 태블릿(md, 768px 이상) 2열, 데스크톱(lg, 1024px 이상) 3열
        </p>
        <div
          data-testid="responsive-grid"
          className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3"
        >
          {CARDS.map((title) => (
            <Card key={title}>
              <CardHeader>
                <CardTitle>{title}</CardTitle>
              </CardHeader>
              <CardContent className="text-sm text-muted-foreground">
                창 너비에 따라 열 수가 바뀝니다.
              </CardContent>
            </Card>
          ))}
        </div>
      </Section>
    </div>
  )
}
