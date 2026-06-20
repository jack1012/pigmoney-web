<script setup>
import { ref, computed, watch, nextTick, onMounted, onBeforeUnmount } from 'vue'
import { useMoneyStore } from '../stores/money.js'
import { rowsToObjects } from '../lib/db.js'
import {
  Chart, BarController, LineController, BarElement, PointElement, LineElement,
  CategoryScale, LinearScale, Tooltip, Legend, Filler,
} from 'chart.js'
Chart.register(
  BarController, LineController, BarElement, PointElement, LineElement,
  CategoryScale, LinearScale, Tooltip, Legend, Filler,
)

const store = useMoneyStore()

// ============== Tab / 選擇年份狀態 ==============
const activeTab = ref('yearly')          // 'yearly' | 'historical'
const selectedYear = ref(null)           // '2025'

// 支出大類 / 資產大類展開狀態
const expandedExpCat = ref(new Set())
function toggleExpCat(cno) {
  const s = new Set(expandedExpCat.value)
  s.has(cno) ? s.delete(cno) : s.add(cno)
  expandedExpCat.value = s
}
// 投資支出明細：股票（sno=101）列展開個別買進交易
const expandedInvest = ref(new Set())
function toggleInvest(sno) {
  const s = new Set(expandedInvest.value)
  s.has(sno) ? s.delete(sno) : s.add(sno)
  expandedInvest.value = s
}
const expandedAssetCat = ref(new Set())
function toggleAssetCat(key) {
  const s = new Set(expandedAssetCat.value)
  s.has(key) ? s.delete(key) : s.add(key)
  expandedAssetCat.value = s
}

// ============== 常數 ==============
// 對應 store.classBuckets 的 4 個桶位（label 對齊 BudgetPage 的 BUCKET_SECTIONS）
const EXPENSE_GROUPS = [
  { key: 'life',    name: '生活類',   color: '#10b981', note: '彈性可調' },
  { key: 'fixed',   name: '固定類',   color: '#3b82f6', note: '剛性' },
  { key: 'want',    name: '想要',     color: '#f59e0b', note: '一次性' },
  { key: 'invloss', name: '投資損失', color: '#8b5cf6', note: '已實現' },
]

const ASSET_GROUPS = [
  { key: 'cash',       name: '現金存款',    color: '#06b6d4', note: '流動性' },
  { key: 'invest',     name: '投資組合',    color: '#8b5cf6', note: '長期' },
  { key: 'realEstate', name: '動產 / 不動產', color: '#f59e0b', note: '不動' },
  { key: 'debt',       name: '負債',        color: '#ef4444', note: '扣除' },
]

// ============== Helpers ==============
const fmt = (n) => n == null || isNaN(n) ? '-' : '$' + Math.round(Number(n)).toLocaleString()
const fmtW = (n) => n == null || isNaN(n) ? '-' : (Number(n) / 10000).toFixed(1) + ' 萬'
const fmtPct = (n, base) => base ? (n / base * 100).toFixed(1) + '%' : '-'

// ============== SQLite 聚合資料 ==============
// 每年每個 cno 的支出總和
const yearCnoSpend = computed(() => {
  if (!store.db) return new Map()
  const rows = rowsToObjects(store.db.exec(
    `SELECT strftime('%Y', date) AS year, cno, SUM(spend) AS total
     FROM money WHERE uno=1
     GROUP BY year, cno`
  ))
  const m = new Map()
  for (const r of rows) {
    if (!m.has(r.year)) m.set(r.year, new Map())
    m.get(r.year).set(r.cno, Number(r.total ?? 0))
  }
  return m
})

// 每年「投資支出」= mode='信用卡支出' SUM（買股 + 還房貸本金 + 出借款 + 動產購置）
const yearInvestOutRaw = computed(() => {
  if (!store.db) return new Map()
  const rows = rowsToObjects(store.db.exec(
    `SELECT strftime('%Y', date) AS year, SUM(spend) AS total
     FROM money WHERE uno=1 AND mode='信用卡支出'
     GROUP BY year`
  ))
  const m = new Map()
  for (const r of rows) m.set(r.year, Number(r.total ?? 0))
  return m
})
// 每年「投資收入」= mode='信用卡收入' SUM（賣股本金回流 + 收回借款）
const yearInvestInRaw = computed(() => {
  if (!store.db) return new Map()
  const rows = rowsToObjects(store.db.exec(
    `SELECT strftime('%Y', date) AS year, SUM(spend) AS total
     FROM money WHERE uno=1 AND mode='信用卡收入'
     GROUP BY year`
  ))
  const m = new Map()
  for (const r of rows) m.set(r.year, Number(r.total ?? 0))
  return m
})
function yearInvestOut(y) { return yearInvestOutRaw.value.get(y) ?? 0 }
function yearInvestIn(y)  { return yearInvestInRaw.value.get(y) ?? 0 }

// 每年「投資淨額」= mode='信用卡支出'（買進）− mode='信用卡收入'（賣出本金回流）
// DB 仍存原字串以相容豬頭記帳.exe；UI 一律顯示「投資支出/投資收入」
const yearInvestSpend = computed(() => {
  if (!store.db) return new Map()
  const rows = rowsToObjects(store.db.exec(
    `SELECT strftime('%Y', date) AS year,
            SUM(CASE WHEN mode='信用卡支出' THEN spend
                     WHEN mode='信用卡收入' THEN -spend
                     ELSE 0 END) AS total
     FROM money WHERE uno=1 AND mode IN ('信用卡支出','信用卡收入')
     GROUP BY year`
  ))
  const m = new Map()
  for (const r of rows) m.set(r.year, Number(r.total ?? 0))
  return m
})

// 每年每個 (cno, sno) 的支出總和（給展開子項用）
const yearCnoSnoSpend = computed(() => {
  if (!store.db) return new Map()
  const rows = rowsToObjects(store.db.exec(
    `SELECT strftime('%Y', date) AS year, cno, sno, SUM(spend) AS total
     FROM money WHERE uno=1
     GROUP BY year, cno, sno`
  ))
  const m = new Map()
  for (const r of rows) {
    if (!m.has(r.year)) m.set(r.year, new Map())
    m.get(r.year).set(`${r.cno}-${r.sno ?? 0}`, Number(r.total ?? 0))
  }
  return m
})

// 找到「收入」 class 的 cno（fallback：用名稱 '收入' 查）
const incomeCno = computed(() => {
  const byBucket = store.classes.find(c => store.classBuckets[c.cno] === 'income')
  if (byBucket) return byBucket.cno
  return store.classes.find(c => c.name === '收入')?.cno ?? null
})

// 所有年份（從交易資料抽出，升序；圖表計算依賴此順序）
const allYears = computed(() =>
  [...yearCnoSpend.value.keys()].sort()
)
// 下拉選單用：遞減排列
const allYearsDesc = computed(() => [...allYears.value].reverse())

// 自動選最新年
watch(allYears, (ys) => {
  if (ys.length && !selectedYear.value) selectedYear.value = ys[ys.length - 1]
}, { immediate: true })

// 資產帳戶 ano -> category 對應
const anoCategory = computed(() => {
  const m = new Map()
  for (const a of store.assetAccounts) m.set(a.ano, a.category)
  return m
})
// ano -> name 對應（用來在「資金」桶內細分 現金 vs 股票）
const anoName = computed(() => {
  const m = new Map()
  for (const a of store.assetAccounts) m.set(a.ano, a.name)
  return m
})
// 名稱含 股票/基金/保單 視為「股票類」（投資組合）
const STOCK_NAME_RE = /股票|基金|保單/
function isStockAccount(name) {
  return STOCK_NAME_RE.test(name ?? '')
}

// 每年「使用日期」：兩類資產分開取
//   現金/投資 (cashDate)    = 當年最新月度（非 -12-31）；沒有就跨年往前找最近月度（→ fallback）
//   動產/負債 (yearEndDate) = 當年 -12-31；沒有就往前找最近 -12-31（→ fallback）
const yearAssetDates = computed(() => {
  // 1) 全域：所有非 -12-31 日期、所有 -12-31 日期，升序排
  const allMonthlyAsc = [...new Set(
    store.assetSnapshots.filter(s => !s.date.endsWith('-12-31')).map(s => s.date)
  )].sort()
  const allYearEndAsc = [...new Set(
    store.assetSnapshots.filter(s => s.date.endsWith('-12-31')).map(s => s.date)
  )].sort()

  // 找 ≤ targetDate 的最大日期
  const lookupBefore = (sortedAsc, targetDate) => {
    let result = null
    for (const d of sortedAsc) {
      if (d <= targetDate) result = d
      else break
    }
    return result
  }

  // 2) 每年計算 cashDate / yearEndDate（含 fallback 旗標）
  //    年份來源：有交易的年份 + 有資產快照的年份（兩者聯集）
  const years = new Set([
    ...allYears.value,
    ...store.assetSnapshots.map(s => s.date.slice(0, 4)),
  ])
  const m = new Map()
  for (const y of years) {
    const monthlyOfYear = allMonthlyAsc.filter(d => d.startsWith(y))
    const ownMonthly    = monthlyOfYear.length ? monthlyOfYear.at(-1) : null
    const ownYearEnd    = allYearEndAsc.find(d => d === `${y}-12-31`) ?? null
    // cashDate fallback：用該年 12 月底為上限往前找
    const cashFallback    = ownMonthly ? null : lookupBefore(allMonthlyAsc, `${y}-12-31`)
    // yearEndDate fallback：用該年 12 月底為上限往前找
    const yearEndFallback = ownYearEnd ? null : lookupBefore(allYearEndAsc, `${y}-12-31`)
    m.set(y, {
      cashDate:        ownMonthly    ?? cashFallback,
      cashIsFallback:  !ownMonthly && !!cashFallback,
      yearEndDate:     ownYearEnd    ?? yearEndFallback,
      yearEndIsFallback: !ownYearEnd && !!yearEndFallback,
    })
  }
  return m
})

// 每年資產：Map<year, {cash, invest, realEstate, debt}>
const yearAssets = computed(() => {
  const m = new Map()
  // 初始化所有年份
  for (const y of yearAssetDates.value.keys()) {
    m.set(y, { cash: 0, invest: 0, realEstate: 0, debt: 0 })
  }
  for (const s of store.assetSnapshots) {
    const y = s.date.slice(0, 4)
    const dates = yearAssetDates.value.get(y)
    if (!dates) continue
    const cat = anoCategory.value.get(s.ano)
    const obj = m.get(y)
    if (cat === '資金' && s.date === dates.cashDate) {
      // 資金桶內依名稱細分：股票/基金/保單 → invest；其餘 → cash
      if (isStockAccount(anoName.value.get(s.ano))) obj.invest += s.amount
      else obj.cash += s.amount
    } else if ((cat === '動產/不動產' || cat === '負債') && s.date === dates.yearEndDate) {
      if (cat === '動產/不動產') obj.realEstate += s.amount
      else obj.debt += s.amount
    }
  }
  return m
})

// ============== Tab A 計算 ==============
function yearIncome(y) {
  if (!y || !incomeCno.value) return 0
  return yearCnoSpend.value.get(y)?.get(incomeCno.value) ?? 0
}
// 「支出」= 生活+固定+想要+投資損失（cno=22）
// 排除：收入、投資桶(save，現金搬移性質)
function yearExpense(y) {
  if (!y) return 0
  const m = yearCnoSpend.value.get(y)
  if (!m) return 0
  let total = 0
  for (const [cno, v] of m) {
    if (cno === incomeCno.value) continue
    if (store.classBuckets[cno] === 'save') continue
    total += v
  }
  return total
}
function yearInvest(y) {
  if (!y) return 0
  return yearInvestSpend.value.get(y) ?? 0
}

// 投資損益（家庭已實現股票/雜物損益）
// = cno=13/sno=64 投資利得（含股息、雜項收益）
// + cno=13/sno=66 資本利得（賣股獲利、二手物品價差）
// − cno=22 投資損失（賣股虧損）
const yearInvestPnL = computed(() => {
  if (!store.db) return new Map()
  const rows = rowsToObjects(store.db.exec(
    `SELECT strftime('%Y', date) AS year,
            SUM(CASE WHEN cno=13 AND sno IN (64,66) THEN spend
                     WHEN cno=22 THEN -spend
                     ELSE 0 END) AS pnl
     FROM money WHERE uno=1 AND (cno=22 OR (cno=13 AND sno IN (64,66)))
     GROUP BY year`
  ))
  const m = new Map()
  for (const r of rows) m.set(r.year, Number(r.pnl ?? 0))
  return m
})
function yearInvPnL(y) {
  return yearInvestPnL.value.get(y) ?? 0
}

function yearTotalAsset(y) {
  const a = yearAssets.value.get(y)
  if (!a) return 0
  return a.cash + a.invest + a.realEstate - a.debt
}

// 現金帳戶總額（直接對齊「資產頁面 → 歷年」現金小計：資金桶排除股票/基金/保單）
//   過去年 → 該年 -12-31；當年 → 最新月份快照（非年底）
//   該基準日無任何現金帳戶快照 → null（無法計算當年現金變動，顯示「—」）
const curYearStr = String(new Date().getFullYear())
function cashAccountTotal(yStr) {
  let date
  if (yStr === curYearStr) {
    date = store.assetSnapshots
      .filter(s => s.date.startsWith(yStr) && !s.date.endsWith('-12-31'))
      .map(s => s.date).sort().at(-1) ?? null
  } else {
    date = `${yStr}-12-31`
  }
  if (!date) return null
  let sum = 0, found = false
  for (const s of store.assetSnapshots) {
    if (s.date !== date) continue
    if (anoCategory.value.get(s.ano) !== '資金') continue
    if (isStockAccount(anoName.value.get(s.ano))) continue
    sum += s.amount; found = true
  }
  return found ? sum : null
}

// 當年 KPI（家庭 CFO 視角，純現金流，不含未實現損益）
// Row 1: 實際收入 / 實際支出 / 資金回收 / 資金轉移 / 實際現金變動（今年現金 − 去年現金，實際餘額差）
// Row 2: 淨收益   = 實際收入 − 實際支出          （對齊 實際收入+實際支出）
//        淨投資   = 資金轉移 − 資金回收           （對齊 資金轉移+資金回收，正 = 淨流出）
//        理論現金變動 = 淨收益 − 淨投資（理論現金變動，對齊 現金變動；與實際差額 = 未記錄缺漏）
const curYearData = computed(() => {
  const y = selectedYear.value
  if (!y) return null
  const idx = allYears.value.indexOf(y)
  const prev = idx > 0 ? allYears.value[idx - 1] : null
  const inc = yearIncome(y)
  const exp = yearExpense(y)
  const investOut = yearInvestOut(y)
  const investIn = yearInvestIn(y)
  const netGain = inc - exp
  const netInvest = investOut - investIn
  const netCash = netGain - netInvest              // 理論現金變動（理論現金變動）
  // 實際現金變動：今年現金 − 去年現金（現金帳戶總額，對齊資產頁面；過去年 -12-31、當年最新月份）
  const curCash  = cashAccountTotal(y)
  const prevCash = prev ? cashAccountTotal(prev) : null
  const realCashChg = (curCash != null && prevCash != null) ? (curCash - prevCash) : null
  const cashDiff = (realCashChg != null) ? (realCashChg - netCash) : null  // 實際 − 理論（缺漏）
  const prevInc = prev ? yearIncome(prev) : null
  const prevExp = prev ? yearExpense(prev) : null
  const prevInvestOut = prev ? yearInvestOut(prev) : null
  const prevInvestIn = prev ? yearInvestIn(prev) : null
  const prevNetGain = (prevInc != null && prevExp != null) ? (prevInc - prevExp) : null
  const prevNetInvest = (prevInvestOut != null && prevInvestIn != null) ? (prevInvestOut - prevInvestIn) : null
  const prevNetCash = (prevNetGain != null && prevNetInvest != null) ? (prevNetGain - prevNetInvest) : null
  const pct = (cur, p) => (p && p !== 0) ? ((cur - p) / Math.abs(p) * 100).toFixed(1) : null
  return {
    inc, exp, investIn, investOut, netGain, netInvest, netCash,
    curCash, prevCash, realCashChg, cashDiff,
    incChange:        pct(inc, prevInc),
    expChange:        pct(exp, prevExp),
    investInChange:   pct(investIn, prevInvestIn),
    investOutChange:  pct(investOut, prevInvestOut),
    netGainChange:    pct(netGain, prevNetGain),
    netInvestChange:  pct(netInvest, prevNetInvest),
    netCashChange:    pct(netCash, prevNetCash),
    savRate: inc ? (netGain / inc * 100).toFixed(1) : '0',
  }
})

