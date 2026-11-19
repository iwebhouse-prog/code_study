import type { DocumentContent } from '../../src/services/document-types'

// Learning document content as the backend sends it (contracts/documents-api.md).
export const RAW_CONTENT = {
  chapter1: { title: '이 코드가 하는 일', summary: '숫자가 짝수인지 홀수인지 알려 줍니다.' },
  chapter2: {
    title: '미리 알아둘 개념',
    concepts: [
      {
        name: '함수(def)',
        explanation: '자주 쓰는 기능에 이름을 붙인 상자입니다.',
        analogy: '믹서기 같은 도구입니다.',
        example: "def hello(): print('안녕!')",
        use_cases: '반복되는 일을 줄일 때 씁니다.',
      },
      {
        name: '나머지 연산(%)',
        explanation: '나눈 뒤 남는 수를 구합니다.',
        analogy: '사탕을 똑같이 나누고 남은 개수입니다.',
        example: '7 % 2 == 1',
        use_cases: '짝수 홀수 판별에 씁니다.',
      },
    ],
  },
  chapter3: {
    title: '코드 구조 한눈에 보기',
    flowchart: 'graph TD; A[시작] --> B[끝];',
    file_breakdown: [
      { file_path: 'even_odd.py', role: '짝수 홀수를 판별합니다.' },
      { file_path: 'main.py', role: '결과를 화면에 보여 줍니다.' },
    ],
  },
  chapter4: {
    title: '한 줄씩 살펴보기',
    explanations: [
      {
        file_path: 'even_odd.py',
        line_start: 1,
        line_end: 2,
        code: 'def is_even(number):\n    return number % 2 == 0',
        what_it_does: '짝수인지 판단하는 함수를 만듭니다.',
        syntax_breakdown: 'def는 함수를 만든다는 뜻입니다.',
        analogy: '2로 나눠 보는 판독기입니다.',
        alternative_example: 'def check(n): return n % 2 != 1',
        notes: '콜론(:)을 잊지 마세요.',
      },
      {
        file_path: 'even_odd.py',
        line_start: 4,
        line_end: 4,
        code: 'print(is_even(2))',
        what_it_does: '결과를 출력합니다.',
        syntax_breakdown: 'print는 화면에 보여 줍니다.',
        analogy: '게시판에 붙이는 일입니다.',
        alternative_example: 'print(2 % 2 == 0)',
        notes: '',
      },
      {
        file_path: 'main.py',
        line_start: 1,
        line_end: 3,
        code: 'for n in range(1, 6):\n    pass\n',
        what_it_does: '1부터 5까지 반복합니다.',
        syntax_breakdown: 'range(1, 6)은 1~5입니다.',
        analogy: '출석부를 차례로 부르는 일입니다.',
        alternative_example: 'while n < 6:',
        notes: '끝 숫자는 포함되지 않습니다.',
      },
    ],
  },
  chapter5: {
    title: '실행 흐름 따라가기',
    steps: [
      { step: 1, description: 'n이 1일 때 홀수입니다.', data_state: 'n = 1' },
      { step: 2, description: 'n이 2일 때 짝수입니다.', data_state: 'n = 2' },
    ],
  },
  chapter6: {
    title: '핵심 개념 정리',
    concepts: [
      {
        name: 'Boolean',
        what_it_is: '참 또는 거짓입니다.',
        why_used: '조건을 판단하려고 씁니다.',
        where_applied: 'if문에 씁니다.',
      },
    ],
  },
  chapter7: {
    title: '자주 하는 실수',
    mistakes: [
      {
        wrong: 'range(1, 5)',
        right: 'range(1, 6)',
        why: '5가 빠집니다.',
        fix: '끝 숫자에 1을 더합니다.',
      },
    ],
  },
}

export const APP_CONTENT: DocumentContent = {
  chapter1: RAW_CONTENT.chapter1,
  chapter2: {
    title: RAW_CONTENT.chapter2.title,
    concepts: RAW_CONTENT.chapter2.concepts.map((c) => ({
      name: c.name,
      explanation: c.explanation,
      analogy: c.analogy,
      example: c.example,
      useCases: c.use_cases,
    })),
  },
  chapter3: {
    title: RAW_CONTENT.chapter3.title,
    flowchart: RAW_CONTENT.chapter3.flowchart,
    fileBreakdown: RAW_CONTENT.chapter3.file_breakdown.map((f) => ({
      filePath: f.file_path,
      role: f.role,
    })),
  },
  chapter4: {
    title: RAW_CONTENT.chapter4.title,
    explanations: RAW_CONTENT.chapter4.explanations.map((e) => ({
      filePath: e.file_path,
      lineStart: e.line_start,
      lineEnd: e.line_end,
      code: e.code,
      whatItDoes: e.what_it_does,
      syntaxBreakdown: e.syntax_breakdown,
      analogy: e.analogy,
      alternativeExample: e.alternative_example,
      notes: e.notes,
    })),
  },
  chapter5: {
    title: RAW_CONTENT.chapter5.title,
    steps: RAW_CONTENT.chapter5.steps.map((s) => ({
      step: s.step,
      description: s.description,
      dataState: s.data_state,
    })),
  },
  chapter6: {
    title: RAW_CONTENT.chapter6.title,
    concepts: RAW_CONTENT.chapter6.concepts.map((c) => ({
      name: c.name,
      whatItIs: c.what_it_is,
      whyUsed: c.why_used,
      whereApplied: c.where_applied,
    })),
  },
  chapter7: RAW_CONTENT.chapter7,
}

export const DOC_TASK_ID = '22222222-2222-4222-8222-222222222222'

export function rawStatus(status: string, extra: Record<string, unknown> = {}) {
  return {
    task_id: DOC_TASK_ID,
    status,
    started_at: null,
    completed_at: null,
    estimated_seconds_remaining: null,
    error: null,
    ...extra,
  }
}

export const RAW_DOCUMENT = {
  task_id: DOC_TASK_ID,
  status: 'completed',
  completed_at: '2026-11-18T01:02:00+00:00',
  content: RAW_CONTENT,
}

// GET /tasks/{id}/code for the files the content above talks about.
export const RAW_CODE = {
  task_id: DOC_TASK_ID,
  detected_language: 'python',
  files: [
    {
      id: 'f-1',
      file_name: 'even_odd.py',
      file_path: 'even_odd.py',
      file_extension: '.py',
      file_size_bytes: 60,
      language: 'python',
      content: 'def is_even(number):\n    return number % 2 == 0\n\nprint(is_even(2))\n',
    },
    {
      id: 'f-2',
      file_name: 'main.py',
      file_path: 'main.py',
      file_extension: '.py',
      file_size_bytes: 30,
      language: 'python',
      content: 'for n in range(1, 6):\n    pass\n',
    },
  ],
}
