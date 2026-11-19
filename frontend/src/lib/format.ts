/** "2026년 11월 10일" for an ISO timestamp. */
export function formatKoreanDate(iso: string): string {
  return new Date(iso).toLocaleDateString('ko-KR', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  })
}
