import type { Config } from 'tailwindcss'
import animate from 'tailwindcss-animate'

// Colors are CSS variables from src/index.css so shadcn/ui components can be
// themed in one place.
const color = (name: string) => `hsl(var(--${name}))`
const pair = (name: string) => ({
  DEFAULT: color(name),
  foreground: color(`${name}-foreground`),
})

export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        background: color('background'),
        foreground: color('foreground'),
        border: color('border'),
        input: color('input'),
        ring: color('ring'),
        primary: pair('primary'),
        secondary: pair('secondary'),
        muted: pair('muted'),
        accent: pair('accent'),
        destructive: pair('destructive'),
        card: pair('card'),
        popover: pair('popover'),
      },
      borderRadius: {
        lg: 'var(--radius)',
        md: 'calc(var(--radius) - 2px)',
        sm: 'calc(var(--radius) - 4px)',
      },
      fontFamily: {
        sans: [
          '-apple-system',
          'BlinkMacSystemFont',
          '"Apple SD Gothic Neo"',
          '"Malgun Gothic"',
          '"Noto Sans KR"',
          'sans-serif',
        ],
      },
    },
  },
  plugins: [animate],
} satisfies Config