// 當年支出結構：按 bucket 分組（含「未分類」fallback）
// 「實際支出」4 桶位中前 3 個用 classBuckets 對應，第 4 個 invloss 對應 cno=22
const FOUR_BUCKET_KEYS = new Set(['life', 'fixed', 'want'])
const curExpenseGroups = computed(() => {
  const y = selectedYear.value
  if (!y) return []
  const cnoSpend = yearCnoSpend.value.get(y) ?? new Map()
  const groups = EXPENSE_GROUPS.map(g => {
    let cats
    if (g.key === 'invloss') {
      // 投資損失：直接掛 cno=22 投資損失 class
      cats = store.classes
        .filter(c => c.cno === 22)
        .map(c => ({ cno: c.cno, name: c.name, amount: cnoSpend.get(c.cno) ?? 0 }))
    } else {
      // 其他 3 桶位依 classBuckets 對應（順序依 store.classes order_id）
      cats = store.classes
        .filter(c => store.classBuckets[c.cno] === g.key)
        .map(c => ({ cno: c.cno, name: c.name, amount: cnoSpend.get(c.cno) ?? 0 }))
    }
    const total = cats.reduce((s, c) => s + c.amount, 0)
    return { ...g, cats, total }
  })
  // 未分類：排除 income / 4 桶位 / cno=22（已在 invloss 桶）/ classBuckets='save'（投資 cno=14，不入支出明細）
  const unbucketed = store.classes
    .filter(c => {
      if (c.cno === 22) return false
      const b = store.classBuckets[c.cno]
      if (b === 'income' || b === 'save') return false
      return !FOUR_BUCKET_KEYS.has(b)
    })
    .map(c => ({ cno: c.cno, name: c.name, amount: cnoSpend.get(c.cno) ?? 0 }))
  if (unbucketed.length) {
    groups.push({
      key: 'unbucketed',
      name: '未分類',
      color: '#71717a',
      note: '請至預算頁設定桶位',
      cats: unbucketed,
      total: unbucketed.reduce((s, c) => s + c.amount, 0),
    })
  }
  return groups
})

const curExpenseTotal = computed(() =>
  curExpenseGroups.value.reduce((s, g) => s + g.total, 0)
)

const curExpenseMaxClassAmt = computed(() => {
  let max = 0
  for (const g of curExpenseGroups.value) {
    for (const c of g.cats) if (c.amount > max) max = c.amount
  }
  return max || 1
})

// 取某一年某 class 的子項目分解（依 subject 的 order_id 順序，含 0 元）
function classSubItems(y, cno) {
  const m = yearCnoSnoSpend.value.get(y) ?? new Map()
  const subjects = store.subjects.filter(s => s.cno === cno)
  const items = subjects.map(s => ({
    sno: s.sno,
    name: s.name,
    amount: m.get(`${cno}-${s.sno}`) ?? 0,
  }))
  const noSno = m.get(`${cno}-0`) ?? 0
  if (noSno > 0) items.push({ sno: 0, name: '（未分類）', amount: noSno })
  return items
}

// 當年收入結構：按 sno（subject）分組
const curIncomeItems = computed(() => {
  const y = selectedYear.value
  if (!y || !incomeCno.value) return []
  return classSubItems(y, incomeCno.value)
})

const curIncomeTotal = computed(() =>
  curIncomeItems.value.reduce((s, i) => s + i.amount, 0)
)

const curIncomeMaxAmt = computed(() =>
  curIncomeItems.value.reduce((m, i) => Math.max(m, i.amount), 1)
)

// 當年資產組成
const curAssetData = computed(() => {
  const y = selectedYear.value
  if (!y) return { cash: 0, invest: 0, realEstate: 0, debt: 0 }
  return yearAssets.value.get(y) ?? { cash: 0, invest: 0, realEstate: 0, debt: 0 }
})

// 當年資產的 fallback 狀態（給 UI 顯示「估」標籤用）
const curAssetMeta = computed(() => {
  const y = selectedYear.value
  const d = y ? yearAssetDates.value.get(y) : null
  return {
    cashDate:          d?.cashDate ?? null,
    cashIsFallback:    !!d?.cashIsFallback,
    yearEndDate:       d?.yearEndDate ?? null,
    yearEndIsFallback: !!d?.yearEndIsFallback,
  }
})

// 當年資產細項（混合日期：現金/投資用 cashDate；動產/負債用 yearEndDate）
const curAssetDetail = computed(() => {
  const y = selectedYear.value
  const result = { cash: [], invest: [], realEstate: [], debt: [] }
  if (!y) return result
  const dates = yearAssetDates.value.get(y)
  if (!dates) return result
  const cashByAno = new Map()    // cashDate 的快照
  const yearEndByAno = new Map() // yearEndDate 的快照
  for (const s of store.assetSnapshots) {
    if (s.date === dates.cashDate)    cashByAno.set(s.ano, s.amount)
    if (s.date === dates.yearEndDate) yearEndByAno.set(s.ano, s.amount)
  }
  for (const a of store.assetAccounts) {
    let v = 0
    if (a.category === '資金') v = cashByAno.get(a.ano) ?? 0
    else if (a.category === '動產/不動產' || a.category === '負債') v = yearEndByAno.get(a.ano) ?? 0
    // 含 0 元也顯示（依 store.assetAccounts 的順序）
    const item = { ano: a.ano, name: a.name, amount: v, note: a.note }
    if (a.category === '資金') {
      if (isStockAccount(a.name)) result.invest.push(item)
      else result.cash.push(item)
    }
    else if (a.category === '動產/不動產') result.realEstate.push(item)
    else if (a.category === '負債') result.debt.push(item)
  }
  // 順序依 store.assetAccounts 的 (category, order_id)，不重排
  return result
})

// 資產大類渲染用的合成 list（含 fallback 旗標）
const curAssetRows = computed(() => {
  const d = curAssetData.value
  const meta = curAssetMeta.value
  return [
    { ...ASSET_GROUPS[0], amount: d.cash,       items: curAssetDetail.value.cash,       isFallback: meta.cashIsFallback,    fbDate: meta.cashDate    },
    { ...ASSET_GROUPS[1], amount: d.invest,     items: curAssetDetail.value.invest,     isFallback: meta.cashIsFallback,    fbDate: meta.cashDate    },
    { ...ASSET_GROUPS[2], amount: d.realEstate, items: curAssetDetail.value.realEstate, isFallback: meta.yearEndIsFallback, fbDate: meta.yearEndDate },
    { ...ASSET_GROUPS[3], amount: d.debt,       items: curAssetDetail.value.debt,       isFallback: meta.yearEndIsFallback, fbDate: meta.yearEndDate },
  ]
})

const curAssetMaxAmt = computed(() => {
  const d = curAssetData.value
  return Math.max(d.cash, d.invest, d.realEstate, d.debt, 1)
})

// ============================================================
// Tab B - LV2-1 歷年收支結餘
// ============================================================
// 年度範圍（預設 2019–2025）
const histYearStart = ref('2019')
const histYearEnd   = ref('2025')

// 用於下拉選單的年份候選：聯集 allYears + 預設範圍，遞減排列
const histYearOptions = computed(() => {
  const set = new Set(allYears.value)
  for (let y = 2019; y <= 2030; y++) set.add(String(y))
  return [...set].sort().reverse()
})
// 起 ≤ 訖：Start 只能選 ≤ End；End 只能選 ≥ Start
const histYearStartOptions = computed(() =>
  histYearOptions.value.filter(y => +y <= +histYearEnd.value)
)
const histYearEndOptions = computed(() =>
  histYearOptions.value.filter(y => +y >= +histYearStart.value)
)
// 若使用者切換造成不一致，自動 clamp（保險）
watch(histYearStart, (v) => {
  if (+v > +histYearEnd.value) histYearEnd.value = v
})
watch(histYearEnd, (v) => {
  if (+v < +histYearStart.value) histYearStart.value = v
})

// 篩選後的年份（升序）；包含起訖區間內全部年份（即使無交易也保留為 0）
const histYears = computed(() => {
  const s = histYearStart.value, e = histYearEnd.value
  if (!s || !e) return allYears.value
  const lo = Math.min(+s, +e), hi = Math.max(+s, +e)
  const out = []
  for (let y = lo; y <= hi; y++) out.push(String(y))
  return out
})

// 每年 { inc, exp, sur, rate }
// exp = 支出（生活+固定+想要+投資損失）
// sur = 收入 − 支出
const histYearData = computed(() => {
  return histYears.value.map(y => {
    const inc = yearIncome(y)
    const exp = yearExpense(y)
    const sur = inc - exp
    return { y, inc, exp, sur, rate: inc ? +(sur / inc * 100).toFixed(1) : 0 }
  })
})

// 收入結構：依 income class 的每個 subject（sno）一條資料集
// 排序依 store.subjects order_id（不重排），含 sno=0「未分類」
const histIncomeDatasets = computed(() => {
  const cno = incomeCno.value
  if (!cno) return []
  const subjects = store.subjects.filter(s => s.cno === cno)
  // 收入子項固定色盤（循環）
  const palette = ['#10b981','#3b82f6','#f59e0b','#8b5cf6','#ef4444','#06b6d4','#ec4899','#84cc16','#6366f1','#f97316']
  const sets = subjects.map((s, i) => ({
    label: s.name,
    data: histYears.value.map(y => yearCnoSnoSpend.value.get(y)?.get(`${cno}-${s.sno}`) ?? 0),
    backgroundColor: palette[i % palette.length],
    borderWidth: 0,
  }))
  // 未分類：sno=0 不在 subjects 內
  const noSnoData = histYears.value.map(y => yearCnoSnoSpend.value.get(y)?.get(`${cno}-0`) ?? 0)
  if (noSnoData.some(v => v > 0)) {
    sets.push({ label: '（未分類）', data: noSnoData, backgroundColor: '#9ca3af', borderWidth: 0 })
  }
  return sets
})

// 歷年「現金存款增加」+「股票買進」（投資變化圖用）
// 現金資產年底總額：使用 asset_snapshot category='資金' 但 name 非股票 的 -12-31 快照
const yearEndCashByYear = computed(() => {
  const m = new Map()  // 'YYYY' → 現金資產年底總額
  for (const s of store.assetSnapshots) {
    if (!s.date.endsWith('-12-31')) continue
    const cat = anoCategory.value.get(s.ano)
    if (cat !== '資金') continue
    if (isStockAccount(anoName.value.get(s.ano))) continue
    const y = s.date.slice(0, 4)
    m.set(y, (m.get(y) ?? 0) + (s.amount ?? 0))
  }
  return m
})

const histCashGrowth = computed(() =>
  histYears.value.map(y => {
    const cur  = yearEndCashByYear.value.get(y)
    const prev = yearEndCashByYear.value.get(String(+y - 1))
    if (cur == null || prev == null) return 0
    return cur - prev
  })
)

// 股票（category='資金' 且 name 含股票/基金/保單）年底總額 + 年度增減（比對表「資金變動」用）
const yearEndStockByYear = computed(() => {
  const m = new Map()
  for (const s of store.assetSnapshots) {
    if (!s.date.endsWith('-12-31')) continue
    const cat = anoCategory.value.get(s.ano)
    if (cat !== '資金') continue
    if (!isStockAccount(anoName.value.get(s.ano))) continue
    const y = s.date.slice(0, 4)
    m.set(y, (m.get(y) ?? 0) + (s.amount ?? 0))
  }
  return m
})
const histStockGrowth = computed(() =>
  histYears.value.map(y => {
    const cur  = yearEndStockByYear.value.get(y)
    const prev = yearEndStockByYear.value.get(String(+y - 1))
    if (cur == null || prev == null) return 0
    return cur - prev
  })
)

const histStockBuy = computed(() =>
  histYears.value.map(y => yearInvestSpend.value.get(y) ?? 0)
)

// ── canvas refs + chart instances ──
const trendCanvas    = ref(null)
const savingsCanvas  = ref(null)
const incStructCanvas = ref(null)
let trendChart    = null
let savingsChart  = null
let incStructChart = null

const fmtTw = (v) => (v / 10000).toFixed(0) + '萬'
const fmtTw1 = (v) => (v / 10000).toFixed(1) + '萬'

function drawTrend() {
  if (trendChart) { trendChart.destroy(); trendChart = null }
  if (!trendCanvas.value) return
  const labels = histYears.value
  const d = histYearData.value
  trendChart = new Chart(trendCanvas.value, {
    type: 'bar',
    data: {
      labels,
      datasets: [
        { label: '淨收益', data: d.map(x => x.sur), type: 'line',
          borderColor: '#f59e0b', backgroundColor: '#f59e0b', tension: 0.3, fill: false,
          pointRadius: 4, borderWidth: 2.5, order: 0 },
        { label: '實際收入', data: d.map(x => x.inc), backgroundColor: '#10b981', borderRadius: 4, order: 2 },
        { label: '實際支出', data: d.map(x => x.exp), backgroundColor: '#ef4444', borderRadius: 4, order: 2 },
      ],
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      scales: { y: { ticks: { callback: v => fmtTw(v) } } },
      plugins: {
        legend: { labels: { boxWidth: 12, font: { size: 11 } } },
        tooltip: { callbacks: { label: c => `${c.dataset.label}: ${fmtTw1(c.raw)}` } },
      },
    },
  })
}

function drawSavings() {
  // 歷年淨投資圖：投資支出(買進) / 投資收入(賣出) / 淨投資(折線)
  if (savingsChart) { savingsChart.destroy(); savingsChart = null }
  if (!savingsCanvas.value) return
  const ys = histYears.value
  const spend = ys.map(y => yearInvestOut(y))
  const income = ys.map(y => yearInvestIn(y))
  const net    = ys.map(y => yearInvestOut(y) - yearInvestIn(y))
  savingsChart = new Chart(savingsCanvas.value, {
    type: 'bar',
    data: {
      labels: ys,
      datasets: [
        { label: '資金轉移', data: spend,  backgroundColor: '#ef4444', borderRadius: 3, order: 2 },
        { label: '資金回收', data: income, backgroundColor: '#10b981', borderRadius: 3, order: 2 },
        { label: '淨投資',  data: net, type: 'line',
          borderColor: '#8b5cf6', backgroundColor: '#8b5cf6',
          tension: 0.3, fill: false, pointRadius: 4, borderWidth: 2.5, order: 0 },
      ],
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      scales: { y: { ticks: { callback: v => fmtTw(v) } } },
      plugins: {
        legend: { labels: { boxWidth: 12, font: { size: 11 } } },
        tooltip: {
          callbacks: { label: c => `${c.dataset.label}: ${fmtTw1(c.raw)}` },
        },
      },
    },
  })
}

