// Learning document as the UI uses it (camelCase). The 7 chapters follow
// backend/src/services/ai/document_schema.py.

export interface Chapter1 {
  title: string
  summary: string
}

export interface Concept {
  name: string
  explanation: string
  analogy: string
  example: string
  useCases: string
}

export interface Chapter2 {
  title: string
  concepts: Concept[]
}

export interface FileBreakdown {
  filePath: string
  role: string
}

export interface Chapter3 {
  title: string
  /** Mermaid flowchart source. */
  flowchart: string
  fileBreakdown: FileBreakdown[]
}

export interface LineExplanation {
  filePath: string
  lineStart: number
  lineEnd: number
  code: string
  whatItDoes: string
  syntaxBreakdown: string
  analogy: string
  alternativeExample: string
  notes: string
}

export interface Chapter4 {
  title: string
  explanations: LineExplanation[]
}

export interface FlowStep {
  step: number
  description: string
  dataState: string
}

export interface Chapter5 {
  title: string
  steps: FlowStep[]
}

export interface KeyConcept {
  name: string
  whatItIs: string
  whyUsed: string
  whereApplied: string
}

export interface Chapter6 {
  title: string
  concepts: KeyConcept[]
}

export interface Mistake {
  wrong: string
  right: string
  why: string
  fix: string
}

export interface Chapter7 {
  title: string
  mistakes: Mistake[]
}

export interface DocumentContent {
  chapter1: Chapter1
  chapter2: Chapter2
  chapter3: Chapter3
  chapter4: Chapter4
  chapter5: Chapter5
  chapter6: Chapter6
  chapter7: Chapter7
}
