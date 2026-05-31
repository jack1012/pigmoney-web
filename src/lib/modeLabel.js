// mode 顯示文字映射
// DB 端值保持原樣（向後相容豬頭記帳.exe），UI 端顯示新名稱
//
//   信用卡支出 → 投資支出（買股本金移轉）
//   信用卡收入 → 投資收入（賣股本金回流）
//   現金支出   → 現金支出
//   收入       → 收入

export const MODE_LABEL = {
  '現金支出':   '現金支出',
  '信用卡支出': '投資支出',
  '信用卡收入': '投資收入',
  '收入':       '收入',
}

// 給 <select> / 篩選按鈕用的選項清單（保留 DB 值順序）
export const MODE_OPTIONS = [
  { value: '現金支出',   label: '現金支出' },
  { value: '信用卡支出', label: '投資支出' },
  { value: '信用卡收入', label: '投資收入' },
  { value: '收入',       label: '收入' },
]

export function modeLabel(m) {
  return MODE_LABEL[m] ?? m
}

// 是否為「投資資產搬移」類型（不算家庭收支，但要單獨追蹤）
export function isInvestTransfer(m) {
  return m === '信用卡支出' || m === '信用卡收入'
}