function drawIncStruct() {
  if (incStructChart) { incStructChart.destroy(); incStructChart = null }
  if (!incStructCanvas.value) return
  incStructChart = new Chart(incStructCanvas.value, {
    type: 'bar',
    data: { labels: histYears.value, datasets: histIncomeDatasets.value },
    options: {
      responsive: true, maintainAspectRatio: false,
      scales: {
        x: { stacked: true },
        y: { stacked: true, ticks: { callback: v => fmtTw(v) } },
      },
      plugins: {
        legend: { labels: { boxWidth: 12, font: { size: 11 } } },
        tooltip: {
          callbacks: {
            label: c => `${c.dataset.label}: ${fmtTw1(c.raw)}`,
            footer: items => '合計: ' + fmtTw1(items.reduce((s, i) => s + i.raw, 0)),
          },
        },
      },
    },
  })
}

// ============================================================
// Tab B - LV2-3 年度數據比對表
// ============================================================
const CURRENT_YEAR_STR = String(new Date().getFullYear())

// 支出依桶位拆解：每年 × 每桶位
function bucketExpenseAt(yearIdx, bucketKey) {
  const y = histYears.value[yearIdx]
  const m = yearCnoSpend.value.get(y)
  if (!m) return 0
  let total = 0
  for (const [cno, v] of m) {
    if (store.classBuckets[cno] === bucketKey) total += v
  }
  return total
}

// 收入分組規則（依 subject 名稱）
const INCOME_SALARY_NAMES = new Set(['怡亭薪水', '政德薪水', '怡亭薪資', '政德薪資'])
const INCOME_INVEST_NAMES = new Set(['投資利得', '利息', '資本利得'])
function incomeAt(yearIdx, group) {
  const y = histYears.value[yearIdx]
  const cno = incomeCno.value
  if (!cno || !y) return 0
  const m = yearCnoSnoSpend.value.get(y)
  if (!m) return 0
  let total = 0
  for (const s of store.subjects) {
    if (s.cno !== cno) continue
    const amt = m.get(`${cno}-${s.sno}`) ?? 0
    if (group === 'salary' && INCOME_SALARY_NAMES.has(s.name)) total += amt
    else if (group === 'invest' && INCOME_INVEST_NAMES.has(s.name)) total += amt
    else if (group === 'other' && !INCOME_SALARY_NAMES.has(s.name) && !INCOME_INVEST_NAMES.has(s.name)) total += amt
  }
  // 未分類（sno=0）歸入「其他」
  if (group === 'other') total += m.get(`${cno}-0`) ?? 0
  return total
}

// 指標列定義：{ label, color, bold?, indent?, fn(yearIdx) }
// 公式對齊上方圖表：支出 = 一般支出（不含投資），結餘 = 收入 − 一般支出，投資獨立放最下
const overviewRows = computed(() => {
  const yd = histYearData.value
  const lossAt = i => yearInvestLoss.value.get(histYears.value[i]) ?? 0
  return [
    { label: '實際收入', color: '#10b981', bold: true, fn: i => fmtTw1(yd[i].inc) },
    { label: '　薪資',     color: '#10b981', indent: true, fn: i => fmtTw1(incomeAt(i, 'salary')) },
    { label: '　投資獲利', color: '#10b981', indent: true, fn: i => fmtTw1(incomeAt(i, 'invest')) },
    { label: '　其他',     color: '#10b981', indent: true, fn: i => fmtTw1(incomeAt(i, 'other')) },
    { label: '實際支出', color: '#ef4444', bold: true, fn: i => fmtTw1(yd[i].exp) },
    { label: '　生活類',     color: '#10b981', indent: true, fn: i => fmtTw1(bucketExpenseAt(i, 'life')) },
    { label: '　固定類',     color: '#3b82f6', indent: true, fn: i => fmtTw1(bucketExpenseAt(i, 'fixed')) },
    { label: '　想要',       color: '#f59e0b', indent: true, fn: i => fmtTw1(bucketExpenseAt(i, 'want')) },
    { label: '　投資損失',   color: '#8b5cf6', indent: true, fn: i => fmtTw1(lossAt(i)) },
    { label: '淨收益',   color: '#f59e0b', bold: true, fn: i => fmtTw1(yd[i].sur) },
    { label: '淨投資',   color: '#8b5cf6', bold: true, fn: i => fmtTw1(yearInvest(histYears.value[i])) },
    { label: '　資金轉移', color: '#ef4444', indent: true, fn: i => fmtTw1(yearInvestOut(histYears.value[i])) },
    { label: '　資金回收', color: '#10b981', indent: true, fn: i => fmtTw1(yearInvestIn(histYears.value[i])) },
    { label: '理論現金變動', formula: '淨收益 − 淨投資', color: '#0891b2', bold: true, fn: i => fmtTw1(yd[i].sur - yearInvest(histYears.value[i])) },
    { label: '實際資金變動', color: '#06b6d4', bold: true, fn: i => fmtTw1(histCashGrowth.value[i] + histStockGrowth.value[i]) },
    { label: '　實際現金變動', color: '#06b6d4', indent: true, fn: i => fmtTw1(histCashGrowth.value[i]) },
    { label: '　實際股票變動', color: '#8b5cf6', indent: true, fn: i => fmtTw1(histStockGrowth.value[i]) },
  ]
})

function drawHistCharts() {
  drawTrend()
  drawSavings()
  drawIncStruct()
}

// activeTab / 資料變動時重繪
watch(
  [activeTab, histYears, histYearData, histIncomeDatasets, histCashGrowth, histStockBuy],
  () => {
    if (activeTab.value !== 'historical') return
    nextTick(drawHistCharts)
  },
  { deep: true, immediate: true },
)

// canvas 第一次掛上 DOM 時補繪一次（v-else 切換時 ref 是異步綁定）
watch(
  [trendCanvas, savingsCanvas, incStructCanvas],
  () => {
    if (activeTab.value === 'historical') nextTick(drawHistCharts)
  }
)

onBeforeUnmount(() => {
  trendChart?.destroy()
  savingsChart?.destroy()
  incStructChart?.destroy()
  monthChart?.destroy()
  investMonthChart?.destroy()
  fundMonthChart?.destroy()
  classTrendChart?.destroy()
  budgetChart?.destroy()
  investBudgetChart?.destroy()
  bucketDetailChart?.destroy()
  investDetailChart?.destroy()
})

// ============================================================
// #1 預算 vs 實際對照（Tab A）
// ============================================================
onMounted(() => { if (store.db) store.loadAllBudgets() })
watch(() => store.db, (v) => { if (v) store.loadAllBudgets() })

// 當年各桶位的「已設預算」總和（依 classBuckets 分桶）
// 規則同 BudgetPage.histClassBudget：每 class 優先用 sno=0 (class 總額)，
// 若無 sno=0 行才加總 sno>0 細項，避免重複計算
const curBudgetByBucket = computed(() => {
  const y = Number(selectedYear.value)
  if (!y) return { life: 0, fixed: 0, want: 0, invloss: 0 }
  // 先依 cno 分組當年的所有 items
  const byCno = new Map()
  for (const it of store.allBudgetItems) {
    if (it.year !== y) continue
    if (!byCno.has(it.cno)) byCno.set(it.cno, [])
    byCno.get(it.cno).push(it)
  }
  const out = { life: 0, fixed: 0, want: 0, invloss: 0 }
  for (const [cno, items] of byCno) {
    // cno=22 走 invloss 桶；其他依 classBuckets
    const bkt = cno === 22 ? 'invloss' : store.classBuckets[cno]
    if (!bkt || !(bkt in out)) continue
    const direct = items.find(i => i.sno === 0)?.amount
    const amt = direct != null ? Number(direct)
      : items.filter(i => i.sno !== 0).reduce((a, i) => a + Number(i.amount ?? 0), 0)
    out[bkt] += amt
  }
  return out
})

// 桶位對照列：實際 / 預算 / 達成率 / 差額
const curBucketCompare = computed(() => {
  return EXPENSE_GROUPS.map(g => {
    const actual = curExpenseGroups.value.find(x => x.key === g.key)?.total ?? 0
    const budget = curBudgetByBucket.value[g.key] ?? 0
    const pct    = budget ? +(actual / budget * 100).toFixed(1) : null
    const diff   = budget - actual
    return { ...g, actual, budget, pct, diff }
  })
})

// 「實際支出明細」表格：是否顯示預算 + 視覺化模式
const showBudgetInExpense = ref(true)
const expenseVisMode     = ref('amount')   // 'amount' | 'percent'
const investVisMode      = ref('amount')   // 'amount' | 'percent'
const showBudgetInInvest = ref(false)

// 「實際收入明細」表格：是否顯示預算
const showBudgetInIncome = ref(true)

// 收入子項預算（sno → amount），收入無 class 級總額，採子項加總
const curIncomeSubBudget = computed(() => {
  const y = Number(selectedYear.value)
  const m = new Map()
  if (!y || !incomeCno.value) return m
  for (const it of store.allBudgetItems) {
    if (it.year !== y) continue
    if (it.cno !== incomeCno.value) continue
    if (it.sno === 0) continue   // class 級總額略過
    m.set(it.sno, Number(it.amount ?? 0))
  }
  return m
})

// 收入視覺化欄共用 max
const curIncomeMaxWithBudget = computed(() => {
  let mx = 0
  for (const it of curIncomeItems.value) {
    if (it.amount > mx) mx = it.amount
    const b = curIncomeSubBudget.value.get(it.sno) ?? 0
    if (b > mx) mx = b
  }
  return mx || 1
})

const curIncomeBudgetTotal = computed(() => {
  let s = 0
  for (const v of curIncomeSubBudget.value.values()) s += v
  return s
})

// ============================================================
// 投資支出明細（右欄）— 對齊 KPI 投資支出 = mode='信用卡支出'（全掛 cno=14）
//   分類 = cno=14 子項（股票/基金/房貸本金/借款/動產購置）
//   ※ 不可用 yearCnoSnoSpend：那會混入賣股回流(信用卡收入)、現金買基金
//   預算多半只有股票(sno=101)；其餘顯示「無預算」
// ============================================================
const INVEST_CNO = 14
const INVEST_SUB_COLOR = { 101: '#8b5cf6', 151: '#06b6d4', 280: '#f59e0b', 281: '#ef4444', 282: '#84cc16' }

// 每年每個 sno 的投資支出（只算信用卡支出）
const yearInvestOutBySno = computed(() => {
  if (!store.db) return new Map()
  const rows = rowsToObjects(store.db.exec(
    `SELECT strftime('%Y', date) AS year, sno, SUM(spend) AS total
     FROM money WHERE uno=1 AND mode='信用卡支出'
     GROUP BY year, sno`
  ))
  const m = new Map()
  for (const r of rows) {
    if (!m.has(r.year)) m.set(r.year, new Map())
    m.get(r.year).set(r.sno, Number(r.total ?? 0))
  }
  return m
})

// 投資子項預算（sno → amount；略過 sno=0 class 級總額）
const curInvestSubBudget = computed(() => {
  const y = Number(selectedYear.value)
  const m = new Map()
  if (!y) return m
  for (const it of store.allBudgetItems) {
    if (it.year !== y || it.cno !== INVEST_CNO || it.sno === 0) continue
    m.set(it.sno, Number(it.amount ?? 0))
  }
  return m
})

// 當年投資支出子項（含 0，依 subject 順序）
const curInvestItems = computed(() => {
  const y = selectedYear.value
  if (!y) return []
  const m = yearInvestOutBySno.value.get(y) ?? new Map()
  return store.subjects
    .filter(s => s.cno === INVEST_CNO)
    .map(s => ({
      sno: s.sno,
      name: s.name,
      color: INVEST_SUB_COLOR[s.sno] ?? '#71717a',
      amount: m.get(s.sno) ?? 0,
      budget: curInvestSubBudget.value.get(s.sno) ?? 0,
    }))
})
const curInvestTotal = computed(() => curInvestItems.value.reduce((s, i) => s + i.amount, 0))
const curInvestBudgetTotal = computed(() => curInvestItems.value.reduce((s, i) => s + i.budget, 0))
const curInvestMaxWithBudget = computed(() => {
  let mx = 0
  for (const it of curInvestItems.value) {
    if (it.amount > mx) mx = it.amount
    if (it.budget > mx) mx = it.budget
  }
  return mx || 1
})
// 投資支出圖表 + 達成率小條用（預算 vs 實際 / 達成率）
const curInvestCompare = computed(() =>
  curInvestItems.value.map(it => ({
    sno: it.sno, name: it.name, color: it.color,
    actual: it.amount, budget: it.budget,
    pct: it.budget ? +(it.amount / it.budget * 100).toFixed(1) : null,
    diff: it.budget - it.amount,
  }))
)

// 股票（sno=101）當年個別買進交易（展開用；note 原文，不解析個股名）
function investStockTxns(y) {
  if (!store.db || !y) return []
  const rows = rowsToObjects(store.db.exec(
    `SELECT date, note, spend FROM money
     WHERE uno=1 AND mode='信用卡支出' AND cno=${INVEST_CNO} AND sno=101
       AND strftime('%Y', date)='${y}'
     ORDER BY date`
  ))
  return rows.map(r => ({ date: r.date, note: r.note ?? '', amount: Number(r.spend ?? 0) }))
}

// 視覺化柱寬計算（回傳 0~100，單位 %，相對視覺化欄寬度）
// 金額模式：全表統一 scale（= 所有列 max(實際, 預算)），柱長 ∝ 實際金額（可橫向比較絕對值）
// 百分比模式：每列以該列預算為 100% 基準，scale 0~120%；預算柱永遠 83.3%、實際柱 = pct/120
function expBarWidth(cat, kind) {
  const budget = curClassBudget.value.get(cat.cno) ?? 0
  const actual = cat.amount ?? 0
  if (expenseVisMode.value === 'percent') {
    if (budget <= 0) return kind === 'actual' ? 100 : 0   // 無預算就讓實際撐滿
    const pct = actual / budget * 100
    const visVal = kind === 'budget' ? 100 : Math.min(pct, 120)
    return visVal / 120 * 100
  }
  // amount mode：全表共用 max，預算 toggle 開啟時納入預算比較
  const max = showBudgetInExpense.value ? curExpenseMaxWithBudget.value : curExpenseMaxClassAmt.value
  const num = kind === 'budget' ? budget : actual
  return num / max * 100
}

function invBarWidth(it, kind) {
  const budget = it.budget ?? 0
  const actual = it.amount ?? 0
  if (investVisMode.value === 'percent') {
    if (budget <= 0) return kind === 'actual' ? 100 : 0
    const pct = actual / budget * 100
    return (kind === 'budget' ? 100 : Math.min(pct, 120)) / 120 * 100
  }
  const max = curInvestMaxWithBudget.value || 1
  return (kind === 'budget' ? budget : actual) / max * 100
}

// 各 class 的已設預算（採 BudgetPage 規則：sno=0 優先，否則加總 sno>0）
const curClassBudget = computed(() => {
  const y = Number(selectedYear.value)
  const m = new Map()  // cno → budget
  if (!y) return m
  const byCno = new Map()
  for (const it of store.allBudgetItems) {
    if (it.year !== y) continue
    if (!byCno.has(it.cno)) byCno.set(it.cno, [])
    byCno.get(it.cno).push(it)
  }
  for (const [cno, items] of byCno) {
    const direct = items.find(i => i.sno === 0)?.amount
    const amt = direct != null ? Number(direct)
      : items.filter(i => i.sno !== 0).reduce((a, i) => a + Number(i.amount ?? 0), 0)
    m.set(cno, amt)
  }
  return m
})

// 當年「實際支出明細」表所有 class 的預算總額（與明細同範圍：排除 save/cno=22）
const curBudgetTotal = computed(() => {
  let s = 0
  for (const g of curExpenseGroups.value) {
    for (const c of g.cats) s += curClassBudget.value.get(c.cno) ?? 0
  }
  return s
})

