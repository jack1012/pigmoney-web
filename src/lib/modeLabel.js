// mode 顯示文字映射
// DB 端值保持原樣（向後相容豬頭記帳.exe），UI 端顯示新名稱
//
//   信用卡支出 → 資金轉移（買股本金移轉、房貸本金等，現金換資產）
//   信用卡收入 → 資金回收（賣股本金回流等，本金變現）
//   現金支出   → 現金支出
//   收入       → 收入

export const MODE_LABEL = {
  '現金支出':   '現金支出',
  '信用卡支出': '資金轉移',
  '信用卡收入': '資金回收',
  '收入':       '收入',
}

// 給 <select> / 篩選按鈕用的選項清單（保留 DB 值順序）
export const MODE_OPTIONS = [
  { value: '現金支出',   label: '現金支出' },
  { value: '信用卡支出', label: '資金轉移' },
  { value: '信用卡收入', label: '資金回收' },
  { value: '收入',       label: '收入' },
]

export function modeLabel(m) {
  return MODE_LABEL[m] ?? m
}

// 是否為「投資資產搬移」類型（不算家庭收支，但要單獨追蹤）
export function isInvestTransfer(m) {
  return m === '信用卡支出' || m === '信用卡收入'
}
