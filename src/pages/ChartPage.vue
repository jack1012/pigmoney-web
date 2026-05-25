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
const expandedAssetCat = ref(new Set())
function toggleAssetCat(key) {
  const s = new Set(expandedAssetCat.value)
  s.has(key) ? s.delete(key) : s.add(key)
  expandedAssetCat.value = s
}

// ============== 常數 ==============
// 對應 store.classBuckets 的 4 個桶位（label 對齊 BudgetPage 的 BUCKET_SECTIONS）
const EXPENSE_GROUPS = [
  { key: 'life',  name: '生活類', color: '#10b981', note: '彈性可調' },
  { key: 'fixed', name: '固定類', color: '#3b82f6', note: '剛性' },
  { key: 'want',  name: '想要',   color: '#f59e0b', note: '一次性' },
  { key: 'save',  name: '投資',   color: '#8b5cf6', note: '結餘去向' },
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

// 每年「信用卡支出」（mode='信用卡支出'）總額 — 視為投資支出
const yearInvestSpend = computed(() => {
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
    if ((cat === '現金' || cat === '投資') && s.date === dates.cashDate) {
      if (cat === '現金') obj.cash += s.amount
      else obj.invest += s.amount
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
function yearExpense(y) {
  if (!y) return 0
  const m = yearCnoSpend.value.get(y)
  if (!m) return 0
  let total = 0
  for (const [cno, v] of m) {
    if (cno !== incomeCno.value) total += v
  }
  return total
}
function yearInvest(y) {
  if (!y) return 0
  return yearInvestSpend.value.get(y) ?? 0
}

function yearTotalAsset(y) {
  const a = yearAssets.value.get(y)
  if (!a) return 0
  return a.cash + a.invest + a.realEstate - a.debt
}

// 當年 KPI
// exp = 一般支出（總支出 - 投資 mode='信用卡支出'）；invest 單獨拉出
const curYearData = computed(() => {
  const y = selectedYear.value
  if (!y) return null
  const idx = allYears.value.indexOf(y)
  const prev = idx > 0 ? allYears.value[idx - 1] : null
  const inc = yearIncome(y)
  const expTotal = yearExpense(y)
  const invest = yearInvest(y)
  const exp = expTotal - invest          // 一般支出（不含投資）
  const surplus = inc - expTotal         // 結餘公式不變（exp + invest = 原 expTotal）
  const totalAsset = yearTotalAsset(y)
  const prevInc = prev ? yearIncome(prev) : null
  const prevExpTotal = prev ? yearExpense(prev) : null
  const prevInvest = prev ? yearInvest(prev) : null
  const prevExp = prevExpTotal != null ? prevExpTotal - (prevInvest ?? 0) : null
  const prevAsset = prev ? yearTotalAsset(prev) : null
  return {
    inc, exp, invest, surplus, totalAsset,
    incChange:    prevInc ? ((inc - prevInc) / prevInc * 100).toFixed(1) : null,
    expChange:    prevExp ? ((exp - prevExp) / prevExp * 100).toFixed(1) : null,
    investChange: prevInvest ? ((invest - prevInvest) / prevInvest * 100).toFixed(1) : null,
    savRate: inc ? (surplus / inc * 100).toFixed(1) : '0',
    assetGrowth: prevAsset ? totalAsset - prevAsset : null,
  }
})

// 當年支出結構：按 bucket 分組（含「未分類」fallback）
const FOUR_BUCKET_KEYS = new Set(['life', 'fixed', 'want', 'save'])
const curExpenseGroups = computed(() => {
  const y = selectedYear.value
  if (!y) return []
  const cnoSpend = yearCnoSpend.value.get(y) ?? new Map()
  const groups = EXPENSE_GROUPS.map(g => {
    // 順序依 store.classes 的 order_id（從 DB 已排好），不重排
    const cats = store.classes
      .filter(c => store.classBuckets[c.cno] === g.key)
      .map(c => ({ cno: c.cno, name: c.name, amount: cnoSpend.get(c.cno) ?? 0 }))
    const total = cats.reduce((s, c) => s + c.amount, 0)
    return { ...g, cats, total }
  })
  // 沒被歸入 4 桶位、也不是 income 的 class → 未分類
  const unbucketed = store.classes
    .filter(c => {
      const b = store.classBuckets[c.cno]
      return b !== 'income' && !FOUR_BUCKET_KEYS.has(b)
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
    if (a.category === '現金' || a.category === '投資') v = cashByAno.get(a.ano) ?? 0
    else if (a.category === '動產/不動產' || a.category === '負債') v = yearEndByAno.get(a.ano) ?? 0
    // 含 0 元也顯示（依 store.assetAccounts 的順序）
    const item = { ano: a.ano, name: a.name, amount: v, note: a.note }
    if (a.category === '現金') result.cash.push(item)
    else if (a.category === '投資') result.invest.push(item)
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
        { label: '收入', data: d.map(x => x.inc), backgroundColor: '#10b981', borderRadius: 4 },
        { label: '支出', data: d.map(x => x.exp), backgroundColor: '#ef4444', borderRadius: 4 },
        { label: '結餘', data: d.map(x => x.sur), type: 'line',
          borderColor: '#f59e0b', backgroundColor: '#f59e0b', tension: 0.3, fill: false, pointRadius: 4 },
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
  if (savingsChart) { savingsChart.destroy(); savingsChart = null }
  if (!savingsCanvas.value) return
  savingsChart = new Chart(savingsCanvas.value, {
    type: 'line',
    data: {
      labels: histYears.value,
      datasets: [{
        label: '儲蓄率 (%)',
        data: histYearData.value.map(x => x.rate),
        borderColor: '#f59e0b',
        backgroundColor: 'rgba(245,158,11,0.15)',
        tension: 0.3, fill: true, pointRadius: 5, pointBackgroundColor: '#f59e0b',
      }],
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      scales: { y: { min: 0, max: 100, ticks: { callback: v => v + '%' } } },
      plugins: {
        legend: { labels: { boxWidth: 12, font: { size: 11 } } },
        tooltip: { callbacks: { label: c => '儲蓄率: ' + c.raw.toFixed(1) + '%' } },
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
const overviewRows = computed(() => {
  const yd = histYearData.value
  return [
    { label: '總收入', color: '#10b981', bold: true, fn: i => fmtTw1(yd[i].inc) },
    { label: '　薪資',     color: '#10b981', indent: true, fn: i => fmtTw1(incomeAt(i, 'salary')) },
    { label: '　投資獲利', color: '#10b981', indent: true, fn: i => fmtTw1(incomeAt(i, 'invest')) },
    { label: '　其他',     color: '#10b981', indent: true, fn: i => fmtTw1(incomeAt(i, 'other')) },
    { label: '總支出', color: '#ef4444', bold: true, fn: i => fmtTw1(yd[i].exp) },
    { label: '　生活類', color: '#10b981', indent: true, fn: i => fmtTw1(bucketExpenseAt(i, 'life')) },
    { label: '　固定類', color: '#3b82f6', indent: true, fn: i => fmtTw1(bucketExpenseAt(i, 'fixed')) },
    { label: '　想要',   color: '#f59e0b', indent: true, fn: i => fmtTw1(bucketExpenseAt(i, 'want')) },
    { label: '　投資',   color: '#8b5cf6', indent: true, fn: i => fmtTw1(bucketExpenseAt(i, 'save')) },
    { label: '結餘',   color: '#f59e0b', bold: true, fn: i => fmtTw1(yd[i].sur) },
    { label: '儲蓄率', color: '#1f2937', fn: i => yd[i].rate.toFixed(1) + '%' },
  ]
})

function drawHistCharts() {
  drawTrend()
  drawSavings()
  drawIncStruct()
}

// activeTab / 資料變動時重繪
watch(
  [activeTab, histYears, histYearData, histIncomeDatasets],
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
  classTrendChart?.destroy()
  budgetChart?.destroy()
  bucketDetailChart?.destroy()
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
  if (!y) return { life: 0, fixed: 0, want: 0, save: 0 }
  // 先依 cno 分組當年的所有 items
  const byCno = new Map()
  for (const it of store.allBudgetItems) {
    if (it.year !== y) continue
    if (!byCno.has(it.cno)) byCno.set(it.cno, [])
    byCno.get(it.cno).push(it)
  }
  const out = { life: 0, fixed: 0, want: 0, save: 0 }
  for (const [cno, items] of byCno) {
    const bkt = store.classBuckets[cno]
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
const expenseVisMode = ref('amount')   // 'amount' | 'percent'

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

// 當年「實際支出明細」表所有 class 的預算總額
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
const bucketTab = ref('life')   // 'life' | 'fixed' | 'want' | 'save'
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

// 月別投資（mode='信用卡支出'）
const yearMonthInvest = computed(() => {
  if (!store.db) return new Map()
  const rows = rowsToObjects(store.db.exec(
    `SELECT strftime('%Y', date) AS year, CAST(strftime('%m', date) AS INT) AS mo, SUM(spend) AS total
     FROM money WHERE uno=1 AND mode='信用卡支出'
     GROUP BY year, mo`
  ))
  const m = new Map()
  for (const r of rows) {
    if (!m.has(r.year)) m.set(r.year, new Map())
    m.get(r.year).set(r.mo, Number(r.total ?? 0))
  }
  return m
})

const curMonthlySeries = computed(() => {
  const y = selectedYear.value
  const ym = yearMonthCnoSpend.value.get(y)
  const yi = yearMonthInvest.value.get(y) ?? new Map()
  const inc = Array(12).fill(0)
  const expTotal = Array(12).fill(0)
  const invest = Array(12).fill(0)
  if (ym) {
    for (const [mo, byCno] of ym) {
      let i = 0, e = 0
      for (const [cno, v] of byCno) {
        if (cno === incomeCno.value) i += v
        else e += v
      }
      inc[mo - 1] = i
      expTotal[mo - 1] = e
    }
  }
  for (const [mo, v] of yi) invest[mo - 1] = v
  // exp = 一般支出（總支出 − 投資）
  const exp = expTotal.map((v, idx) => v - invest[idx])
  const sur = inc.map((v, idx) => v - expTotal[idx])
  return { inc, exp, invest, sur }
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
const bucketDetailCanvas = ref(null)
const monthCanvas = ref(null)
const classTrendCanvas = ref(null)
let budgetChart = null
let bucketDetailChart = null
let monthChart = null
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

function drawMonth() {
  if (monthChart) { monthChart.destroy(); monthChart = null }
  if (!monthCanvas.value) return
  const s = curMonthlySeries.value
  monthChart = new Chart(monthCanvas.value, {
    type: 'bar',
    data: {
      labels: Array.from({ length: 12 }, (_, i) => (i + 1) + '月'),
      datasets: [
        { label: '結餘', data: s.sur, type: 'line', borderColor: '#f59e0b',
          backgroundColor: '#f59e0b', tension: 0.3, pointRadius: 4, fill: false,
          borderWidth: 2.5, order: 0 },
        { label: '收入',   data: s.inc,    backgroundColor: '#10b981', borderRadius: 3, order: 2 },
        { label: '一般支出', data: s.exp,    backgroundColor: '#ef4444', borderRadius: 3, order: 2 },
        { label: '投資',   data: s.invest, backgroundColor: '#8b5cf6', borderRadius: 3, order: 2 },
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
  [activeTab, selectedYear, curMonthlySeries, monthCanvas,
   curBucketCompare, budgetCanvas, curBucketDetail, bucketDetailCanvas, bucketTab],
  () => {
    if (activeTab.value !== 'yearly') return
    nextTick(() => { drawMonth(); drawBudget(); drawBucketDetail() })
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

        <!-- KPI 四卡 -->
        <section v-if="curYearData" class="panel">
          <span class="panel-title">💰 收入 / 支出 / 投資 / 結餘</span>
          <div class="grid grid-cols-2 md:grid-cols-4 gap-2 pt-1">
            <div class="rounded p-3 border-l-4" style="border-color:#10b981;background:#10b9810f">
              <div class="text-[12px] text-zinc-500 dark:text-zinc-400">{{ selectedYear }} 年總收入</div>
              <div class="text-[20px] font-bold" style="color:#10b981">{{ fmtW(curYearData.inc) }}</div>
              <div class="text-[11px] text-zinc-400">
                {{ curYearData.incChange != null
                  ? (curYearData.incChange >= 0 ? '↑ ' : '↓ ') + Math.abs(curYearData.incChange) + '% (vs 上年)'
                  : '—' }}
              </div>
            </div>
            <div class="rounded p-3 border-l-4" style="border-color:#ef4444;background:#ef44440f">
              <div class="text-[12px] text-zinc-500 dark:text-zinc-400">{{ selectedYear }} 年一般支出</div>
              <div class="text-[20px] font-bold" style="color:#ef4444">{{ fmtW(curYearData.exp) }}</div>
              <div class="text-[11px] text-zinc-400">
                {{ curYearData.expChange != null
                  ? (curYearData.expChange >= 0 ? '↑ ' : '↓ ') + Math.abs(curYearData.expChange) + '% (vs 上年)'
                  : '—' }}
              </div>
            </div>
            <div class="rounded p-3 border-l-4" style="border-color:#8b5cf6;background:#8b5cf60f">
              <div class="text-[12px] text-zinc-500 dark:text-zinc-400">{{ selectedYear }} 年投資</div>
              <div class="text-[20px] font-bold" style="color:#8b5cf6">{{ fmtW(curYearData.invest) }}</div>
              <div class="text-[11px] text-zinc-400">
                {{ curYearData.investChange != null
                  ? (curYearData.investChange >= 0 ? '↑ ' : '↓ ') + Math.abs(curYearData.investChange) + '% (vs 上年)'
                  : '（信用卡支出）' }}
              </div>
            </div>
            <div class="rounded p-3 border-l-4" style="border-color:#f59e0b;background:#f59e0b0f">
              <div class="text-[12px] text-zinc-500 dark:text-zinc-400">{{ selectedYear }} 年結餘</div>
              <div class="text-[20px] font-bold" style="color:#f59e0b">{{ fmtW(curYearData.surplus) }}</div>
              <div class="text-[11px] text-zinc-400">儲蓄率 {{ curYearData.savRate }}%</div>
            </div>
          </div>
        </section>

        <!-- #1 預算對照 + #2 月別趨勢 並列 -->
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

          <section class="panel">
            <span class="panel-title">📅 {{ selectedYear }} 年月別收支</span>
            <div class="h-[240px] mt-2"><canvas ref="monthCanvas"></canvas></div>
            <!-- 月別數值表（3 行：收入 / 支出 / 結餘，每月一欄，對齊圖表繪圖區） -->
            <div class="mt-2 pl-10 pr-2 text-[10px] leading-tight">
              <div v-for="row in [
                { label: '收入',   color: '#10b981', data: curMonthlySeries.inc },
                { label: '一般支出', color: '#ef4444', data: curMonthlySeries.exp },
                { label: '投資',   color: '#8b5cf6', data: curMonthlySeries.invest },
                { label: '結餘',   color: '#f59e0b', data: curMonthlySeries.sur, bold: true },
              ]" :key="row.label"
                 class="grid items-center border-b border-zinc-100 dark:border-zinc-800 last:border-b-0"
                 :style="{ gridTemplateColumns: '38px repeat(12, minmax(0,1fr))' }">
                <div class="text-zinc-500 dark:text-zinc-400 font-medium"
                     :style="{ color: row.color }">{{ row.label }}</div>
                <div v-for="(v, i) in row.data" :key="i"
                     class="text-center tabular-nums py-0.5"
                     :class="[
                       row.bold ? 'font-semibold' : '',
                       v === 0 ? 'text-zinc-300 dark:text-zinc-600'
                         : (row.label === '結餘' && v < 0 ? 'text-red-500' : ''),
                     ]"
                     :style="row.bold ? { color: row.color } : {}">
                  {{ v === 0 ? '—' : fmtTw1(v) }}
                </div>
              </div>
            </div>
          </section>
        </div>

        <!-- #1b 各類細部預算 vs 實際（4 tab 切換桶位） -->
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
          <!-- 達成率小條（同一行，N 卡平均分配，對齊上方圖表繪圖區） -->
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

        <!-- 實際支出明細 -->
        <section class="panel">
          <span class="panel-title">🧾 實際支出明細</span>
          <div class="pt-1">
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
                               left: 'calc(' + Math.max(expBarWidth(cat, 'actual'), expBarWidth(cat, 'budget')) + '% + 4px)',
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
          <span class="panel-title">🏆 {{ selectedYear }} 年支出 Top 10 子項</span>
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
            📈 歷年收入 / 支出 / 結餘 <span class="text-[11px] text-zinc-400 ml-1">跨年比較</span>
          </div>

          <div class="grid grid-cols-1 lg:grid-cols-2 gap-3">
            <section class="panel">
              <span class="panel-title">歷年收入 / 支出 / 結餘</span>
              <div class="h-[260px] mt-2"><canvas ref="trendCanvas"></canvas></div>
            </section>
            <section class="panel">
              <span class="panel-title">儲蓄率變化</span>
              <div class="h-[260px] mt-2"><canvas ref="savingsCanvas"></canvas></div>
            </section>
          </div>

          <section class="panel">
            <span class="panel-title">收入結構（歷年）</span>
            <div class="h-[280px] mt-2"><canvas ref="incStructCanvas"></canvas></div>
          </section>

          <section class="panel">
            <span class="panel-title">📉 各大類年際趨勢</span>
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