// 視覺化欄共用 max：取 max(實際, 預算) 一起 normalize（顯示預算時才同尺）
const curExpenseMaxWithBudget = computed(() => {
  let mx = 0
  for (const g of curExpenseGroups.value) {
    for (const c of g.cats) {
      if (c.amount > mx) mx = c.amount
      const b = curClassBudget.value.get(c.cno) ?? 0
      if (b > mx) mx = b
    }
  }
  return mx || 1
})

// 桶位細部：選中桶位內每個 class 的「已設預算 vs 實際」
const bucketTab = ref('life')   // 'life' | 'fixed' | 'want' | 'invloss'
// 細部用調色盤（每 class 一色，圖表與下方文字卡共用）
const CLASS_PALETTE_INNER = [
  '#10b981', '#3b82f6', '#f59e0b', '#8b5cf6', '#ef4444', '#06b6d4',
  '#ec4899', '#84cc16', '#6366f1', '#f97316', '#14b8a6', '#a855f7',
]
const curBucketDetail = computed(() => {
  const y = Number(selectedYear.value)
  if (!y) return []
  const bkt = bucketTab.value
  const grp = EXPENSE_GROUPS.find(g => g.key === bkt)
  if (!grp) return []
  // 該桶位下的 classes
  const classes = store.classes.filter(c => store.classBuckets[c.cno] === bkt)
  // 依 cno 取得當年 budget_item
  const items = store.allBudgetItems.filter(it => it.year === y)
  const byCno = new Map()
  for (const it of items) {
    if (!byCno.has(it.cno)) byCno.set(it.cno, [])
    byCno.get(it.cno).push(it)
  }
  const cnoSpend = yearCnoSpend.value.get(String(y)) ?? new Map()
  return classes.map((c, i) => {
    const items = byCno.get(c.cno) ?? []
    const direct = items.find(i => i.sno === 0)?.amount
    const budget = direct != null ? Number(direct)
      : items.filter(i => i.sno !== 0).reduce((a, i) => a + Number(i.amount ?? 0), 0)
    const actual = cnoSpend.get(c.cno) ?? 0
    const pct  = budget ? +(actual / budget * 100).toFixed(1) : null
    const diff = budget - actual
    return {
      cno: c.cno, name: c.name,
      color: CLASS_PALETTE_INNER[i % CLASS_PALETTE_INNER.length],
      budget, actual, pct, diff,
    }
  })
})

// ============================================================
// #4 Top 10 子項排行（Tab A）
// ============================================================
// 建立 cno → {name, bucket, color} 對照
const classMeta = computed(() => {
  const m = new Map()
  const bucketColor = Object.fromEntries(EXPENSE_GROUPS.map(g => [g.key, g.color]))
  for (const c of store.classes) {
    const b = store.classBuckets[c.cno]
    m.set(c.cno, { name: c.name, bucket: b, color: bucketColor[b] ?? '#71717a' })
  }
  return m
})
const subjectName = computed(() => {
  const m = new Map()
  for (const s of store.subjects) m.set(`${s.cno}-${s.sno}`, s.name)
  return m
})

const curTopItems = computed(() => {
  const y = selectedYear.value
  if (!y) return []
  const m = yearCnoSnoSpend.value.get(y)
  if (!m) return []
  const list = []
  for (const [k, amt] of m) {
    const [cno, sno] = k.split('-').map(Number)
    if (cno === incomeCno.value) continue           // 排除收入
    const cls = classMeta.value.get(cno)
    if (!cls || cls.bucket === 'income') continue   // 雙保險
    if (cls.bucket === 'save') continue             // 排除投資（cno=14 信用卡支出/早期現金支出）
    const sName = subjectName.value.get(k) ?? (sno === 0 ? '（未分類）' : `#${sno}`)
    list.push({
      key: k, cno, sno, amount: amt,
      className: cls.name, subjectName: sName, color: cls.color,
    })
  }
  return list.sort((a, b) => b.amount - a.amount).slice(0, 10)
})
const curTopMax = computed(() =>
  curTopItems.value.reduce((m, i) => Math.max(m, i.amount), 1)
)

// ============================================================
// #2 月別趨勢（Tab A）— 當年 12 個月 inc/exp/sur
// ============================================================
const yearMonthCnoSpend = computed(() => {
  if (!store.db) return new Map()
  const rows = rowsToObjects(store.db.exec(
    `SELECT strftime('%Y', date) AS year, CAST(strftime('%m', date) AS INT) AS mo, cno, SUM(spend) AS total
     FROM money WHERE uno=1
     GROUP BY year, mo, cno`
  ))
  // Map<year, Map<mo, Map<cno, total>>>
  const m = new Map()
  for (const r of rows) {
    if (!m.has(r.year)) m.set(r.year, new Map())
    const ym = m.get(r.year)
    if (!ym.has(r.mo)) ym.set(r.mo, new Map())
    ym.get(r.mo).set(r.cno, Number(r.total ?? 0))
  }
  return m
})

// 每年 / 每月 「投資損失」(cno=22)
const yearInvestLoss = computed(() => {
  if (!store.db) return new Map()
  const rows = rowsToObjects(store.db.exec(
    `SELECT strftime('%Y', date) AS year, SUM(spend) AS total
     FROM money WHERE uno=1 AND cno=22
     GROUP BY year`
  ))
  const m = new Map()
  for (const r of rows) m.set(r.year, Number(r.total ?? 0))
  return m
})
const yearMonthInvestLoss = computed(() => {
  if (!store.db) return new Map()
  const rows = rowsToObjects(store.db.exec(
    `SELECT strftime('%Y', date) AS year, CAST(strftime('%m', date) AS INT) AS mo, SUM(spend) AS total
     FROM money WHERE uno=1 AND cno=22
     GROUP BY year, mo`
  ))
  const m = new Map()
  for (const r of rows) {
    if (!m.has(r.year)) m.set(r.year, new Map())
    m.get(r.year).set(r.mo, Number(r.total ?? 0))
  }
  return m
})

// 月別投資淨額 = 信用卡支出（買進）− 信用卡收入（賣出本金回流）
const yearMonthInvest = computed(() => {
  if (!store.db) return new Map()
  const rows = rowsToObjects(store.db.exec(
    `SELECT strftime('%Y', date) AS year, CAST(strftime('%m', date) AS INT) AS mo,
            SUM(CASE WHEN mode='信用卡支出' THEN spend
                     WHEN mode='信用卡收入' THEN -spend
                     ELSE 0 END) AS total
     FROM money WHERE uno=1 AND mode IN ('信用卡支出','信用卡收入')
     GROUP BY year, mo`
  ))
  const m = new Map()
  for (const r of rows) {
    if (!m.has(r.year)) m.set(r.year, new Map())
    m.get(r.year).set(r.mo, Number(r.total ?? 0))
  }
  return m
})

// 月別「實際投資買入/賣出」(來自 money 表的現金流，非 snapshot)
// 實際買入 = mode='信用卡支出'；實際賣出 = mode='信用卡收入'
const yearMonthInvestFlow = computed(() => {
  if (!store.db) return new Map()
  const rows = rowsToObjects(store.db.exec(
    `SELECT strftime('%Y', date) AS year, CAST(strftime('%m', date) AS INT) AS mo, mode, SUM(spend) AS total
     FROM money WHERE uno=1 AND mode IN ('信用卡支出','信用卡收入')
     GROUP BY year, mo, mode`
  ))
  const m = new Map()
  for (const r of rows) {
    if (!m.has(r.year)) m.set(r.year, new Map())
    const ym = m.get(r.year)
    if (!ym.has(r.mo)) ym.set(r.mo, { buy: 0, sell: 0 })
    const v = Number(r.total ?? 0)
    if (r.mode === '信用卡支出') ym.get(r.mo).buy = v
    else ym.get(r.mo).sell = v
  }
  return m
})

// 當年度月別「資金變動」：每月現金 / 股票 相對「上一個有 snapshot 的月份」增減
// 起點 = 上年 12-31；缺月不算（delta=0），有 snapshot 那月補計累積差
// 怡亭-凱基股票 名稱判斷（定期定額追蹤）
const KAIJI_NAME_RE = /怡亭.*凱基/

const curMonthlyFund = computed(() => {
  const y = selectedYear.value
  const dCash = Array(12).fill(0)
  const dStock = Array(12).fill(0)
  const dKaiji = Array(12).fill(0)
  const hasData = Array(12).fill(false)
  const invBuy = Array(12).fill(0)
  const invSell = Array(12).fill(0)
  if (!y) return { dCash, dStock, dKaiji, hasData, invBuy, invSell }
  // 月別買賣（一定有資料就填，與 snapshot 無關）
  const flow = yearMonthInvestFlow.value.get(y) ?? new Map()
  for (const [mo, v] of flow) {
    invBuy[mo - 1]  = v.buy
    invSell[mo - 1] = v.sell
  }
  const prevYear = String(+y - 1)
  let prevCash  = yearEndCashByYear.value.get(prevYear)  ?? null
  let prevStock = yearEndStockByYear.value.get(prevYear) ?? null
  // 起點：上年 12-31 凱基股票金額（找特定 ano）
  let prevKaiji = null
  for (const s of store.assetSnapshots) {
    if (s.date !== `${prevYear}-12-31`) continue
    if (!KAIJI_NAME_RE.test(anoName.value.get(s.ano) ?? '')) continue
    prevKaiji = (prevKaiji ?? 0) + s.amount
  }
  // 將該年所有 snapshot 依月份分組（取每月最晚日期）
  const monthLatestDate = new Map()  // mo(1-12) → 'YYYY-MM-DD'
  for (const s of store.assetSnapshots) {
    if (s.date.slice(0, 4) !== String(y)) continue
    if (s.date.endsWith('-12-31') && +y === new Date().getFullYear()) continue // 當年若有人為 12-31 估值跳過
    const mo = Number(s.date.slice(5, 7))
    const cur = monthLatestDate.get(mo)
    if (!cur || s.date > cur) monthLatestDate.set(mo, s.date)
  }
  for (let m = 1; m <= 12; m++) {
    const d = monthLatestDate.get(m)
    if (!d) continue
    let cash = 0, stock = 0, kaiji = 0
    let stockFound = false, kaijiFound = false
    for (const s of store.assetSnapshots) {
      if (s.date !== d) continue
      const cat = anoCategory.value.get(s.ano)
      if (cat !== '資金') continue
      const nm = anoName.value.get(s.ano)
      if (isStockAccount(nm)) { stock += s.amount; stockFound = true }
      else cash += s.amount
      if (KAIJI_NAME_RE.test(nm ?? '')) { kaiji += s.amount; kaijiFound = true }
    }
    if (prevCash != null)               dCash[m - 1]  = cash  - prevCash
    if (prevStock != null && stockFound) dStock[m - 1] = stock - prevStock
    if (prevKaiji != null && kaijiFound) dKaiji[m - 1] = kaiji - prevKaiji
    hasData[m - 1] = true
    prevCash  = cash
    if (stockFound) prevStock = stock
    if (kaijiFound) prevKaiji = kaiji
  }
  return { dCash, dStock, dKaiji, hasData, invBuy, invSell }
})

// Δ現金 累積：逐月把現金月增減累加；首個快照前為 null（折線不畫）
const curCumCash = computed(() => {
  const f = curMonthlyFund.value
  let acc = 0
  let started = false
  return f.dCash.map((v, i) => {
    if (f.hasData[i]) started = true
    acc += v
    return { v: acc, started }
  })
})

const curMonthlySeries = computed(() => {
  const y = selectedYear.value
  const ym = yearMonthCnoSpend.value.get(y)
  const yl = yearMonthInvestLoss.value.get(y) ?? new Map()
  const kaiji = curMonthlyFund.value.dKaiji   // 怡亭凱基 月度增減（同 monthFund）
  const inc = Array(12).fill(0)
  const exp = Array(12).fill(0)
  const invloss = Array(12).fill(0)
  if (ym) {
    for (const [mo, byCno] of ym) {
      let i = 0, e = 0
      for (const [cno, v] of byCno) {
        if (cno === incomeCno.value) i += v
        // 支出 = 排除投資桶(save，現金搬移)；cno=22 投資損失 計入支出
        else if (store.classBuckets[cno] !== 'save') e += v
      }
      inc[mo - 1] = i
      exp[mo - 1] = e
    }
  }
  for (const [mo, v] of yl) invloss[mo - 1] = v
  // 淨收益 = 實際收入 − 實際支出（依 CLAUDE.md 定義，不含怡亭凱基股票月增）
  const sur = inc.map((v, idx) => v - exp[idx])
  return { inc, exp, invloss, kaiji, sur }
})

// 淨收益累積：逐月把月度淨收益累加
const curCumSur = computed(() => {
  let acc = 0
  return curMonthlySeries.value.sur.map(v => (acc += v))
})

// 理論現金變動累積：逐月 (淨收益 − 淨投資) 累加（折線用）
const curCumTheory = computed(() => {
  const { inc, exp } = curMonthlySeries.value
  const { invBuy, invSell } = curMonthlyFund.value
  let acc = 0
  return inc.map((v, i) => (acc += (v - exp[i]) - (invBuy[i] - invSell[i])))
})

// 理論現金變動月度：當月淨收益 − 當月淨投資（表格用）
const curMonthTheory = computed(() => {
  const { inc, exp } = curMonthlySeries.value
  const { invBuy, invSell } = curMonthlyFund.value
  return inc.map((v, i) => (v - exp[i]) - (invBuy[i] - invSell[i]))
})

// 淨投資月度：每月資金轉移 − 資金回收（表格用）
const curMonthInvNet = computed(() => {
  const f = curMonthlyFund.value
  return f.invBuy.map((v, i) => v - f.invSell[i])
})
// 淨投資累積：逐月把月度淨投資（支出−收入）累加（折線用）
const curCumInvNet = computed(() => {
  const f = curMonthlyFund.value
  let acc = 0
  return f.invBuy.map((v, i) => (acc += v - f.invSell[i]))
})

// ============================================================
// #3 大類年際趨勢（Tab B）— 每非收入 class 一條線
// ============================================================
const histClassTrendDatasets = computed(() => {
  const palette = ['#10b981','#3b82f6','#f59e0b','#8b5cf6','#ef4444','#06b6d4','#ec4899','#84cc16','#6366f1','#f97316','#14b8a6','#a855f7']
  let pi = 0
  const sets = []
  for (const c of store.classes) {
    if (c.cno === incomeCno.value) continue
    const data = histYears.value.map(y => yearCnoSpend.value.get(y)?.get(c.cno) ?? 0)
    if (data.every(v => v === 0)) continue   // 全 0 不畫
    sets.push({
      label: c.name,
      data,
      borderColor: palette[pi % palette.length],
      backgroundColor: palette[pi % palette.length],
      tension: 0.3,
      pointRadius: 3,
      fill: false,
      borderWidth: 1.5,
    })
    pi++
  }
  return sets
})

