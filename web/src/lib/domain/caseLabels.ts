/** Port of case_labels.py — phase-aware catalog / VIP labels. */

const ORDER_NUMBERS: Record<string, string> = {
  '1:1': '12-26-02-0002',
  '1:2': '12-26-02-0004',
  '1:3': '12-26-02-0008',
  '1:4': '12-26-02-0010',
  '1:5': '12-26-02-0012',
  '1:6': '12-26-02-0014',
  '1:7': '12-26-02-0016',
  '1:8': '12-26-02-0018',
  '1:9': '12-26-02-0020',
  '1:10': '12-26-02-0022',
  '1:11': '12-26-02-0024',
  '1:12': '12-26-02-0028',
  '1:13': '12-26-02-0032',
  '1:14': '12-26-02-0034',
  '1:15': '12-26-02-0036',
  '1:16': '12-26-02-0038',
  '2:1': '12-26-02-0003',
  '2:2': '12-26-02-0005',
  '2:3': '12-26-02-0009',
  '2:4': '12-26-02-0011',
  '2:5': '12-26-02-0013',
  '2:6': '12-26-02-0015',
  '2:7': '12-26-02-0017',
  '2:8': '12-26-02-0019',
  '2:9': '12-26-02-0021',
  '2:10': '12-26-02-0023',
  '2:11': '12-26-02-0025',
  '2:12': '12-26-02-0029',
  '2:13': '12-26-02-0033',
  '2:14': '12-26-02-0035',
  '2:15': '12-26-02-0037',
  '2:16': '12-26-02-0039',
}

export type CaseLabelInput = {
  phase_no?: number | null
  set_no: number
  case_no: number
  catalog_label?: string | null
  order_number?: string | null
}

export function casePhaseNo(row: CaseLabelInput): number {
  const raw = row.phase_no
  if (raw == null) return 1
  const n = Number(raw)
  return Number.isFinite(n) ? n : 1
}

export function caseCatalogLabel(row: CaseLabelInput): string {
  if (row.catalog_label) return String(row.catalog_label)
  if (casePhaseNo(row) === 2) {
    return `L${String(row.case_no).padStart(2, '0')}`
  }
  return `${row.case_no}${row.set_no === 1 ? 'A' : 'B'}`
}

export function caseOrderNumber(row: CaseLabelInput): string | null {
  if (row.order_number) return String(row.order_number)
  // Phase-2 reuses set_no=1 with case_no 1–30 — never fall back to phase-1 map.
  if (casePhaseNo(row) !== 1) return null
  return ORDER_NUMBERS[`${row.set_no}:${row.case_no}`] ?? null
}

export function caseLabel(row: CaseLabelInput): string {
  const order = caseOrderNumber(row)
  const prefix = casePhaseNo(row) === 2 ? 'Live case' : 'Case'
  const label = `${prefix} ${caseCatalogLabel(row)}`
  return order ? `${label} · ${order}` : label
}

export function caseTitle(row: CaseLabelInput): string {
  const order = caseOrderNumber(row)
  const title =
    casePhaseNo(row) === 2
      ? `Live case ${caseCatalogLabel(row)}`
      : `Set ${row.set_no} · Case ${caseCatalogLabel(row)}`
  return order ? `${title} · ${order}` : title
}