// Chart.js 小 plugin：
//  - 預算數字：灰色，放預算柱「頂端上方」
//  - 實際數字：類別色，放實際柱「底部」（接近 X 軸基準線）
const valueLabelPlugin = {
  id: 'valueLabel',
  afterDatasetsDraw(chart) {
    const { ctx } = chart
    const budgetIdx = chart.data.datasets.findIndex(d => d.label === '已設預算')
    const actualIdx = chart.data.datasets.findIndex(d => d.label === '實際')
    ctx.save()
    ctx.font = '600 10px sans-serif'
    ctx.textAlign = 'center'

    // 預算（灰，柱頂）
    if (budgetIdx >= 0) {
      const dm = chart.getDatasetMeta(budgetIdx)
      ctx.fillStyle = '#9ca3af'
      ctx.textBaseline = 'bottom'
      dm.data.forEach((bar, i) => {
        const v = chart.data.datasets[budgetIdx].data[i]
        if (v == null || v === 0) return
        ctx.fillText(fmtTw1(v), bar.x, bar.y - 3)
      })
    }

    // 實際（類別色，柱底接近 X 軸；超支柱頂用紅）
    if (actualIdx >= 0) {
      const dm = chart.getDatasetMeta(actualIdx)
      dm.data.forEach((bar, i) => {
        const v = chart.data.datasets[actualIdx].data[i]
        if (v == null || v === 0) return
        const baseY = bar.base ?? chart.chartArea.bottom   // 柱底 y
        // 取邊框色當文字色，超支變紅
        const borderColor = Array.isArray(chart.data.datasets[actualIdx].borderColor)
          ? chart.data.datasets[actualIdx].borderColor[i]
          : chart.data.datasets[actualIdx].borderColor
        ctx.fillStyle = borderColor ?? '#374151'
        ctx.textBaseline = 'top'
        ctx.fillText(fmtTw1(v), bar.x, baseY - 14)   // 接近 X 軸基準線上方
      })
    }
    ctx.restore()
  },
}

// ── canvas refs + chart instances（#1 / #1b / #2 / #3） ──
const budgetCanvas = ref(null)
const investBudgetCanvas = ref(null)
const bucketDetailCanvas = ref(null)
const investDetailCanvas = ref(null)
const monthCanvas = ref(null)
const investMonthCanvas = ref(null)
const fundMonthCanvas = ref(null)
const classTrendCanvas = ref(null)
let budgetChart = null
let investBudgetChart = null
let bucketDetailChart = null
let investDetailChart = null
let monthChart = null
let investMonthChart = null
let fundMonthChart = null
let classTrendChart = null

function drawBucketDetail() {
  if (bucketDetailChart) { bucketDetailChart.destroy(); bucketDetailChart = null }
  if (!bucketDetailCanvas.value) return
  const rows = curBucketDetail.value   // 已含每 class 的調色色彩
  bucketDetailChart = new Chart(bucketDetailCanvas.value, {
    type: 'bar',
    data: {
      labels: rows.map(r => r.name),
      datasets: [
        {
          label: '已設預算',
          data: rows.map(r => r.budget),
          backgroundColor: '#e5e7eb',
          borderColor: '#9ca3af',
          borderWidth: 1,
          borderRadius: 3,
          grouped: false,
          categoryPercentage: 0.7,
          barPercentage: 1.0,
          order: 2,
        },
        {
          label: '實際',
          data: rows.map(r => r.actual),
          backgroundColor: rows.map(r => r.color + '33'),
          borderColor: rows.map(r => r.color),
          borderWidth: 1,
          borderRadius: 3,
          grouped: false,
          categoryPercentage: 0.7,
          barPercentage: 1.0,
          order: 1,
        },
      ],
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      layout: { padding: { top: 18 } },
      scales: {
        y: { beginAtZero: true, ticks: { callback: v => fmtTw(v) } },
        x: {
          ticks: {
            // X 軸類別名：超支用紅色字
            color: (ctx) => {
              const r = rows[ctx.index]
              return r && r.pct != null && r.pct > 100 ? '#ef4444' : '#6b7280'
            },
            font: (ctx) => {
              const r = rows[ctx.index]
              const over = r && r.pct != null && r.pct > 100
              return { size: 11, weight: over ? '700' : '400' }
            },
          },
        },
      },
      plugins: {
        legend: { labels: { boxWidth: 12, font: { size: 11 } } },
        tooltip: {
          callbacks: {
            label: c => `${c.dataset.label}: ${fmtTw1(c.raw)}`,
            footer: items => {
              const r = rows[items[0].dataIndex]
              if (!r.budget) return '無預算設定'
              return `達成率 ${r.pct}% · ${r.diff >= 0 ? '剩 ' : '超 '}${fmtTw1(Math.abs(r.diff))}`
            },
          },
        },
      },
    },
    plugins: [valueLabelPlugin],
  })
}

function drawInvestDetail() {
  if (investDetailChart) { investDetailChart.destroy(); investDetailChart = null }
  if (!investDetailCanvas.value) return
  const rows = curInvestCompare.value
  investDetailChart = new Chart(investDetailCanvas.value, {
    type: 'bar',
    data: {
      labels: rows.map(r => r.name),
      datasets: [
        {
          label: '已設預算',
          data: rows.map(r => r.budget),
          backgroundColor: '#e5e7eb',
          borderColor: '#9ca3af',
          borderWidth: 1,
          borderRadius: 3,
          grouped: false,
          categoryPercentage: 0.7,
          barPercentage: 1.0,
          order: 2,
        },
        {
          label: '實際',
          data: rows.map(r => r.actual),
          backgroundColor: rows.map(r => r.color + '33'),
          borderColor: rows.map(r => r.color),
          borderWidth: 1,
          borderRadius: 3,
          grouped: false,
          categoryPercentage: 0.7,
          barPercentage: 1.0,
          order: 1,
        },
      ],
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      layout: { padding: { top: 18 } },
      scales: {
        y: { beginAtZero: true, ticks: { callback: v => fmtTw(v) } },
        x: {
          ticks: {
            color: (ctx) => {
              const r = rows[ctx.index]
              return r && r.pct != null && r.pct > 100 ? '#ef4444' : '#6b7280'
            },
            font: (ctx) => {
              const r = rows[ctx.index]
              return { size: 11, weight: (r && r.pct != null && r.pct > 100) ? '700' : '400' }
            },
          },
        },
      },
      plugins: {
        legend: { labels: { boxWidth: 12, font: { size: 11 } } },
        tooltip: {
          callbacks: {
            label: c => `${c.dataset.label}: ${fmtTw1(c.raw)}`,
            footer: items => {
              const r = rows[items[0].dataIndex]
              if (!r.budget) return '無預算設定'
              return `達成率 ${r.pct}% · ${r.diff >= 0 ? '剩 ' : '超 '}${fmtTw1(Math.abs(r.diff))}`
            },
          },
        },
      },
    },
    plugins: [valueLabelPlugin],
  })
}

function drawBudget() {
  if (budgetChart) { budgetChart.destroy(); budgetChart = null }
  if (!budgetCanvas.value) return
  const rows = curBucketCompare.value
  budgetChart = new Chart(budgetCanvas.value, {
    type: 'bar',
    data: {
      labels: rows.map(r => r.name),
      datasets: [
        // 已設預算 — 寬底柱（淺灰背景）
        {
          label: '已設預算',
          data: rows.map(r => r.budget),
          backgroundColor: '#e5e7eb',
          borderColor: '#9ca3af',
          borderWidth: 1,
          borderRadius: 3,
          grouped: false,
          categoryPercentage: 0.7,
          barPercentage: 1.0,
          order: 2,
        },
        // 實際 — 同寬疊在前面（20% 透明，色彩固定不因超支變色）
        {
          label: '實際',
          data: rows.map(r => r.actual),
          backgroundColor: rows.map(r => r.color + '33'),
          borderColor: rows.map(r => r.color),
          borderWidth: 1,
          borderRadius: 3,
          grouped: false,
          categoryPercentage: 0.7,
          barPercentage: 1.0,
          order: 1,
        },
      ],
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      layout: { padding: { top: 18 } },   // 為頂端標籤騰空間
      scales: {
        y: { beginAtZero: true, ticks: { callback: v => fmtTw(v) } },
        x: {
          ticks: {
            color: (ctx) => {
              const r = rows[ctx.index]
              return r && r.pct != null && r.pct > 100 ? '#ef4444' : '#6b7280'
            },
            font: (ctx) => {
              const r = rows[ctx.index]
              const over = r && r.pct != null && r.pct > 100
              return { size: 11, weight: over ? '700' : '400' }
            },
          },
        },
      },
      plugins: {
        legend: { labels: { boxWidth: 12, font: { size: 11 } } },
        tooltip: {
          callbacks: {
            label: c => `${c.dataset.label}: ${fmtTw1(c.raw)}`,
            footer: items => {
              const r = rows[items[0].dataIndex]
              if (!r.budget) return '無預算設定'
              return `達成率 ${r.pct}% · ${r.diff >= 0 ? '剩 ' : '超 '}${fmtTw1(Math.abs(r.diff))}`
            },
          },
        },
      },
    },
    plugins: [valueLabelPlugin],
  })
}

function drawInvestBudget() {
  // 投資支出圖表：各投資子項「已設預算 vs 實際」（對齊 drawBudget 樣式）
  if (investBudgetChart) { investBudgetChart.destroy(); investBudgetChart = null }
  if (!investBudgetCanvas.value) return
  const rows = curInvestCompare.value
  investBudgetChart = new Chart(investBudgetCanvas.value, {
    type: 'bar',
    data: {
      labels: rows.map(r => r.name),
      datasets: [
        {
          label: '已設預算',
          data: rows.map(r => r.budget),
          backgroundColor: '#e5e7eb',
          borderColor: '#9ca3af',
          borderWidth: 1,
          borderRadius: 3,
          grouped: false,
          categoryPercentage: 0.7,
          barPercentage: 1.0,
          order: 2,
        },
        {
          label: '實際',
          data: rows.map(r => r.actual),
          backgroundColor: rows.map(r => r.color + '33'),
          borderColor: rows.map(r => r.color),
          borderWidth: 1,
          borderRadius: 3,
          grouped: false,
          categoryPercentage: 0.7,
          barPercentage: 1.0,
          order: 1,
        },
      ],
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      layout: { padding: { top: 18 } },
      scales: {
        y: { beginAtZero: true, ticks: { callback: v => fmtTw(v) } },
        x: {
          ticks: {
            color: (ctx) => {
              const r = rows[ctx.index]
              return r && r.pct != null && r.pct > 100 ? '#ef4444' : '#6b7280'
            },
            font: (ctx) => {
              const r = rows[ctx.index]
              const over = r && r.pct != null && r.pct > 100
              return { size: 11, weight: over ? '700' : '400' }
            },
          },
        },
      },
      plugins: {
        legend: { labels: { boxWidth: 12, font: { size: 11 } } },
        tooltip: {
          callbacks: {
            label: c => `${c.dataset.label}: ${fmtTw1(c.raw)}`,
            footer: items => {
              const r = rows[items[0].dataIndex]
              if (!r.budget) return '無預算設定'
              return `達成率 ${r.pct}% · ${r.diff >= 0 ? '剩 ' : '超 '}${fmtTw1(Math.abs(r.diff))}`
            },
          },
        },
      },
    },
    plugins: [valueLabelPlugin],
  })
}

function drawMonth() {
  if (monthChart) { monthChart.destroy(); monthChart = null }
  if (!monthCanvas.value) return
  const s = curMonthlySeries.value
  const cumSur = curCumSur.value
  monthChart = new Chart(monthCanvas.value, {
    type: 'bar',
    data: {
      labels: Array.from({ length: 12 }, (_, i) => (i + 1) + '月'),
      datasets: [
        { label: '淨收益(月)', data: cumSur, type: 'line', borderColor: '#f59e0b',
          backgroundColor: '#f59e0b', tension: 0.3, pointRadius: 4, fill: false,
          borderWidth: 2.5, order: 0 },
        { label: '實際收入(月)', data: s.inc, backgroundColor: '#10b981', borderRadius: 3, order: 2 },
        { label: '實際支出(月)', data: s.exp, backgroundColor: '#ef4444', borderRadius: 3, order: 2 },
      ],
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      layout: { padding: { right: 8 } },   // 與下方表 pr-2 對齊
      scales: {
        y: {
          afterFit: (a) => { a.width = 56 },  // 與下方表首欄 52px+4 對齊
          ticks: { callback: v => fmtTw(v) },
        },
      },
      plugins: {
        legend: { labels: { boxWidth: 12, font: { size: 11 } } },
        tooltip: { callbacks: { label: c => `${c.dataset.label}: ${fmtTw1(c.raw)}` } },
      },
    },
  })
}

function drawInvestMonth() {
  // 月別投資收支：投資支出(買股+還本金+出借) / 投資收入(賣股本金+收回借款) / 淨投資(支出−收入)
  if (investMonthChart) { investMonthChart.destroy(); investMonthChart = null }
  if (!investMonthCanvas.value) return
  const f = curMonthlyFund.value
  const cumInvNet = curCumInvNet.value   // 累積淨投資（正 = 流出投資）
  investMonthChart = new Chart(investMonthCanvas.value, {
    type: 'bar',
    data: {
      labels: Array.from({ length: 12 }, (_, i) => (i + 1) + '月'),
      datasets: [
        { label: '淨投資(月)', data: cumInvNet, type: 'line', borderColor: '#8b5cf6',
          backgroundColor: '#8b5cf6', tension: 0.3, pointRadius: 4, fill: false,
          borderWidth: 2.5, order: 0 },
        { label: '資金轉移(月)', data: f.invBuy,  backgroundColor: '#ef4444', borderRadius: 3, order: 2 },
        { label: '資金回收(月)', data: f.invSell, backgroundColor: '#10b981', borderRadius: 3, order: 2 },
      ],
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      layout: { padding: { right: 8 } },
      scales: {
        y: {
          afterFit: (a) => { a.width = 56 },
          ticks: { callback: v => fmtTw(v) },
        },
      },
      plugins: {
        legend: { labels: { boxWidth: 12, font: { size: 11 } } },
        tooltip: { callbacks: { label: c => `${c.dataset.label}: ${fmtTw1(c.raw)}` } },
      },
    },
  })
}

function drawFundMonth() {
  if (fundMonthChart) { fundMonthChart.destroy(); fundMonthChart = null }
  if (!fundMonthCanvas.value) return
  const cum = curCumCash.value
  const actual = cum.map((o) => o.started ? o.v : null)  // null before first snapshot
  const theory = curCumTheory.value
  fundMonthChart = new Chart(fundMonthCanvas.value, {
    type: 'line',
    data: {
      labels: Array.from({ length: 12 }, (_, i) => (i + 1) + '月'),
      datasets: [
        { label: '實際現金變動', data: actual,
          borderColor: '#06b6d4', backgroundColor: '#06b6d414', tension: 0.3, pointRadius: 4,
          fill: true, borderWidth: 2.5, order: 0 },
        { label: '理論現金變動', data: theory,
          borderColor: '#f59e0b', backgroundColor: 'transparent', tension: 0.3, pointRadius: 4,
          fill: false, borderWidth: 2, borderDash: [5, 3], order: 1 },
      ],
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      layout: { padding: { right: 8 } },
      scales: {
        y: {
          afterFit: (a) => { a.width = 56 },
          ticks: { callback: v => fmtTw(v) },
        },
      },
      plugins: {
        legend: { labels: { boxWidth: 12, font: { size: 11 } } },
        tooltip: {
          callbacks: {
            label: c => `${c.dataset.label}: ${fmtTw1(c.raw)}`,
            afterBody: (items) => {
              const i = items[0]?.dataIndex
              if (i != null && !curMonthlyFund.value.hasData[i]) return ['（累積至上次快照）']
              return null
            },
          },
        },
      },
    },
  })
}

function drawClassTrend() {
  if (classTrendChart) { classTrendChart.destroy(); classTrendChart = null }
  if (!classTrendCanvas.value) return
  classTrendChart = new Chart(classTrendCanvas.value, {
    type: 'line',
    data: { labels: histYears.value, datasets: histClassTrendDatasets.value },
    options: {
      responsive: true, maintainAspectRatio: false,
      scales: { y: { ticks: { callback: v => fmtTw(v) } } },
      plugins: {
        legend: { labels: { boxWidth: 12, font: { size: 10 } } },
        tooltip: { callbacks: { label: c => `${c.dataset.label}: ${fmtTw1(c.raw)}` } },
      },
    },
  })
}

// Tab A 切換 / 年份變動時繪月別圖 + 預算對照圖 + 桶位細部
watch(
  [activeTab, selectedYear, curMonthlySeries, curMonthlyFund, monthCanvas, investMonthCanvas, fundMonthCanvas,
   curBucketCompare, budgetCanvas, curInvestCompare, investBudgetCanvas, curBucketDetail, bucketDetailCanvas, bucketTab, investDetailCanvas],
  () => {
    if (activeTab.value !== 'yearly') return
    nextTick(() => { drawMonth(); drawInvestMonth(); drawBudget(); drawInvestBudget(); drawBucketDetail(); drawInvestDetail(); drawFundMonth() })
  },
  { deep: true, immediate: true },
)

// Tab B 加入大類趨勢重繪
watch(
  [activeTab, histClassTrendDatasets, classTrendCanvas],
  () => {
    if (activeTab.value !== 'historical') return
    nextTick(drawClassTrend)
  },
  { deep: true, immediate: true },
)
</script>

<template>
  <div class="p-3 h-full overflow-auto space-y-3 bg-zinc-50 dark:bg-zinc-950">
    <!-- 無 DB 提示 -->
    <div v-if="!store.db" class="panel">
      <span class="panel-title">圖表</span>
      <div class="text-[13px] text-zinc-500 py-4">請先到「設定」頁載入資料庫</div>
    </div>

    <template v-else>
      <!-- ============== Tab 切換 ============== -->
      <div class="flex items-end gap-1 border-b border-zinc-200 dark:border-zinc-700">
        <button class="tab" :class="{ active: activeTab === 'yearly' }" @click="activeTab = 'yearly'">
          📊 年度資料
        </button>
        <button class="tab" :class="{ active: activeTab === 'historical' }" @click="activeTab = 'historical'">
          📈 歷年趨勢
        </button>
        <!-- Tab A：單年選擇（與 Tab 同行） -->
        <div v-if="activeTab === 'yearly'"
             class="flex items-center gap-2 pb-1 ml-3 text-[12px]">
          <span class="text-zinc-500">年份</span>
          <select v-model="selectedYear"
                  class="border rounded px-2 py-0.5 text-[12px] bg-white dark:bg-zinc-800 dark:border-zinc-600">
            <option v-for="y in allYearsDesc" :key="y" :value="y">{{ y }}</option>
          </select>
          <span v-if="!allYears.length" class="text-[11px] text-zinc-400">（無交易資料）</span>
        </div>
        <!-- 歷年趨勢的年度範圍選擇器（與 Tab 同行） -->
        <div v-if="activeTab === 'historical'"
             class="flex items-center gap-2 pb-1 ml-3 text-[12px]">
          <span class="text-zinc-500">年度範圍</span>
          <select v-model="histYearStart"
                  class="border rounded px-2 py-0.5 text-[12px] bg-white dark:bg-zinc-800 dark:border-zinc-600">
            <option v-for="y in histYearStartOptions" :key="'s'+y" :value="y">{{ y }}</option>
          </select>
          <span class="text-zinc-400">~</span>
          <select v-model="histYearEnd"
                  class="border rounded px-2 py-0.5 text-[12px] bg-white dark:bg-zinc-800 dark:border-zinc-600">
            <option v-for="y in histYearEndOptions" :key="'e'+y" :value="y">{{ y }}</option>
          </select>
          <span class="text-[11px] text-zinc-400">共 {{ histYears.length }} 年</span>
        </div>
      </div>

      <!-- ====================================================== -->
      <!-- Tab A：年度資料                                           -->
      <!-- ====================================================== -->
      <div v-if="activeTab === 'yearly'" class="space-y-3">

        <!-- KPI 5+3 卡 2 行（分組對齊：收支→淨收益、投資→淨投資、現金→理論現金變動）-->
        <section v-if="curYearData" class="panel">
          <span class="panel-title">💰 KPI 綜覽</span>
          <!-- Row 1: 5 原始項 -->
          <div class="grid grid-cols-2 md:grid-cols-5 gap-2 pt-1">
            <div class="rounded p-3 border-l-4" style="border-color:#10b981;background:#10b9810f">
              <div class="text-[12px] text-zinc-500 dark:text-zinc-400">{{ selectedYear }} 年實際收入</div>
              <div class="text-[20px] font-bold" style="color:#10b981">{{ fmtW(curYearData.inc) }}</div>
              <div class="text-[11px] text-zinc-400">
                {{ curYearData.incChange != null
                  ? (curYearData.incChange >= 0 ? '↑ ' : '↓ ') + Math.abs(curYearData.incChange) + '% (vs 上年)'
                  : '—' }}
              </div>
            </div>
            <div class="rounded p-3 border-l-4" style="border-color:#ef4444;background:#ef44440f">
              <div class="text-[12px] text-zinc-500 dark:text-zinc-400">{{ selectedYear }} 年實際支出</div>
              <div class="text-[20px] font-bold" style="color:#ef4444">{{ fmtW(curYearData.exp) }}</div>
              <div class="text-[11px] text-zinc-400">
                {{ curYearData.expChange != null
                  ? (curYearData.expChange >= 0 ? '↑ ' : '↓ ') + Math.abs(curYearData.expChange) + '% (vs 上年)'
                  : '（含投資損失）' }}
              </div>
            </div>
            <div class="rounded p-3 border-l-4" style="border-color:#10b981;background:#10b9810f;border-style:dashed">
              <div class="text-[12px] text-zinc-500 dark:text-zinc-400">{{ selectedYear }} 年資金回收</div>
              <div class="text-[20px] font-bold" style="color:#10b981">{{ fmtW(curYearData.investIn) }}</div>
              <div class="text-[11px] text-zinc-400">
                {{ curYearData.investInChange != null
                  ? (curYearData.investInChange >= 0 ? '↑ ' : '↓ ') + Math.abs(curYearData.investInChange) + '% (vs 上年)'
                  : '（賣股本金 + 收回借款）' }}
              </div>
            </div>
            <div class="rounded p-3 border-l-4" style="border-color:#ef4444;background:#ef44440f;border-style:dashed">
              <div class="text-[12px] text-zinc-500 dark:text-zinc-400">{{ selectedYear }} 年資金轉移</div>
              <div class="text-[20px] font-bold" style="color:#ef4444">{{ fmtW(curYearData.investOut) }}</div>
              <div class="text-[11px] text-zinc-400">
                {{ curYearData.investOutChange != null
                  ? (curYearData.investOutChange >= 0 ? '↑ ' : '↓ ') + Math.abs(curYearData.investOutChange) + '% (vs 上年)'
                  : '（買股 + 還房貸本金 + 出借款）' }}
              </div>
            </div>
            <div class="rounded p-3 border-l-4" style="border-color:#06b6d4;background:#06b6d40f">
              <div class="text-[12px] text-zinc-500 dark:text-zinc-400">{{ selectedYear }} 年實際現金變動</div>
              <div class="text-[20px] font-bold"
                   :style="{ color: (curYearData.realCashChg ?? 0) >= 0 ? '#06b6d4' : '#ef4444' }">
                {{ curYearData.realCashChg != null
                  ? (curYearData.realCashChg >= 0 ? '+' : '') + fmtW(curYearData.realCashChg)
                  : '—' }}
              </div>
              <div class="text-[11px] text-zinc-400">
                {{ curYearData.realCashChg != null
                  ? '今年 ' + fmtW(curYearData.curCash) + ' − 去年 ' + fmtW(curYearData.prevCash)
                  : '今年現金 − 去年現金（缺餘額）' }}
              </div>
            </div>
          </div>
          <!-- Row 2: 3 衍生項（對齊 2+2+1：淨收益↔收支、淨投資↔投資、理論現金變動↔現金變動）-->
          <div class="grid grid-cols-1 md:grid-cols-5 gap-2 pt-2">
            <div class="rounded p-3 border-l-4 md:col-span-2" style="border-color:#f59e0b;background:#f59e0b0f">
              <div class="text-[12px] text-zinc-500 dark:text-zinc-400">{{ selectedYear }} 年淨收益</div>
              <div class="text-[20px] font-bold"
                   :style="{ color: curYearData.netGain >= 0 ? '#f59e0b' : '#ef4444' }">
                {{ (curYearData.netGain >= 0 ? '+' : '') + fmtW(curYearData.netGain) }}
              </div>
              <div class="text-[11px] text-zinc-400">實際收入 − 實際支出　儲蓄率 {{ curYearData.savRate }}%</div>
            </div>
            <div class="rounded p-3 border-l-4 md:col-span-2" style="border-color:#8b5cf6;background:#8b5cf60f">
              <div class="text-[12px] text-zinc-500 dark:text-zinc-400">{{ selectedYear }} 年淨投資</div>
              <div class="text-[20px] font-bold"
                   :style="{ color: curYearData.netInvest >= 0 ? '#8b5cf6' : '#10b981' }">
                {{ (curYearData.netInvest >= 0 ? '+' : '') + fmtW(curYearData.netInvest) }}
              </div>
              <div class="text-[11px] text-zinc-400">資金轉移 − 資金回收（正 = 淨流出）</div>
            </div>
            <div class="rounded p-3 border-l-4 md:col-span-1" style="border-color:#0891b2;background:#0891b20f">
              <div class="text-[12px] text-zinc-500 dark:text-zinc-400">{{ selectedYear }} 年理論現金變動</div>
              <div class="text-[20px] font-bold"
                   :style="{ color: curYearData.netCash >= 0 ? '#0891b2' : '#ef4444' }">
                {{ (curYearData.netCash >= 0 ? '+' : '') + fmtW(curYearData.netCash) }}
              </div>
              <div class="text-[11px] text-zinc-400">
                {{ curYearData.cashDiff != null
                  ? '淨收益 − 淨投資　(實際差 ' + (curYearData.cashDiff >= 0 ? '+' : '') + fmtW(curYearData.cashDiff) + ')'
                  : '淨收益 − 淨投資' }}
              </div>
            </div>
          </div>
        </section>

        <!-- KPI 下第一列：月別收支 / 月別投資收支 / 月別資金變動 三欄（對齊 KPI 收支/投資/現金三組）-->
        <div class="grid grid-cols-1 xl:grid-cols-3 gap-3">

          <!-- 月別收支（對應 KPI 收支組）-->
          <section class="panel">
            <span class="panel-title">📅 {{ selectedYear }} 淨收益(實際收支)</span>
            <div class="h-[240px] mt-2"><canvas ref="monthCanvas"></canvas></div>
            <!-- 月別數值表（每月一欄，對齊圖表繪圖區） -->
            <div class="mt-2 pr-2 text-[10px] leading-tight">
              <div v-for="row in [
                { label: '實際收入(月)', color: '#10b981', data: curMonthlySeries.inc },
                { label: '實際支出(月)', color: '#ef4444', data: curMonthlySeries.exp },
                { label: '淨收益(月)', color: '#f59e0b', data: curMonthlySeries.sur, bold: true },
              ]" :key="row.label"
                 class="grid items-center border-b border-zinc-100 dark:border-zinc-800 last:border-b-0"
                 :style="{ gridTemplateColumns: '56px repeat(12, minmax(0,1fr))' }">
                <div class="text-zinc-500 dark:text-zinc-400 font-medium"
                     :style="{ color: row.color }">{{ row.label }}</div>
                <div v-for="(v, i) in row.data" :key="i"
                     class="text-center tabular-nums py-0.5"
                     :class="[
                       row.bold ? 'font-semibold' : '',
                       v === 0 ? 'text-zinc-300 dark:text-zinc-600'
                         : (row.label === '淨收益(月)' && v < 0 ? 'text-red-500' : ''),
                     ]"
                     :style="row.bold ? { color: row.color } : {}">
                  {{ v === 0 ? '—' : fmtTw1(v) }}
                </div>
              </div>
            </div>
          </section>

          <!-- 月別投資收支（對應 KPI 投資組：投資支出/投資收入 ➜ 淨投資）-->
          <section class="panel">
            <span class="panel-title">📈 {{ selectedYear }} 淨投資(實際投資)</span>
            <div class="h-[240px] mt-2"><canvas ref="investMonthCanvas"></canvas></div>
            <div class="mt-2 pr-2 text-[10px] leading-tight">
              <div v-for="row in [
                { label: '資金轉移(月)', color: '#ef4444', data: curMonthlyFund.invBuy },
                { label: '資金回收(月)', color: '#10b981', data: curMonthlyFund.invSell },
                { label: '淨投資(月)',   color: '#8b5cf6', data: curMonthInvNet, bold: true },
              ]" :key="row.label"
                 class="grid items-center border-b border-zinc-100 dark:border-zinc-800 last:border-b-0"
                 :style="{ gridTemplateColumns: '56px repeat(12, minmax(0,1fr))' }">
                <div class="text-zinc-500 dark:text-zinc-400 font-medium"
                     :style="{ color: row.color }">{{ row.label }}</div>
                <div v-for="(v, i) in row.data" :key="i"
                     class="text-center tabular-nums py-0.5"
                     :class="[
                       row.bold ? 'font-semibold' : '',
                       v === 0 ? 'text-zinc-300 dark:text-zinc-600' : '',
                     ]"
                     :style="row.bold ? { color: row.color } : {}">
                  {{ v === 0 ? '—' : fmtTw1(v) }}
                </div>
              </div>
            </div>
          </section>

          <!-- 月別資金變動（Δ現金 累積）-->
          <section class="panel">
            <span class="panel-title">💧 {{ selectedYear }} 現金變動(實際 VS 理論)</span>
            <div class="h-[240px] mt-2"><canvas ref="fundMonthCanvas"></canvas></div>
            <div class="mt-2 pr-2 text-[10px] leading-tight">
              <!-- 實際現金變動列（月度Δ） -->
              <div class="grid items-center border-b border-zinc-100 dark:border-zinc-800"
                   :style="{ gridTemplateColumns: '56px repeat(12, minmax(0,1fr))' }">
                <div class="font-semibold" style="color: #06b6d4">Δ實際</div>
                <div v-for="(_, i) in Array(12)" :key="'a'+i"
                     class="text-center tabular-nums py-0.5 font-semibold"
                     :style="curMonthlyFund.dCash[i] < 0 ? { color: '#ef4444' } : { color: '#06b6d4' }">
                  {{ curMonthlyFund.hasData[i] ? fmtTw1(curMonthlyFund.dCash[i]) : '—' }}
                </div>
              </div>
              <!-- 理論現金變動列（月度） -->
              <div class="grid items-center"
                   :style="{ gridTemplateColumns: '56px repeat(12, minmax(0,1fr))' }">
                <div class="font-semibold" style="color: #f59e0b">Δ理論</div>
                <div v-for="(v, i) in curMonthTheory" :key="'t'+i"
                     class="text-center tabular-nums py-0.5 font-semibold"
                     :style="{ color: v < 0 ? '#ef4444' : '#f59e0b' }">
                  {{ fmtTw1(v) }}
                </div>
              </div>
            </div>
            <div class="text-[11px] text-zinc-400 mt-1 leading-relaxed" style="padding-left: 56px">
              · 實際（藍）：當月實際現金金額 − 前月現金金額；首個快照前顯示「—」<br>
              · 理論（橙虛線）：淨收益 − 淨投資 逐月累積；差距 = 未記錄現金流
            </div>
          </section>

        </div>
        <!-- /KPI 下月別三欄 -->

        <!-- 實際支出圖表 + 投資支出圖表 並列 -->
        <div class="grid grid-cols-1 xl:grid-cols-2 gap-3">
          <section class="panel">
            <span class="panel-title">🎯 實際支出圖表</span>
            <div class="h-[240px] mt-2"><canvas ref="budgetCanvas"></canvas></div>
            <!-- 達成率小條（同一行，對齊上方圖表繪圖區） -->
            <div class="grid grid-cols-4 gap-1.5 mt-2 pl-10 pr-2">
              <div v-for="b in curBucketCompare" :key="b.key"
                   class="rounded px-2 py-1 border-l-4 text-[11px] leading-tight text-center"
                   :style="{ borderColor: b.color, background: b.color + '0a' }">
                <div class="flex items-center justify-center gap-1.5">
                  <span class="text-zinc-600 dark:text-zinc-300 font-medium">{{ b.name }}</span>
                  <span :class="b.pct == null ? 'text-zinc-400'
                    : (b.pct > 100 ? 'text-red-500 font-bold'
                      : (b.pct > 80 ? 'text-amber-500' : 'text-emerald-600'))">
                    {{ b.pct == null ? '無預算' : b.pct + '%' }}
                  </span>
                </div>
                <div class="flex items-baseline justify-center gap-1">
                  <span class="font-semibold" :style="{ color: b.color }">{{ fmtW(b.actual) }}</span>
                  <span class="text-zinc-400">/ {{ fmtW(b.budget) }}</span>
                </div>
              </div>
            </div>
          </section>

          <!-- 投資支出圖表（對齊 實際支出圖表；分類 = 投資子項，預算多半只有股票） -->
          <section class="panel">
            <span class="panel-title">📊 資金轉移圖表</span>
            <div class="h-[240px] mt-2"><canvas ref="investBudgetCanvas"></canvas></div>
            <!-- 達成率小條（同一行，N 卡平均分配，對齊上方圖表繪圖區） -->
            <div class="grid gap-1.5 mt-2 pl-10 pr-2"
                 :style="{ gridTemplateColumns: `repeat(${curInvestCompare.length || 1}, minmax(0, 1fr))` }">
              <div v-for="b in curInvestCompare" :key="b.sno"
                   class="rounded px-2 py-1 border-l-4 text-[11px] leading-tight text-center"
                   :style="{ borderColor: b.color, background: b.color + '0a' }">
                <div class="flex items-center justify-center gap-1.5">
                  <span class="text-zinc-600 dark:text-zinc-300 font-medium truncate">{{ b.name }}</span>
                  <span :class="b.pct == null ? 'text-zinc-400'
                    : (b.pct > 100 ? 'text-red-500 font-bold'
                      : (b.pct > 80 ? 'text-amber-500' : 'text-emerald-600'))">
                    {{ b.pct == null ? '無預算' : b.pct + '%' }}
                  </span>
                </div>
                <div class="flex items-baseline justify-center gap-1">
                  <span class="font-semibold" :style="{ color: b.color }">{{ fmtW(b.actual) }}</span>
                  <span class="text-zinc-400">/ {{ fmtW(b.budget) }}</span>
                </div>
              </div>
            </div>
          </section>
        </div>

        <!-- 實際支出圖表 各項細部 + 投資支出圖表 各項細部 並列 -->
        <div class="grid grid-cols-1 xl:grid-cols-2 gap-3">
          <section class="panel">
            <div class="flex items-center justify-between flex-wrap gap-2">
              <span class="panel-title">🔍 實際支出圖表 各項細部</span>
              <div class="flex rounded-md overflow-hidden border border-zinc-200 dark:border-zinc-700 text-[12px]">
                <button v-for="g in EXPENSE_GROUPS" :key="g.key"
                        class="px-3 py-1 transition-colors"
                        :class="bucketTab === g.key
                          ? 'text-white font-semibold'
                          : 'bg-white dark:bg-zinc-800 text-zinc-600 dark:text-zinc-300 hover:bg-zinc-50 dark:hover:bg-zinc-700'"
                        :style="bucketTab === g.key ? { background: g.color } : {}"
                        @click="bucketTab = g.key">
                  {{ g.name }}
                </button>
              </div>
            </div>
            <div class="h-[260px] mt-2"><canvas ref="bucketDetailCanvas"></canvas></div>
            <!-- 達成率小條 -->
            <div class="grid gap-1.5 mt-2 pl-10 pr-2"
                 :style="{ gridTemplateColumns: `repeat(${curBucketDetail.length || 1}, minmax(0, 1fr))` }">
              <div v-for="d in curBucketDetail" :key="d.cno"
                   class="rounded px-2 py-1 border-l-4 text-[11px] leading-tight text-center"
                   :style="{ borderColor: d.color, background: d.color + '0a' }">
                <div class="flex items-center justify-center gap-1.5">
                  <span class="text-zinc-600 dark:text-zinc-300 font-medium truncate">{{ d.name }}</span>
                  <span :class="d.pct == null ? 'text-zinc-400'
                    : (d.pct > 100 ? 'text-red-500 font-bold'
                      : (d.pct > 80 ? 'text-amber-500' : 'text-emerald-600'))">
                    {{ d.pct == null ? '無預算' : d.pct + '%' }}
                  </span>
                </div>
                <div class="flex items-baseline justify-center gap-1">
                  <span class="font-semibold" :style="{ color: d.color }">{{ fmtW(d.actual) }}</span>
                  <span class="text-zinc-400">/ {{ fmtW(d.budget) }}</span>
                </div>
              </div>
            </div>
          </section>

          <section class="panel">
            <span class="panel-title">📊 資金轉移圖表 各項細部</span>
            <div class="h-[260px] mt-2"><canvas ref="investDetailCanvas"></canvas></div>
            <!-- 達成率小條 -->
            <div class="grid gap-1.5 mt-2 pl-10 pr-2"
                 :style="{ gridTemplateColumns: `repeat(${curInvestCompare.length || 1}, minmax(0, 1fr))` }">
              <div v-for="d in curInvestCompare" :key="d.sno"
                   class="rounded px-2 py-1 border-l-4 text-[11px] leading-tight text-center"
                   :style="{ borderColor: d.color, background: d.color + '0a' }">
                <div class="flex items-center justify-center gap-1.5">
                  <span class="text-zinc-600 dark:text-zinc-300 font-medium truncate">{{ d.name }}</span>
                  <span :class="d.pct == null ? 'text-zinc-400'
                    : (d.pct > 100 ? 'text-red-500 font-bold'
                      : (d.pct > 80 ? 'text-amber-500' : 'text-emerald-600'))">
                    {{ d.pct == null ? '無預算' : d.pct + '%' }}
                  </span>
                </div>
                <div class="flex items-baseline justify-center gap-1">
                  <span class="font-semibold" :style="{ color: d.color }">{{ fmtW(d.actual) }}</span>
                  <span class="text-zinc-400">{{ d.budget ? '/ ' + fmtW(d.budget) : '' }}</span>
                </div>
              </div>
            </div>
          </section>
        </div>

        <!-- 實際支出明細 + 投資支出明細 並列 -->
        <div class="grid grid-cols-1 xl:grid-cols-2 gap-3">
        <!-- 實際支出明細 -->
        <section class="panel">
          <span class="panel-title">🧾 實際支出明細</span>
          <div class="pt-1">
            <!-- 桶位 KPI -->
            <div class="flex flex-wrap gap-2 mb-3">
              <div
                v-for="g in curExpenseGroups" :key="g.key"
                class="flex-1 min-w-[130px] rounded p-2.5 border-l-4"
                :style="{ borderColor: g.color, background: g.color + '0f' }"
              >
                <div class="text-[12px] text-zinc-500 dark:text-zinc-400">
                  {{ g.name }} <span class="text-zinc-400">{{ g.note }}</span>
                </div>
                <div class="text-[17px] font-bold" :style="{ color: g.color }">{{ fmtW(g.total) }}</div>
                <div class="text-[11px] text-zinc-400">
                  佔總支出 {{ fmtPct(g.total, curExpenseTotal) }}
                </div>
              </div>
            </div>

            <!-- toolbar：模式切換 + 顯示預算 -->
            <div class="flex items-center justify-end gap-3 mb-2 text-[12px]">
              <div class="flex rounded-md overflow-hidden border border-zinc-200 dark:border-zinc-700">
                <button class="px-2 py-0.5 transition-colors"
                        :class="expenseVisMode === 'amount'
                          ? 'bg-blue-500 text-white font-semibold'
                          : 'bg-white dark:bg-zinc-800 text-zinc-600 dark:text-zinc-300 hover:bg-zinc-50'"
                        @click="expenseVisMode = 'amount'">金額</button>
                <button class="px-2 py-0.5 transition-colors border-l border-zinc-200 dark:border-zinc-700"
                        :class="expenseVisMode === 'percent'
                          ? 'bg-blue-500 text-white font-semibold'
                          : 'bg-white dark:bg-zinc-800 text-zinc-600 dark:text-zinc-300 hover:bg-zinc-50'"
                        @click="expenseVisMode = 'percent'">百分比</button>
              </div>
              <label class="inline-flex items-center gap-1.5 text-zinc-600 dark:text-zinc-300 cursor-pointer select-none">
                <input type="checkbox" v-model="showBudgetInExpense" class="accent-zinc-500" />
                顯示預算
              </label>
            </div>
            <!-- 主表 -->
            <div class="text-[12px] text-zinc-500 mb-1">點擊大類列展開 / 收合子項</div>
            <table class="w-full text-[13px]">
              <thead class="text-zinc-600 dark:text-zinc-300">
                <tr class="border-b border-zinc-200 dark:border-zinc-700 text-left">
                  <th class="w-[30px]"></th>
                  <th class="w-[140px] py-1">大類</th>
                  <th class="w-[110px] text-right">金額</th>
                  <th class="w-[110px] text-right text-zinc-400">預算</th>
                  <th class="w-[60px] text-right">佔比</th>
                  <th>視覺化</th>
                  <th class="w-[50px] text-center">子項</th>
                </tr>
              </thead>
              <tbody v-for="g in curExpenseGroups" :key="g.key">
                <tr :style="{ background: g.color + '15' }">
                  <td colspan="7" class="px-2 py-1.5 font-bold" :style="{ color: g.color }">
                    <span class="inline-block w-2 h-2 rounded-full mr-1.5" :style="{ background: g.color }"></span>
                    {{ g.name }}
                    <span class="text-zinc-400 font-normal text-[11px]">（{{ g.note }}）</span>
                    — <span class="text-zinc-700 dark:text-zinc-200">{{ fmt(g.total) }}</span>
                    <span class="text-zinc-400 font-normal">（{{ fmtPct(g.total, curExpenseTotal) }}）</span>
                  </td>
                </tr>
                <template v-for="cat in g.cats" :key="cat.cno">
                  <tr
                    class="border-b border-zinc-100 dark:border-zinc-800 cursor-pointer hover:bg-zinc-50 dark:hover:bg-zinc-800/50"
                    @click="toggleExpCat(cat.cno)"
                  >
                    <td class="text-center text-zinc-400">
                      {{ expandedExpCat.has(cat.cno) ? '▼' : '▶' }}
                    </td>
                    <td class="py-1 font-medium">{{ cat.name }}</td>
                    <td class="text-right">{{ fmt(cat.amount) }}</td>
                    <td class="text-right text-zinc-400">
                      {{ (curClassBudget.get(cat.cno) ?? 0) > 0 ? fmt(curClassBudget.get(cat.cno)) : '—' }}
                    </td>
                    <td class="text-right text-zinc-500">
                      {{ fmtPct(cat.amount, curExpenseTotal) }}
                    </td>
                    <td class="py-1.5 px-2">
                      <div class="relative h-4">
                        <!-- 100% 基準虛線（百分比模式且有預算才顯示） -->
                        <div v-if="expenseVisMode === 'percent' && (curClassBudget.get(cat.cno) ?? 0) > 0"
                             class="absolute inset-y-0 border-r border-dashed border-zinc-400 dark:border-zinc-500"
                             style="width: 83.33%; left: 0; pointer-events: none;">
                        </div>
                        <!-- 預算灰底柱 -->
                        <div v-if="showBudgetInExpense && (curClassBudget.get(cat.cno) ?? 0) > 0"
                             class="absolute inset-y-0 left-0 rounded bg-zinc-300 dark:bg-zinc-600"
                             :style="{ width: expBarWidth(cat, 'budget') + '%', minWidth: '2px' }">
                        </div>
                        <!-- 實際彩色柱 -->
                        <div class="absolute inset-y-0 left-0 rounded"
                             :style="{
                               background: g.color,
                               opacity: showBudgetInExpense ? 0.75 : 1,
                               width: expBarWidth(cat, 'actual') + '%',
                               minWidth: '2px',
                             }">
                        </div>
                        <!-- 數值標籤：金額模式 → 金額；百分比模式 → 達成率% -->
                        <div class="absolute inset-y-0 flex items-center text-[10px] font-semibold tabular-nums whitespace-nowrap pointer-events-none"
                             :style="{
                               left: 'calc(' + Math.max(expBarWidth(cat, 'actual'), showBudgetInExpense ? expBarWidth(cat, 'budget') : 0) + '% + 4px)',
                               color: (curClassBudget.get(cat.cno) ?? 0) > 0
                                 && cat.amount > curClassBudget.get(cat.cno)
                                 ? '#ef4444' : '#52525b',
                             }">
                          {{ expenseVisMode === 'percent'
                            ? ((curClassBudget.get(cat.cno) ?? 0) > 0
                                ? (cat.amount / curClassBudget.get(cat.cno) * 100).toFixed(1) + '%'
                                : '—')
                            : fmtW(cat.amount) }}
                        </div>
                      </div>
                    </td>
                    <td class="text-center text-zinc-500 text-[12px]">
                      {{ classSubItems(selectedYear, cat.cno).length }}
                    </td>
                  </tr>
                  <tr
                    v-for="item in (expandedExpCat.has(cat.cno) ? classSubItems(selectedYear, cat.cno) : [])"
                    :key="cat.cno + '-' + item.sno"
                    class="bg-zinc-50 dark:bg-zinc-800/30"
                  >
                    <td></td>
                    <td class="pl-6 text-zinc-500 text-[12px]">└ {{ item.name }}</td>
                    <td class="text-right text-zinc-500 text-[12px]">{{ fmt(item.amount) }}</td>
                    <td></td>
                    <td class="text-right text-zinc-400 text-[11px]">
                      {{ fmtPct(item.amount, cat.amount) }}
                    </td>
                    <td class="py-1 px-2">
                      <div
                        class="h-2 rounded opacity-40"
                        :style="{
                          background: g.color,
                          width: (cat.amount ? item.amount / cat.amount * 100 : 0) + '%',
                          minWidth: '1px',
                        }"
                      ></div>
                    </td>
                    <td></td>
                  </tr>
                </template>
              </tbody>
              <tbody>
                <tr class="bg-zinc-800 text-white font-bold dark:bg-zinc-700">
                  <td></td>
                  <td class="py-1.5 px-2">總計</td>
                  <td class="text-right pr-2">{{ fmt(curExpenseTotal) }}</td>
                  <td class="text-right pr-2 text-zinc-300">{{ curBudgetTotal ? fmt(curBudgetTotal) : '—' }}</td>
                  <td class="text-right pr-2">100%</td>
                  <td></td>
                  <td></td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>

        <!-- 投資支出明細 -->
        <section class="panel">
          <span class="panel-title">💼 資金轉移明細</span>
          <div class="pt-1">
            <div v-if="curInvestTotal === 0" class="text-[13px] text-zinc-500 py-3 text-center">
              {{ selectedYear }} 年無投資支出資料
            </div>
            <template v-else>
              <!-- 子項 KPI -->
              <div class="grid grid-cols-5 gap-2 mb-3">
                <div
                  v-for="it in curInvestItems"
                  :key="it.sno"
                  class="rounded p-2.5 border-l-4"
                  :style="{ borderColor: it.color, background: it.color + '0f' }"
                >
                  <div class="text-[12px] text-zinc-500 dark:text-zinc-400">{{ it.name }}</div>
                  <div class="text-[17px] font-bold" :style="{ color: it.color }">{{ fmtW(it.amount) }}</div>
                  <div class="text-[11px] text-zinc-400">
                    佔投資支出 {{ fmtPct(it.amount, curInvestTotal) }}
                  </div>
                </div>
              </div>
              <!-- toolbar：金額/百分比 + 顯示預算 -->
              <div class="flex items-center justify-end gap-3 mb-2 text-[12px]">
                <div class="flex rounded-md overflow-hidden border border-zinc-200 dark:border-zinc-700">
                  <button class="px-2 py-0.5 transition-colors"
                          :class="investVisMode === 'amount'
                            ? 'bg-blue-500 text-white font-semibold'
                            : 'bg-white dark:bg-zinc-800 text-zinc-600 dark:text-zinc-300 hover:bg-zinc-50'"
                          @click="investVisMode = 'amount'">金額</button>
                  <button class="px-2 py-0.5 transition-colors border-l border-zinc-200 dark:border-zinc-700"
                          :class="investVisMode === 'percent'
                            ? 'bg-blue-500 text-white font-semibold'
                            : 'bg-white dark:bg-zinc-800 text-zinc-600 dark:text-zinc-300 hover:bg-zinc-50'"
                          @click="investVisMode = 'percent'">百分比</button>
                </div>
                <label class="inline-flex items-center gap-1.5 text-zinc-600 dark:text-zinc-300 cursor-pointer select-none">
                  <input type="checkbox" v-model="showBudgetInInvest" class="accent-zinc-500" />
                  顯示預算
                </label>
              </div>
              <!-- 主表 -->
              <div class="text-[12px] text-zinc-500 mb-1">點擊「股票」列展開 / 收合個別買進交易</div>
              <table class="w-full text-[13px]">
                <thead class="text-zinc-600 dark:text-zinc-300">
                  <tr class="border-b border-zinc-200 dark:border-zinc-700 text-left">
                    <th class="w-[30px]"></th>
                    <th class="w-[140px] py-1">子項</th>
                    <th class="w-[110px] text-right">金額</th>
                    <th class="w-[110px] text-right text-zinc-400">預算</th>
                    <th class="w-[60px] text-right">佔比</th>
                    <th>視覺化</th>
                  </tr>
                </thead>
                <tbody>
                  <template v-for="it in curInvestItems" :key="it.sno">
                    <tr
                      class="border-b border-zinc-100 dark:border-zinc-800"
                      :class="it.sno === 101 ? 'cursor-pointer hover:bg-zinc-50 dark:hover:bg-zinc-800/50' : ''"
                      @click="it.sno === 101 && toggleInvest(101)"
                    >
                      <td class="text-center text-zinc-400">
                        <span v-if="it.sno === 101">{{ expandedInvest.has(101) ? '▼' : '▶' }}</span>
                      </td>
                      <td class="py-1 font-medium">
                        <span class="inline-block w-2 h-2 rounded-full mr-1.5" :style="{ background: it.color }"></span>
                        {{ it.name }}
                      </td>
                      <td class="text-right" :style="{ color: it.budget > 0 && it.amount > it.budget ? '#ef4444' : '' }">{{ fmt(it.amount) }}</td>
                      <td class="text-right text-zinc-400">{{ it.budget > 0 ? fmt(it.budget) : '無預算' }}</td>
                      <td class="text-right text-zinc-500">{{ fmtPct(it.amount, curInvestTotal) }}</td>
                      <td class="py-1.5 px-2">
                        <div v-if="it.amount > 0 || it.budget > 0" class="relative h-4">
                          <!-- 100% 基準虛線（百分比模式且有預算才顯示） -->
                          <div v-if="investVisMode === 'percent' && it.budget > 0"
                               class="absolute inset-y-0 border-r border-dashed border-zinc-400 dark:border-zinc-500"
                               style="width: 83.33%; left: 0; pointer-events: none;">
                          </div>
                          <!-- 預算灰底柱 -->
                          <div v-if="showBudgetInInvest && it.budget > 0"
                               class="absolute inset-y-0 left-0 rounded bg-zinc-300 dark:bg-zinc-600"
                               :style="{ width: invBarWidth(it, 'budget') + '%', minWidth: '2px' }">
                          </div>
                          <!-- 實際彩色柱 -->
                          <div class="absolute inset-y-0 left-0 rounded"
                               :style="{
                                 background: it.color,
                                 opacity: showBudgetInInvest && it.budget > 0 ? 0.75 : 1,
                                 width: invBarWidth(it, 'actual') + '%',
                                 minWidth: '2px',
                               }">
                          </div>
                          <!-- 數值標籤 -->
                          <div class="absolute inset-y-0 flex items-center text-[10px] font-semibold tabular-nums whitespace-nowrap pointer-events-none"
                               :style="{
                                 left: 'calc(' + Math.max(invBarWidth(it, 'actual'), showBudgetInInvest ? invBarWidth(it, 'budget') : 0) + '% + 4px)',
                                 color: showBudgetInInvest && it.budget > 0 && it.amount > it.budget ? '#ef4444' : '#52525b',
                               }">
                            {{ investVisMode === 'percent'
                               ? (it.budget > 0 ? +(it.amount / it.budget * 100).toFixed(1) + '%' : '—')
                               : fmtW(it.amount) }}
                          </div>
                        </div>
                      </td>
                    </tr>
                    <!-- 股票展開：個別買進交易 -->
                    <tr
                      v-for="(txn, ti) in (it.sno === 101 && expandedInvest.has(101) ? investStockTxns(selectedYear) : [])"
                      :key="'txn-' + ti"
                      class="bg-zinc-50 dark:bg-zinc-800/30"
                    >
                      <td></td>
                      <td class="pl-6 text-zinc-500 text-[12px]">└ {{ txn.note || '（無註記）' }}</td>
                      <td class="text-right text-zinc-500 text-[12px]">{{ fmt(txn.amount) }}</td>
                      <td></td>
                      <td class="text-right text-zinc-400 text-[11px]">{{ txn.date }}</td>
                      <td></td>
                    </tr>
                  </template>
                </tbody>
                <tbody>
                  <tr class="bg-zinc-800 text-white font-bold dark:bg-zinc-700">
                    <td></td>
                    <td class="py-1.5 px-2">總計</td>
                    <td class="text-right pr-2">{{ fmt(curInvestTotal) }}</td>
                    <td class="text-right pr-2 text-zinc-300">{{ curInvestBudgetTotal ? fmt(curInvestBudgetTotal) : '—' }}</td>
                    <td class="text-right pr-2">100%</td>
                    <td></td>
                  </tr>
                </tbody>
              </table>
            </template>
          </div>
        </section>
        </div>

        <!-- 實際收入明細 -->
        <section class="panel">
          <span class="panel-title">💵 實際收入明細</span>
          <div class="pt-1">
            <!-- toolbar：顯示預算 -->
            <div class="flex items-center justify-end mb-2 text-[12px]">
              <label class="inline-flex items-center gap-1.5 text-zinc-600 dark:text-zinc-300 cursor-pointer select-none">
                <input type="checkbox" v-model="showBudgetInIncome" class="accent-zinc-500" />
                顯示預算
              </label>
            </div>
            <div v-if="!curIncomeItems.length" class="text-[13px] text-zinc-500 py-3 text-center">
              {{ selectedYear }} 年無收入資料
            </div>
            <table v-else class="w-full text-[13px]">
              <thead class="text-zinc-600 dark:text-zinc-300">
                <tr class="border-b border-zinc-200 dark:border-zinc-700 text-left">
                  <th class="w-[160px] py-1">來源</th>
                  <th class="w-[110px] text-right">金額</th>
                  <th class="w-[110px] text-right text-zinc-400">預算</th>
                  <th class="w-[60px] text-right">佔比</th>
                  <th>視覺化</th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="item in curIncomeItems" :key="item.sno"
                  class="border-b border-zinc-100 dark:border-zinc-800"
                >
                  <td class="py-1 font-medium">{{ item.name }}</td>
                  <td class="text-right">{{ fmt(item.amount) }}</td>
                  <td class="text-right text-zinc-400">
                    {{ (curIncomeSubBudget.get(item.sno) ?? 0) > 0 ? fmt(curIncomeSubBudget.get(item.sno)) : '—' }}
                  </td>
                  <td class="text-right text-zinc-500">{{ fmtPct(item.amount, curIncomeTotal) }}</td>
                  <td class="py-1.5 px-2">
                    <div class="relative h-4">
                      <!-- 預算灰底柱 -->
                      <div v-if="showBudgetInIncome && (curIncomeSubBudget.get(item.sno) ?? 0) > 0"
                           class="absolute inset-y-0 left-0 rounded bg-zinc-300 dark:bg-zinc-600"
                           :style="{
                             width: ((curIncomeSubBudget.get(item.sno) ?? 0) / (showBudgetInIncome ? curIncomeMaxWithBudget : curIncomeMaxAmt) * 100) + '%',
                             minWidth: '2px',
                           }">
                      </div>
                      <!-- 實際彩色柱 -->
                      <div class="absolute inset-y-0 left-0 rounded"
                           :style="{
                             background: '#10b981',
                             opacity: showBudgetInIncome ? 0.75 : 1,
                             width: (item.amount / (showBudgetInIncome ? curIncomeMaxWithBudget : curIncomeMaxAmt) * 100) + '%',
                             minWidth: '2px',
                           }">
                      </div>
                      <!-- 金額標籤 -->
                      <div class="absolute inset-y-0 flex items-center text-[10px] font-semibold tabular-nums whitespace-nowrap pointer-events-none text-zinc-600"
                           :style="{
                             left: 'calc(' + Math.max(
                               item.amount / (showBudgetInIncome ? curIncomeMaxWithBudget : curIncomeMaxAmt) * 100,
                               showBudgetInIncome ? ((curIncomeSubBudget.get(item.sno) ?? 0) / curIncomeMaxWithBudget * 100) : 0
                             ) + '% + 4px)',
                           }">
                        {{ fmtW(item.amount) }}
                      </div>
                    </div>
                  </td>
                </tr>
                <tr class="bg-emerald-700 text-white font-bold">
                  <td class="py-1.5 px-2">總收入</td>
                  <td class="text-right pr-2">{{ fmt(curIncomeTotal) }}</td>
                  <td class="text-right pr-2 text-emerald-100">{{ curIncomeBudgetTotal ? fmt(curIncomeBudgetTotal) : '—' }}</td>
                  <td class="text-right pr-2">100%</td>
                  <td></td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>

        <!-- #4 Top 10 子項排行 -->
        <section class="panel">
          <span class="panel-title">🏆 {{ selectedYear }} 年實際支出 Top 10 子項</span>
          <div class="pt-1">
            <div v-if="!curTopItems.length" class="text-[13px] text-zinc-500 py-3 text-center">
              無支出資料
            </div>
            <table v-else class="w-full text-[13px]">
              <thead class="text-zinc-600 dark:text-zinc-300">
                <tr class="border-b border-zinc-200 dark:border-zinc-700 text-left">
                  <th class="w-[30px] py-1">#</th>
                  <th class="w-[100px]">大類</th>
                  <th class="w-[140px]">子項</th>
                  <th class="w-[110px] text-right">金額</th>
                  <th>視覺化</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(it, idx) in curTopItems" :key="it.key"
                    class="border-b border-zinc-100 dark:border-zinc-800">
                  <td class="text-zinc-400">{{ idx + 1 }}</td>
                  <td>
                    <span class="inline-block w-2 h-2 rounded-full mr-1.5" :style="{ background: it.color }"></span>
                    <span class="text-[12px] text-zinc-600 dark:text-zinc-300">{{ it.className }}</span>
                  </td>
                  <td class="font-medium">{{ it.subjectName }}</td>
                  <td class="text-right tabular-nums">{{ fmt(it.amount) }}</td>
                  <td class="py-1.5 px-2">
                    <div class="h-3 rounded"
                         :style="{
                           background: it.color,
                           width: (it.amount / curTopMax * 100) + '%',
                           minWidth: '2px',
                         }"></div>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>

      </div>

      <!-- ====================================================== -->
      <!-- Tab B：歷年趨勢                                           -->
      <!-- ====================================================== -->
      <div v-else class="space-y-3">

        <!-- LV2-1: 歷年收入 / 支出 / 結餘 -->
        <div class="space-y-3">
          <div class="text-[13px] font-semibold text-zinc-600 dark:text-zinc-300 px-1 border-l-4 border-purple-500 pl-3">
            📈 歷年 淨收益 與 淨投資 <span class="text-[11px] text-zinc-400 ml-1">跨年比較</span>
          </div>

          <div class="grid grid-cols-1 lg:grid-cols-2 gap-3">
            <section class="panel">
              <span class="panel-title">歷年 實際收入 / 實際支出 / 淨收益</span>
              <div class="h-[260px] mt-2"><canvas ref="trendCanvas"></canvas></div>
            </section>
            <section class="panel">
              <span class="panel-title">歷年 淨投資　資金回收 / 資金轉移 / 淨投資</span>
              <div class="h-[260px] mt-2"><canvas ref="savingsCanvas"></canvas></div>
            </section>
          </div>

          <section class="panel">
            <span class="panel-title">實際收入結構（歷年）</span>
            <div class="h-[280px] mt-2"><canvas ref="incStructCanvas"></canvas></div>
          </section>

          <section class="panel">
            <span class="panel-title">📉 現金使用 趨勢</span>
            <div class="h-[280px] mt-2"><canvas ref="classTrendCanvas"></canvas></div>
          </section>
        </div>

        <!-- LV2-3: 年度數據比對表 -->
        <div class="space-y-3">
          <div class="text-[13px] font-semibold text-zinc-600 dark:text-zinc-300 px-1 border-l-4 border-emerald-500 pl-3">
            📋 年度數據比對表 <span class="text-[11px] text-zinc-400 ml-1">{{ histYears[0] }}–{{ histYears.at(-1) }} 一覽</span>
          </div>

          <section class="panel">
            <div class="overflow-x-auto mt-2">
              <table class="text-[12px] table-fixed">
                <colgroup>
                  <col style="width:110px" />
                  <col v-for="y in histYears" :key="y" style="width:72px" />
                </colgroup>
                <thead class="text-[11px] text-zinc-500 bg-zinc-50 dark:bg-zinc-800/30">
                  <tr>
                    <th class="text-left py-2 px-3 font-medium">指標</th>
                    <th v-for="y in histYears" :key="y"
                        class="text-right py-2 px-2 font-medium tabular-nums"
                        :class="y === CURRENT_YEAR_STR ? 'bg-blue-50 dark:bg-blue-900/20 text-blue-700 dark:text-blue-300' : ''">
                      {{ y }}
                    </th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="row in overviewRows" :key="row.label"
                      :class="['border-t border-zinc-100 dark:border-zinc-800', row.bg]">
                    <td class="py-1 px-3 text-[11px]"
                        :class="[
                          row.bold ? 'font-semibold text-zinc-700 dark:text-zinc-200' : 'text-zinc-500',
                          row.indent ? 'pl-5 text-zinc-400 dark:text-zinc-500' : '',
                        ]">
                      {{ row.label }}
                      <span v-if="row.formula"
                            class="block font-normal text-zinc-400 dark:text-zinc-500 text-[10px] leading-tight">
                        {{ row.formula }}
                      </span>
                    </td>
                    <td v-for="(y, i) in histYears" :key="y"
                        class="py-1 px-2 text-right tabular-nums"
                        :class="[
                          row.bold ? 'font-bold' : (row.indent ? 'text-[11px] opacity-75' : ''),
                          y === CURRENT_YEAR_STR ? 'bg-blue-50 dark:bg-blue-900/20' : '',
                        ]"
                        :style="{ color: row.color }">
                      {{ row.fn(i) }}
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </section>
        </div>
      </div>
    </template>
  </div>
</template>
