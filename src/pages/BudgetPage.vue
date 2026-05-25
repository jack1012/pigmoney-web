<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { useMoneyStore } from '../stores/money.js'

const store = useMoneyStore()

// ── 檢視模式 ──────────────────────────────────────
const viewMode = ref('edit')  // 'edit' | 'history'
watch(viewMode, (v) => { if (v === 'history') store.loadAllBudgets() })

// ── 年份 ──────────────────────────────────────────
const yearOptions = computed(() => {
  const now = new Date().getFullYear()
  return [now + 1, now, now - 1, now - 2, now - 3, now - 4, now - 5]
})
const year = ref(store.budgetYear)
watch(year, (v) => store.loadBudget(v))
onMounted(() => { if (store.db) store.loadBudget(year.value) })
watch(() => store.db, (v) => { if (v) store.loadBudget(year.value) })

// ── 年度 meta ─────────────────────────────────────
const metaTotal  = ref('')
const metaNote   = ref('')
const ratioLife  = ref(30)
const ratioFixed = ref(20)
const ratioWant  = ref(10)
const ratioSave  = ref(40)

watch(() => store.budgetYearMeta, (m) => {
  metaTotal.value  = m?.total  ?? ''
  metaNote.value   = m?.note   ?? ''
  ratioLife.value  = m ? Math.round((m.ratio_life  ?? 0.30) * 100) : 30
  ratioFixed.value = m ? Math.round((m.ratio_fixed ?? 0.20) * 100) : 20
  ratioWant.value  = m ? Math.round((m.ratio_want  ?? 0.10) * 100) : 10
  ratioSave.value  = m ? Math.round((m.ratio_save  ?? 0.40) * 100) : 40
}, { immediate: true })

const ratioSum = computed(() =>
  Number(ratioLife.value) + Number(ratioFixed.value) + Number(ratioWant.value) + Number(ratioSave.value)
)

// 各桶位金額（萬），由比例 × 總收入計算
const targetAmountsW = computed(() => ({
  life:  total.value ? Math.round(total.value * ratioLife.value  / 100 / 10000) : '',
  fixed: total.value ? Math.round(total.value * ratioFixed.value / 100 / 10000) : '',
  want:  total.value ? Math.round(total.value * ratioWant.value  / 100 / 10000) : '',
  save:  total.value ? Math.round(total.value * ratioSave.value  / 100 / 10000) : '',
}))
// 直接輸入金額（萬）→ 反推並更新比例
const RATIO_REFS = { life: ratioLife, fixed: ratioFixed, want: ratioWant, save: ratioSave }
function setBucketFromAmountW(key, val) {
  if (!total.value || val === '' || val == null) return
  RATIO_REFS[key].value = Math.round(Number(val) * 10000 / total.value * 100)
  saveMeta()
}
async function saveMeta() {
  await store.upsertBudgetYear({
    year: year.value,
    total: metaTotal.value === '' ? null : Number(metaTotal.value),
    note: metaNote.value,
    ratio_life:  (ratioLife.value  || 0) / 100,
    ratio_fixed: (ratioFixed.value || 0) / 100,
    ratio_want:  (ratioWant.value  || 0) / 100,
    ratio_save:  (ratioSave.value  || 0) / 100,
  })
}

// ── 收入預估表 ────────────────────────────────────
const incomeCno = computed(() =>
  store.classes.find((c) => store.classBuckets[c.cno] === 'income' || c.name === '收入')?.cno ?? null
)
const incomeSubjects = computed(() =>
  incomeCno.value != null ? store.subjects.filter((s) => s.cno === incomeCno.value) : []
)

// ── 預算 lookup ───────────────────────────────────
const yearBudgetMap = computed(() => {
  const m = new Map()
  for (const it of store.budgetItems) {
    if (it.month === 0) m.set(`${it.cno}-${it.sno}`, it.amount)
  }
  return m
})
function getYearBudget(cno, sno = 0) {
  return yearBudgetMap.value.get(`${cno}-${sno}`) ?? null
}
function classBudgetSum(cno) {
  const direct = getYearBudget(cno, 0)
  if (direct != null) return direct
  return store.subjects.filter((s) => s.cno === cno)
    .reduce((acc, s) => acc + (getYearBudget(cno, s.sno) ?? 0), 0)
}
// 類別層級「設定預算」：sno=0 那筆 input
function classSetting(cno)  { return getYearBudget(cno, 0) ?? 0 }
// 類別層級「細項預算」：所有子項目加總
function classDetailSum(cno) {
  return store.subjects.filter((s) => s.cno === cno)
    .reduce((acc, s) => acc + (getYearBudget(cno, s.sno) ?? 0), 0)
}
// 設定 vs 細項 差額（設定 − 細項，正數表示設定還有空間，負數表示細項超出設定，提醒去調）
function settingMinusDetail(cno) {
  const set = classSetting(cno)
  const det = classDetailSum(cno)
  if (!set && !det) return null
  return set - det
}
function settingVsDetailClass(diff) {
  if (diff == null) return 'text-zinc-300 dark:text-zinc-600'
  if (diff < 0) return 'text-red-600 dark:text-red-400 font-semibold'  // 細項超支
  if (diff === 0) return 'text-emerald-600 dark:text-emerald-400'      // 剛好
  return 'text-zinc-500'                                                // 還有空間
}

// 註記讀寫
function getNote(cno, sno = 0) {
  return store.budgetItems.find(b => b.year === year.value && b.cno === cno && b.sno === sno && b.month === 0)?.note ?? ''
}
const noteEditing = ref({})
function getNoteEditValue(cno, sno = 0) {
  const k = `n-${cno}-${sno}`
  return k in noteEditing.value ? noteEditing.value[k] : getNote(cno, sno)
}
function onNoteInput(cno, sno, ev) { noteEditing.value[`n-${cno}-${sno}`] = ev.target.value }
// textarea 高度依文字行數自動配（最少 1 行）
function noteRows(text) {
  if (!text) return 1
  return Math.max(1, String(text).split('\n').length)
}
async function commitNote(cno, sno = 0) {
  const k = `n-${cno}-${sno}`
  if (!(k in noteEditing.value)) return
  await store.upsertBudgetItemNote({
    year: year.value, cno, sno, month: 0, note: noteEditing.value[k] || null,
  })
  delete noteEditing.value[k]
}

// ── inline 編輯 ───────────────────────────────────
const editing = ref({})
function getEditValue(cno, sno = 0) {
  const k = `${cno}-${sno}`
  if (k in editing.value) return editing.value[k]
  const v = getYearBudget(cno, sno)
  return v == null ? '' : String(v)
}
function evalFormula(expr) {
  if (!expr) return { ok: true, value: null }
  const s = String(expr).trim()
  if (s === '') return { ok: true, value: null }
  if (!/^[0-9+\-*/().\s,]+$/.test(s)) return { ok: false, value: null }
  try {
    // eslint-disable-next-line no-new-func
    const val = Function('"use strict"; return (' + s.replace(/,/g, '') + ')')()
    return (typeof val === 'number' && isFinite(val))
      ? { ok: true, value: Math.round(val) } : { ok: false, value: null }
  } catch { return { ok: false, value: null } }
}
async function commitEdit(cno, sno = 0) {
  const k = `${cno}-${sno}`
  if (!(k in editing.value)) return
  const raw = editing.value[k]
  const r = evalFormula(raw)
  if (!r.ok) { delete editing.value[k]; return }
  const isFormula = /[+\-*/()]/.test(String(raw).trim())
  await store.upsertBudgetItem({
    year: year.value, cno, sno, month: 0,
    amount: r.value,
    formula: isFormula ? String(raw).trim() : null,
  })
  delete editing.value[k]
}
function onInput(cno, sno, ev) { editing.value[`${cno}-${sno}`] = ev.target.value }

// 萬為單位的版本（收入預估專用）
function getEditValueW(cno, sno = 0) {
  const k = `${cno}-${sno}`
  if (k in editing.value) return editing.value[k]
  const v = getYearBudget(cno, sno)
  return v == null ? '' : String(v / 10000)
}
async function commitEditW(cno, sno = 0) {
  const k = `${cno}-${sno}`
  if (!(k in editing.value)) return
  const raw = editing.value[k]
  if (raw === '' || raw == null) { delete editing.value[k]; return }
  const num = Number(raw)
  if (isNaN(num)) { delete editing.value[k]; return }
  await store.upsertBudgetItem({
    year: year.value, cno, sno, month: 0,
    amount: Math.round(num * 10000),
    formula: null,
  })
  delete editing.value[k]
}

// ── KPI 計算 ──────────────────────────────────────
const total = computed(() => Number(metaTotal.value) || 0)

// 以萬為單位的雙向轉換（顯示用）
const metaTotalW = computed({
  get: () => metaTotal.value === '' || metaTotal.value == null ? '' : Number(metaTotal.value) / 10000,
  set: (v) => { metaTotal.value = (v === '' || v == null) ? '' : String(Math.round(Number(v) * 10000)) },
})

// 收入實際 from DB
const incomeActual = computed(() => store.actualIncome(String(year.value)))

// 收入預估 = budget_item 裡 income class 所有子項目加總
const incomeBudgeted = computed(() => {
  if (incomeCno.value == null) return 0
  return incomeSubjects.value.reduce((acc, s) => acc + (getYearBudget(incomeCno.value, s.sno) ?? 0), 0)
    || getYearBudget(incomeCno.value, 0) || 0
})

const SPEND_BUCKETS = ['life', 'fixed', 'want', 'save']
const targetAmounts = computed(() => ({
  life:  Math.round(total.value * (ratioLife.value  / 100)),
  fixed: Math.round(total.value * (ratioFixed.value / 100)),
  want:  Math.round(total.value * (ratioWant.value  / 100)),
  save:  Math.round(total.value * (ratioSave.value  / 100)),
}))

const budgetedByBucket = computed(() => {
  const sums = { life: 0, fixed: 0, want: 0, save: 0 }
  for (const c of store.classes) {
    const b = store.classBuckets[c.cno]
    if (b && b in sums) sums[b] += classBudgetSum(c.cno)
  }
  return sums
})
const actualByBucket = computed(() => {
  const sums = { life: 0, fixed: 0, want: 0, save: 0 }
  for (const c of store.classes) {
    const b = store.classBuckets[c.cno]
    if (b && b in sums) sums[b] += store.actualSpend(String(year.value), c.cno, 0)
  }
  return sums
})
const totalSpendActual = computed(() =>
  SPEND_BUCKETS.reduce((a, b) => a + actualByBucket.value[b], 0)
)
const savingsDerived = computed(() => incomeActual.value - totalSpendActual.value)

// bar 滿格 = 目標的 200%；超過 200% 才截斷
function barPct(val, target) {
  if (!target) return 0
  return Math.min(100, (val / target) * 50)   // 100% target → 50% bar
}
// 顯示用：真實百分比，不截斷
function barPctNum(val, target) {
  if (!target) return 0
  return Math.round(val / target * 100)
}

// ── 四大區塊分組 ──────────────────────────────────
const BUCKET_SECTIONS = [
  { key: 'life',  label: '生活類' },
  { key: 'fixed', label: '固定類' },
  { key: 'want',  label: '想要'   },
  { key: 'save',  label: '投資'   },
]
const classesByBucket = computed(() => {
  const map = {}
  for (const b of BUCKET_SECTIONS) map[b.key] = []
  for (const c of store.classes) {
    const b = store.classBuckets[c.cno]
    if (b && b in map) map[b].push(c)
  }
  return map
})

// 類別展開狀態（預設全部收合，僅顯示第一階層）
const expandedClasses = ref(new Set())
function toggleClass(cno) {
  if (expandedClasses.value.has(cno)) expandedClasses.value.delete(cno)
  else expandedClasses.value.add(cno)
  expandedClasses.value = new Set(expandedClasses.value)  // 觸發 reactivity
}
function expandAll() {
  expandedClasses.value = new Set(store.classes.map((c) => c.cno))
}
function collapseAll() {
  expandedClasses.value = new Set()
}
const allExpanded = computed(() =>
  store.classes.length > 0 && store.classes.every((c) => expandedClasses.value.has(c.cno))
)

// ── 歷史 ─────────────────────────────────────────
function median3yr(cno, sno = 0) { return store.historicalSpend(cno, sno, 3).median }
function actualThisYear(cno, sno = 0) { return store.actualSpend(String(year.value), cno, sno) }
function diffPct(budget, actual) {
  if (!budget) return null
  return ((actual - budget) / budget) * 100
}
function diffClass(pct) {
  if (pct == null) return 'text-zinc-300 dark:text-zinc-600'
  if (pct > 10) return 'text-red-600 dark:text-red-400 font-semibold'
  if (pct < -10) return 'text-blue-600 dark:text-blue-400'
  return 'text-zinc-500'
}

const yearTotalBudget = computed(() =>
  store.classes
    .filter((c) => store.classBuckets[c.cno] !== 'income')
    .reduce((acc, c) => acc + classBudgetSum(c.cno), 0)
)

// ── 一鍵初值 + 複製 ────────────────────────────────
async function autofillFromHistory() {
  const items = []
  for (const c of store.classes) {
    const subs = store.subjects.filter((s) => s.cno === c.cno)
    if (subs.length === 0) {
      if (getYearBudget(c.cno, 0) != null) continue
      const med = median3yr(c.cno, 0)
      if (med > 0) items.push({ year: year.value, cno: c.cno, sno: 0, amount: med })
    } else {
      for (const s of subs) {
        if (getYearBudget(c.cno, s.sno) != null) continue
        const med = median3yr(c.cno, s.sno)
        if (med > 0) items.push({ year: year.value, cno: c.cno, sno: s.sno, amount: med })
      }
    }
  }
  if (!items.length) { alert('沒有可填的項目'); return }
  await store.bulkUpsertBudgetItems(items)
  alert(`已自動填入 ${items.length} 個項目`)
}
async function copyLastYear() {
  if (!confirm(`從 ${year.value - 1} 複製預算到 ${year.value}？（覆蓋既有資料）`)) return
  await store.copyBudgetFromYear(year.value - 1, year.value)
}

function exportBudgetJson() {
  const data = store.exportBudgetYearJson(year.value)
  if (!data) { alert('尚未載入資料庫'); return }
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `budget_${year.value}.json`
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}

// ── 格式化 ────────────────────────────────────────
function fmt(n, unit = '') {
  if (n == null || isNaN(n)) return '—'
  if (unit === 'W') {
    const w = n / 10000
    return (w >= 100 ? w.toFixed(0) : w >= 10 ? w.toFixed(1) : w.toFixed(1)) + 'W'
  }
  return Number(n).toLocaleString()
}
function fmtDiff(actual, target) {
  if (!target || !actual) return null
  const diff = actual - target
  const pct = Math.round(diff / target * 100)
  return { diff, pct, over: diff > 0 }
}

// KPI 卡片設定（不含存款推算，存款推算單獨處理）
const CARDS = [
  { key: 'income', label: '總收入預算', sub: '怡亭 政德 投資利得…', border: '#805ad5', badgeBg: '#faf5ff', badgeText: '#44337a' },
  { key: 'life',   label: '生活類',    sub: '食 衣 生活 交通 教育 娛樂', border: '#38b2ac', badgeBg: '#e6fffa', badgeText: '#234e52' },
  { key: 'fixed',  label: '固定類',    sub: '特殊 稅金 房屋 車 保險',    border: '#667eea', badgeBg: '#ebf4ff', badgeText: '#1a365d' },
  { key: 'want',   label: '想要',      sub: '專案項目',                  border: '#ed8936', badgeBg: '#fffaf0', badgeText: '#744210' },
  { key: 'save',   label: '投資',      sub: '投資',                      border: '#48bb78', badgeBg: '#f0fff4', badgeText: '#1c4532' },
]

// 存款推算（預算面）：收入預估 − 實際已設預算合計
const budgetSavings = computed(() => incomeBudgeted.value - yearTotalBudget.value)
// ── 歷年 computeds ────────────────────────────────
const histYears = computed(() =>
  [...new Set([
    ...store.allBudgetYearMetas.map(m => m.year),
    ...store.allBudgetItems.map(i => i.year),
  ])].sort((a, b) => a - b)
)
const histYearTotals = computed(() => {
  const m = new Map()
  for (const meta of store.allBudgetYearMetas) m.set(meta.year, meta.total)
  return m
})
// Map: `${year}:${cno}` → items[]
const histItemMap = computed(() => {
  const m = new Map()
  for (const it of store.allBudgetItems) {
    const k = `${it.year}:${it.cno}`
    if (!m.has(k)) m.set(k, [])
    m.get(k).push(it)
  }
  return m
})
function histClassBudget(y, cno) {
  const items = histItemMap.value.get(`${y}:${cno}`) ?? []
  const direct = items.find(i => i.sno === 0)?.amount ?? null
  if (direct != null) return direct
  const detail = items.filter(i => i.sno !== 0).reduce((a, i) => a + (i.amount ?? 0), 0)
  return detail || null
}
function histBucketTotal(y, bucketKey) {
  return store.classes
    .filter(c => store.classBuckets[c.cno] === bucketKey)
    .reduce((a, c) => a + (histClassBudget(y, c.cno) ?? 0), 0) || null
}

// 設定列存款推算：總收入 − 四桶位目標金額加總（即時反映比例/總額變動）
const settingsSavings = computed(() =>
  total.value - Object.values(targetAmounts.value).reduce((a, b) => a + b, 0)
)
// 已設預算列的存款推算：設定預算（total）− 已設預算（incomeBudgeted）
const actualSavingsByBucket = computed(() => total.value - incomeBudgeted.value)
</script>

<template>
  <div class="p-4 h-full overflow-auto space-y-4 bg-zinc-50 dark:bg-zinc-950">

    <!-- ── 工具列 ── -->
    <div class="flex items-center gap-2 flex-wrap">
      <!-- 模式切換 -->
      <div class="flex rounded-lg overflow-hidden border border-zinc-300 dark:border-zinc-600 text-[13px]">
        <button @click="viewMode = 'edit'"
                :class="viewMode === 'edit'
                  ? 'bg-zinc-800 dark:bg-zinc-200 text-white dark:text-zinc-900 px-3 py-1'
                  : 'bg-white dark:bg-zinc-800 text-zinc-500 hover:text-zinc-800 dark:hover:text-zinc-200 px-3 py-1'">
          編輯
        </button>
        <button @click="viewMode = 'history'"
                :class="viewMode === 'history'
                  ? 'bg-zinc-800 dark:bg-zinc-200 text-white dark:text-zinc-900 px-3 py-1'
                  : 'bg-white dark:bg-zinc-800 text-zinc-500 hover:text-zinc-800 dark:hover:text-zinc-200 px-3 py-1'">
          歷年
        </button>
      </div>
      <!-- 年份（編輯模式才顯示） -->
      <template v-if="viewMode === 'edit'">
        <span class="text-[13px] text-zinc-500 ml-1">年份</span>
        <select v-model.number="year" class="field">
          <option v-for="y in yearOptions" :key="y" :value="y">{{ y }} 年</option>
        </select>
      </template>
      <button class="btn" @click="exportBudgetJson">📥 匯出 JSON</button>
    </div>

    <!-- ── 編輯模式 ── -->
    <template v-if="viewMode === 'edit'">

    <!-- ── 收入預估表 ── -->
    <div class="bg-white dark:bg-zinc-900 rounded-xl shadow-sm border border-zinc-200 dark:border-zinc-700 px-5 py-4">
      <div class="text-[13px] font-semibold text-zinc-500 mb-3">收入預估（萬）</div>
      <table class="text-[13px] border-collapse">
        <thead>
          <tr class="text-zinc-500 dark:text-zinc-400 border-b border-zinc-200 dark:border-zinc-700">
            <th class="text-center py-1.5 px-3 font-medium">項目</th>
            <th v-for="s in incomeSubjects" :key="s.sno"
                class="text-center py-1.5 px-3 font-medium">{{ s.name }}</th>
            <th class="text-center py-1.5 px-3 font-medium">合計</th>
          </tr>
        </thead>
        <tbody>
          <tr class="border-t border-zinc-100 dark:border-zinc-800">
            <td class="py-2 px-3 text-center text-zinc-400 text-[12px]">預估金額</td>
            <td v-for="s in incomeSubjects" :key="s.sno" class="py-2 px-3 text-center">
              <div class="inline-flex items-center gap-1">
                <input type="number"
                  :value="getEditValueW(incomeCno, s.sno)"
                  @input="onInput(incomeCno, s.sno, $event)"
                  @blur="commitEditW(incomeCno, s.sno)"
                  @keydown.enter="$event.target.blur()"
                  class="field w-20 text-center"
                  placeholder="—"
                />
                <span class="text-zinc-400 text-[12px]">萬</span>
              </div>
            </td>
            <td class="py-2 px-3 text-center font-semibold">
              {{ incomeBudgeted ? Math.round(incomeBudgeted / 10000) + '萬' : '—' }}
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- ── 年度設定 標頭 ── -->
    <div class="flex items-center gap-3">
      <span class="text-[13px] font-semibold text-zinc-500 shrink-0">{{ year }} 年度預算設定</span>
      <input v-model="metaNote" @blur="saveMeta" class="field flex-1 text-[12px]" placeholder="備註…" />
    </div>

    <!-- ── 4列 6欄：設定（3列）+ KPI（1列）統一對齊 ── -->
    <div class="grid grid-cols-6 gap-4">

      <!-- ── Row 1：欄位標頭 ── -->
      <div v-for="col in [
             { label: '預算收入設定', sub: '年度收入目標' },
             { label: '生活類',     sub: '食 衣 生活 交通…' },
             { label: '固定類',     sub: '特殊 稅 房 車 保險' },
             { label: '想要',       sub: '專案項目' },
             { label: '投資',       sub: '投資' },
             { label: '存款推算',   sub: '預算收入 − 預算支出' },
           ]" :key="col.label"
           class="bg-zinc-100 dark:bg-zinc-800 rounded-lg px-3 py-2 text-center">
        <div class="text-[12px] font-semibold text-zinc-600 dark:text-zinc-300">{{ col.label }}</div>
        <div class="text-[10px] text-zinc-400 mt-0.5">{{ col.sub }}</div>
      </div>

      <!-- ── Row 2：比例 ── -->
      <!-- 總收入欄位：顯示 ratioSum（四桶位合計） -->
      <div class="bg-white dark:bg-zinc-900 rounded-lg border border-zinc-200 dark:border-zinc-700
                  flex items-center justify-center gap-1.5 py-2">
        <span class="text-[10px] text-zinc-400 shrink-0">已分配</span>
        <span class="font-semibold text-[14px]"
              :class="ratioSum === 100 ? 'text-emerald-600 dark:text-emerald-400'
                      : ratioSum > 100 ? 'text-red-500' : 'text-zinc-700 dark:text-zinc-200'">
          {{ ratioSum }}%
        </span>
      </div>
      <!-- 四大桶位 比例 input -->
      <div v-for="key in ['life','fixed','want','save']" :key="'r-'+key"
           class="bg-white dark:bg-zinc-900 rounded-lg border border-zinc-200 dark:border-zinc-700
                  flex items-center justify-center gap-1 py-2">
        <input :value="RATIO_REFS[key].value"
               @input="RATIO_REFS[key].value = Number($event.target.value)"
               @blur="saveMeta" type="number"
               class="field w-14 text-center" />
        <span class="text-zinc-400 text-[12px]">%</span>
      </div>
      <!-- 存款推算 % = settingsSavings / total -->
      <div class="bg-white dark:bg-zinc-900 rounded-lg border border-zinc-200 dark:border-zinc-700
                  flex flex-col items-center justify-center py-2 gap-0.5">
        <span class="font-semibold text-[14px]"
              :class="settingsSavings < 0 ? 'text-red-500' : 'text-zinc-700 dark:text-zinc-200'">
          {{ total ? Math.round(settingsSavings / total * 100) + '%' : '—' }}
        </span>
        <span class="text-[10px] text-zinc-400">100% − 生活 − 固定 − 想要 − 投資</span>
      </div>

      <!-- ── Row 3：金額 ── -->
      <!-- 總收入 input -->
      <div class="bg-white dark:bg-zinc-900 rounded-lg border border-zinc-200 dark:border-zinc-700
                  flex items-center justify-center gap-1 py-2">
        <span class="text-[10px] text-zinc-400 shrink-0">設定預算</span>
        <input v-model.number="metaTotalW" @blur="saveMeta" type="number"
               class="field w-14 text-center font-bold" placeholder="400" />
        <span class="text-zinc-400 text-[12px]">萬</span>
      </div>
      <!-- 四大桶位 金額 -->
      <div v-for="key in ['life','fixed','want','save']" :key="'a-'+key"
           class="bg-white dark:bg-zinc-900 rounded-lg border border-zinc-200 dark:border-zinc-700
                  flex items-center justify-center gap-1 py-2">
        <input type="number"
               :value="targetAmountsW[key]"
               @blur="setBucketFromAmountW(key, $event.target.value)"
               @keydown.enter="$event.target.blur()"
               class="field w-16 text-center" placeholder="—" />
        <span class="text-zinc-400 text-[12px]">萬</span>
      </div>
      <!-- 存款推算（唯讀，即時反映設定） -->
      <div class="bg-white dark:bg-zinc-900 rounded-lg border border-zinc-200 dark:border-zinc-700
                  flex flex-col items-center justify-center py-2 gap-0.5">
        <span class="font-semibold text-[14px]"
              :class="settingsSavings < 0 ? 'text-red-500' : 'text-zinc-700 dark:text-zinc-200'">
          {{ total ? (settingsSavings >= 0 ? '+' : '') + Math.round(settingsSavings / 10000) + '萬' : '—' }}
        </span>
        <span class="text-[10px] text-zinc-400">設定預算 − 生活 − 固定 − 想要 − 投資</span>
      </div>

      <!-- ── Row 4：目前設定預算（唯讀） ── -->
      <div class="bg-zinc-50 dark:bg-zinc-800/50 rounded-lg border border-zinc-200 dark:border-zinc-700
                  flex items-center justify-center text-[13px] font-semibold py-2
                  text-zinc-700 dark:text-zinc-200 gap-1">
        <span class="text-[10px] text-zinc-400 font-normal shrink-0">已設預算</span>
        {{ incomeBudgeted ? Math.round(incomeBudgeted / 10000) + '萬' : '—' }}
      </div>
      <div v-for="key in ['life','fixed','want','save']" :key="'b-'+key"
           class="bg-zinc-50 dark:bg-zinc-800/50 rounded-lg border border-zinc-200 dark:border-zinc-700
                  flex items-center justify-center text-[13px] font-semibold py-2
                  text-zinc-700 dark:text-zinc-200">
        {{ budgetedByBucket[key] ? Math.round(budgetedByBucket[key] / 10000) + '萬' : '—' }}
      </div>
      <div class="bg-zinc-50 dark:bg-zinc-800/50 rounded-lg border border-zinc-200 dark:border-zinc-700
                  flex flex-col items-center justify-center py-2 gap-0.5">
        <span class="text-[13px] font-semibold"
              :class="actualSavingsByBucket < 0 ? 'text-red-500' : 'text-zinc-700 dark:text-zinc-200'">
          {{ incomeBudgeted
             ? (actualSavingsByBucket >= 0 ? '+' : '') + Math.round(actualSavingsByBucket / 10000) + '萬'
             : '—' }}
        </span>
        <span class="text-[10px] text-zinc-400">設定預算 − 已設預算</span>
      </div>

      <!-- 卡片 1–5：總收入 + 四個支出桶 -->
      <div v-for="card in CARDS" :key="card.key"
           class="bg-white dark:bg-zinc-900 rounded-xl shadow-md hover:-translate-y-0.5 transition-transform duration-200 overflow-hidden"
           :style="{ borderLeft: `5px solid ${card.border}` }">
        <div class="px-5 py-4 space-y-3">
          <!-- 標題 + 比例 badge -->
          <div class="flex items-start justify-between">
            <div>
              <div class="text-[13px] font-semibold text-zinc-500 dark:text-zinc-400">{{ card.label }}</div>
              <div class="text-[10px] text-zinc-400 mt-0.5 whitespace-nowrap overflow-hidden text-ellipsis">{{ card.sub }}</div>
            </div>
            <span v-if="card.key !== 'income'" class="text-[12px] font-bold px-2 py-0.5 rounded-full"
                  :style="{ background: card.badgeBg, color: card.badgeText }">
              {{ card.key==='life'?ratioLife : card.key==='fixed'?ratioFixed : card.key==='want'?ratioWant : ratioSave }}%
            </span>
          </div>

          <!-- 目標金額（大字） -->
          <div class="text-[28px] font-bold leading-none" :style="{ color: card.border }">
            {{ card.key === 'income'
               ? fmt(total, 'W')
               : fmt(targetAmounts[card.key], 'W') }}
          </div>

          <!-- 已設預算 vs 目標 -->
          <div>
            <div class="flex justify-between text-[12px] text-zinc-500 mb-1">
              <span>{{ card.key === 'income' ? '收入預估合計' : '已設預算' }}</span>
              <span :class="(card.key==='income' ? incomeBudgeted : budgetedByBucket[card.key]) >
                            (card.key==='income' ? total : targetAmounts[card.key])
                ? (card.key==='income' ? 'text-emerald-600 font-semibold' : 'text-red-500 font-semibold')
                : 'text-zinc-600 dark:text-zinc-300'">
                {{ card.key === 'income'
                   ? fmt(incomeBudgeted, 'W')
                   : fmt(budgetedByBucket[card.key], 'W') }}
              </span>
            </div>
            <!-- bar：滿格 = 200% 目標；100% 目標在 50% 處為顏色交界 -->
            <div class="relative w-full" style="padding: 3px 0">
              <div class="w-full h-2 rounded-full bg-zinc-100 dark:bg-zinc-700 overflow-hidden flex">
                <!-- 正常段（0 → 100% 目標 = bar 的 0–50%） -->
                <div class="h-2 transition-all flex-shrink-0"
                     :style="{
                       width: Math.min(barPct(
                         card.key==='income' ? incomeBudgeted : budgetedByBucket[card.key],
                         card.key==='income' ? total : targetAmounts[card.key]
                       ), 50) + '%',
                       background: card.border,
                       borderRadius: barPctNum(
                         card.key==='income' ? incomeBudgeted : budgetedByBucket[card.key],
                         card.key==='income' ? total : targetAmounts[card.key]
                       ) > 100 ? '9999px 0 0 9999px' : '9999px'
                     }">
                </div>
                <!-- 超標段（100% → 200% 目標 = bar 的 50–100%） -->
                <div v-if="barPctNum(
                       card.key==='income' ? incomeBudgeted : budgetedByBucket[card.key],
                       card.key==='income' ? total : targetAmounts[card.key]
                     ) > 100"
                     class="h-2 transition-all flex-shrink-0 rounded-r-full"
                     :style="{
                       width: Math.max(0, barPct(
                         card.key==='income' ? incomeBudgeted : budgetedByBucket[card.key],
                         card.key==='income' ? total : targetAmounts[card.key]
                       ) - 50) + '%',
                       background: '#dc2626'
                     }">
                </div>
              </div>
              <!-- 100% 目標標記線（在 bar 50% 處，突出上下） -->
              <div class="absolute rounded-sm bg-zinc-500 dark:bg-zinc-300"
                   style="left: 50%; transform: translateX(-50%); width: 2px; top: 0; bottom: 0">
              </div>
            </div>
          </div>

          <!-- 實際百分比 -->
          <div class="flex items-center justify-end">
            <span class="text-[11px] font-medium"
                  :class="barPctNum(
                    card.key==='income' ? incomeBudgeted : budgetedByBucket[card.key],
                    card.key==='income' ? total : targetAmounts[card.key]
                  ) > 100 ? 'text-red-500' : 'text-zinc-400'">
              {{ barPctNum(
                   card.key==='income' ? incomeBudgeted : budgetedByBucket[card.key],
                   card.key==='income' ? total : targetAmounts[card.key]
                 ) }}%
            </span>
          </div>
        </div>
      </div>

      <!-- 卡片 6：存款推算 -->
      <div class="bg-white dark:bg-zinc-900 rounded-xl shadow-md hover:-translate-y-0.5 transition-transform duration-200 overflow-hidden"
           style="border-left: 5px solid #f6ad55">
        <div class="px-5 py-4 space-y-3">
          <div class="text-[13px] font-semibold text-zinc-500 dark:text-zinc-400">{{ year }} 存款推算</div>

          <!-- 預算結餘大字 -->
          <div class="text-[28px] font-bold leading-none"
               :class="budgetSavings >= 0 ? 'text-emerald-600 dark:text-emerald-400' : 'text-red-500'">
            {{ budgetSavings >= 0 ? '+' : '' }}{{ fmt(budgetSavings, 'W') }}
          </div>

          <!-- 明細 -->
          <div class="space-y-1.5 text-[12px]">
            <div class="flex justify-between">
              <span class="text-zinc-400">預估收入</span>
              <span class="font-medium">{{ fmt(incomeBudgeted, 'W') }}</span>
            </div>
            <div class="flex justify-between">
              <span class="text-zinc-400">− 預算支出</span>
              <span class="font-medium">{{ fmt(yearTotalBudget, 'W') }}</span>
            </div>
            <div class="border-t border-zinc-100 dark:border-zinc-700 pt-1 flex justify-between font-semibold">
              <span class="text-zinc-500">= 預算結餘</span>
              <span :class="budgetSavings >= 0 ? 'text-emerald-600 dark:text-emerald-400' : 'text-red-500'">
                {{ budgetSavings >= 0 ? '+' : '' }}{{ fmt(budgetSavings, 'W') }}
              </span>
            </div>
          </div>

          <div class="text-[11px] text-zinc-400">
            年度預算 {{ fmt(total, 'W') }} 已分配 {{ fmt(yearTotalBudget, 'W') }}（存款 {{ total ? Math.round(budgetSavings / total * 100) : 0 }}%）
          </div>
        </div>
      </div>

    </div>

    <!-- ── 區塊分隔線 ── -->
    <div class="flex items-center gap-3 my-2">
      <div class="flex-1 h-px bg-zinc-300 dark:bg-zinc-700"></div>
      <span class="text-[11px] text-zinc-400 uppercase tracking-widest">細項預算編列</span>
      <div class="flex-1 h-px bg-zinc-300 dark:bg-zinc-700"></div>
    </div>

    <!-- ── 月例行預算表 ── -->
    <div class="bg-white dark:bg-zinc-900 rounded-xl shadow-sm border border-zinc-200 dark:border-zinc-700 overflow-hidden">
      <div class="px-5 py-3 border-b border-zinc-100 dark:border-zinc-800 flex items-center justify-between gap-3">
        <div class="flex items-center gap-3">
          <span class="text-[14px] font-semibold text-zinc-700 dark:text-zinc-200">已設預算</span>
          <button class="btn text-[12px] py-0.5 px-2" @click="expandAll">全部展開</button>
          <button class="btn text-[12px] py-0.5 px-2" @click="collapseAll">全部收合</button>
        </div>
        <span class="text-[11px] text-zinc-400">輸入數字或算式如 <code class="bg-zinc-100 dark:bg-zinc-800 px-1 rounded">15000*12</code>，離開欄位自動存</span>
      </div>
      <div class="overflow-auto">
        <table class="w-full text-[13px] border-collapse">
          <thead class="bg-zinc-50 dark:bg-zinc-800/60 text-zinc-500 dark:text-zinc-400 text-[12px]">
            <tr>
              <th class="text-left  py-2 px-3 border-b border-zinc-200 dark:border-zinc-700 w-[18%]">類別 / 子項目</th>
              <th class="text-right py-2 px-3 border-b border-zinc-200 dark:border-zinc-700 w-[12%]">設定預算</th>
              <th class="text-right py-2 px-3 border-b border-zinc-200 dark:border-zinc-700 w-[12%]">細項預算</th>
              <th class="text-right py-2 px-3 border-b border-zinc-200 dark:border-zinc-700 w-[10%]">月均</th>
              <th class="text-right py-2 px-3 border-b border-zinc-200 dark:border-zinc-700 w-[10%]">3年中位</th>
              <th class="text-left  py-2 px-3 border-b border-zinc-200 dark:border-zinc-700">註記</th>
              <th class="text-right py-2 px-3 border-b border-zinc-200 dark:border-zinc-700 w-[12%]">設定 − 細項</th>
            </tr>
          </thead>
          <tbody>
            <template v-for="section in BUCKET_SECTIONS" :key="section.key">
              <!-- 區塊標題列 -->
              <tr class="bg-zinc-200/60 dark:bg-zinc-700/60">
                <td class="py-1.5 px-3 font-bold text-[12px] text-zinc-600 dark:text-zinc-300 tracking-wide" colspan="7">
                  {{ section.label }}
                </td>
              </tr>
              <!-- 該區塊的類別 -->
              <template v-for="c in classesByBucket[section.key]" :key="c.cno">
                <tr class="bg-zinc-50/50 dark:bg-zinc-800/30 font-semibold">
                  <td class="py-1.5 px-3 border-b border-zinc-100 dark:border-zinc-800">
                    <button v-if="store.subjects.some(s => s.cno === c.cno)"
                            @click="toggleClass(c.cno)"
                            class="inline-flex items-center justify-center w-4 h-4 mr-1 text-zinc-400 hover:text-zinc-700 dark:hover:text-zinc-200 text-[10px]">
                      {{ expandedClasses.has(c.cno) ? '▼' : '▶' }}
                    </button>
                    <span v-else class="inline-block w-4 mr-1"></span>
                    {{ c.name }}
                  </td>
                  <!-- 設定預算（類別 input） -->
                  <td class="py-1.5 px-3 border-b border-zinc-100 dark:border-zinc-800 text-right">
                    <input :value="getEditValue(c.cno, 0)"
                           @input="onInput(c.cno, 0, $event)"
                           @blur="commitEdit(c.cno, 0)"
                           @keydown.enter="$event.target.blur()"
                           class="field w-24 text-right" placeholder="—" />
                  </td>
                  <!-- 細項預算（子項目加總，唯讀） -->
                  <td class="py-1.5 px-3 border-b border-zinc-100 dark:border-zinc-800 text-right text-zinc-500">
                    {{ classDetailSum(c.cno) ? fmt(classDetailSum(c.cno)) : '' }}
                  </td>
                  <!-- 月均（用 設定 || 細項） -->
                  <td class="py-1.5 px-3 border-b border-zinc-100 dark:border-zinc-800 text-right text-zinc-400">
                    {{ (classSetting(c.cno) || classDetailSum(c.cno))
                       ? fmt(Math.round((classSetting(c.cno) || classDetailSum(c.cno)) / 12)) : '' }}
                  </td>
                  <!-- 3年中位 -->
                  <td class="py-1.5 px-3 border-b border-zinc-100 dark:border-zinc-800 text-right text-zinc-400">
                    {{ fmt(median3yr(c.cno, 0)) || '' }}
                  </td>
                  <!-- 註記 -->
                  <td class="py-1.5 px-3 border-b border-zinc-100 dark:border-zinc-800">
                    <textarea :value="getNoteEditValue(c.cno, 0)"
                              @input="onNoteInput(c.cno, 0, $event)"
                              @blur="commitNote(c.cno, 0)"
                              :rows="noteRows(getNoteEditValue(c.cno, 0))"
                              class="field w-full text-[12px] resize-y leading-snug whitespace-pre-wrap"
                              placeholder="—"></textarea>
                  </td>
                  <!-- 設定 − 細項 -->
                  <td class="py-1.5 px-3 border-b border-zinc-100 dark:border-zinc-800 text-right"
                      :class="settingVsDetailClass(settingMinusDetail(c.cno))">
                    <template v-if="settingMinusDetail(c.cno) != null">
                      {{ settingMinusDetail(c.cno) >= 0 ? '+' : '' }}{{ fmt(settingMinusDetail(c.cno)) }}
                    </template>
                  </td>
                </tr>
                <tr v-for="s in (expandedClasses.has(c.cno) ? store.subjects.filter(x => x.cno === c.cno) : [])" :key="s.sno"
                    class="hover:bg-zinc-50 dark:hover:bg-zinc-800/20">
                  <td class="py-1 px-3 pl-8 border-b border-zinc-100/70 dark:border-zinc-800/40 text-zinc-500 dark:text-zinc-400">
                    └ {{ s.name }}
                  </td>
                  <!-- 設定預算：子項目層級留白 -->
                  <td class="py-1 px-3 border-b border-zinc-100/70 dark:border-zinc-800/40"></td>
                  <!-- 細項預算（子項目 input） -->
                  <td class="py-1 px-3 border-b border-zinc-100/70 dark:border-zinc-800/40 text-right">
                    <input :value="getEditValue(c.cno, s.sno)"
                           @input="onInput(c.cno, s.sno, $event)"
                           @blur="commitEdit(c.cno, s.sno)"
                           @keydown.enter="$event.target.blur()"
                           class="field w-24 text-right" placeholder="—" />
                  </td>
                  <!-- 月均 -->
                  <td class="py-1 px-3 border-b border-zinc-100/70 dark:border-zinc-800/40 text-right text-zinc-400">
                    {{ getYearBudget(c.cno, s.sno) ? fmt(Math.round(getYearBudget(c.cno, s.sno) / 12)) : '' }}
                  </td>
                  <!-- 3年中位 -->
                  <td class="py-1 px-3 border-b border-zinc-100/70 dark:border-zinc-800/40 text-right text-zinc-400">
                    {{ fmt(median3yr(c.cno, s.sno)) || '' }}
                  </td>
                  <!-- 註記 -->
                  <td class="py-1 px-3 border-b border-zinc-100/70 dark:border-zinc-800/40">
                    <textarea :value="getNoteEditValue(c.cno, s.sno)"
                              @input="onNoteInput(c.cno, s.sno, $event)"
                              @blur="commitNote(c.cno, s.sno)"
                              :rows="noteRows(getNoteEditValue(c.cno, s.sno))"
                              class="field w-full text-[12px] resize-y leading-snug whitespace-pre-wrap"
                              placeholder="—"></textarea>
                  </td>
                  <!-- 設定 − 細項：子項目層級無 -->
                  <td class="py-1 px-3 border-b border-zinc-100/70 dark:border-zinc-800/40"></td>
                </tr>
              </template>
              <!-- 區塊小計 -->
              <tr class="bg-zinc-50 dark:bg-zinc-800/50 text-[12px] font-semibold border-b-2 border-zinc-200 dark:border-zinc-700">
                <td class="py-1.5 px-3 text-zinc-500">{{ section.label }} 小計</td>
                <!-- 設定預算合計 -->
                <td class="py-1.5 px-3 text-right">
                  {{ fmt(classesByBucket[section.key].reduce((a,c) => a + classSetting(c.cno), 0)) }}
                </td>
                <!-- 細項預算合計 -->
                <td class="py-1.5 px-3 text-right text-zinc-500">
                  {{ fmt(classesByBucket[section.key].reduce((a,c) => a + classDetailSum(c.cno), 0)) }}
                </td>
                <!-- 月均（取設定或細項） -->
                <td class="py-1.5 px-3 text-right text-zinc-400">
                  {{ (() => {
                    const set = classesByBucket[section.key].reduce((a,c) => a + classSetting(c.cno), 0)
                    const det = classesByBucket[section.key].reduce((a,c) => a + classDetailSum(c.cno), 0)
                    const base = set || det
                    return base ? fmt(Math.round(base / 12)) : ''
                  })() }}
                </td>
                <!-- 3年中位 -->
                <td class="py-1.5 px-3 text-right text-zinc-400">
                  {{ fmt(classesByBucket[section.key].reduce((a,c) => a + median3yr(c.cno,0), 0)) || '' }}
                </td>
                <!-- 註記空白 -->
                <td></td>
                <!-- 設定 − 細項 -->
                <td class="py-1.5 px-3 text-right"
                    :class="(() => {
                      const set = classesByBucket[section.key].reduce((a,c) => a + classSetting(c.cno), 0)
                      const det = classesByBucket[section.key].reduce((a,c) => a + classDetailSum(c.cno), 0)
                      return settingVsDetailClass((set || det) ? set - det : null)
                    })()">
                  {{ (() => {
                    const set = classesByBucket[section.key].reduce((a,c) => a + classSetting(c.cno), 0)
                    const det = classesByBucket[section.key].reduce((a,c) => a + classDetailSum(c.cno), 0)
                    if (!set && !det) return ''
                    const diff = set - det
                    return (diff >= 0 ? '+' : '') + fmt(diff)
                  })() }}
                </td>
              </tr>
            </template>

            <!-- 總計 -->
            <tr class="font-bold bg-zinc-100 dark:bg-zinc-800 border-t-2 border-zinc-300 dark:border-zinc-600">
              <td class="py-2 px-3">總計</td>
              <!-- 設定預算總計 -->
              <td class="py-2 px-3 text-right">
                {{ fmt(BUCKET_SECTIONS.reduce((a,s) => a + classesByBucket[s.key].reduce((b,c) => b + classSetting(c.cno), 0), 0)) }}
              </td>
              <!-- 細項預算總計 -->
              <td class="py-2 px-3 text-right text-zinc-500">
                {{ fmt(BUCKET_SECTIONS.reduce((a,s) => a + classesByBucket[s.key].reduce((b,c) => b + classDetailSum(c.cno), 0), 0)) }}
              </td>
              <!-- 月均 -->
              <td class="py-2 px-3 text-right">
                {{ (() => {
                  const set = BUCKET_SECTIONS.reduce((a,s) => a + classesByBucket[s.key].reduce((b,c) => b + classSetting(c.cno), 0), 0)
                  const det = BUCKET_SECTIONS.reduce((a,s) => a + classesByBucket[s.key].reduce((b,c) => b + classDetailSum(c.cno), 0), 0)
                  const base = set || det
                  return base ? fmt(Math.round(base / 12)) : ''
                })() }}
              </td>
              <!-- 3年中位 -->
              <td class="py-2 px-3 text-right text-zinc-500">
                {{ fmt(BUCKET_SECTIONS.reduce((a,s) => a + classesByBucket[s.key].reduce((b,c) => b + median3yr(c.cno,0), 0), 0)) || '' }}
              </td>
              <!-- 註記空 -->
              <td></td>
              <!-- 設定 − 細項 -->
              <td class="py-2 px-3 text-right"
                  :class="(() => {
                    const set = BUCKET_SECTIONS.reduce((a,s) => a + classesByBucket[s.key].reduce((b,c) => b + classSetting(c.cno), 0), 0)
                    const det = BUCKET_SECTIONS.reduce((a,s) => a + classesByBucket[s.key].reduce((b,c) => b + classDetailSum(c.cno), 0), 0)
                    return settingVsDetailClass((set || det) ? set - det : null)
                  })()">
                {{ (() => {
                  const set = BUCKET_SECTIONS.reduce((a,s) => a + classesByBucket[s.key].reduce((b,c) => b + classSetting(c.cno), 0), 0)
                  const det = BUCKET_SECTIONS.reduce((a,s) => a + classesByBucket[s.key].reduce((b,c) => b + classDetailSum(c.cno), 0), 0)
                  if (!set && !det) return ''
                  const diff = set - det
                  return (diff >= 0 ? '+' : '') + fmt(diff)
                })() }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    </template><!-- /edit mode -->

    <!-- ── 歷年模式 ── -->
    <template v-else>
      <div class="bg-white dark:bg-zinc-900 rounded-xl shadow-sm border border-zinc-200 dark:border-zinc-700 overflow-auto">
        <table class="w-full text-[13px] border-collapse">
          <thead class="bg-zinc-50 dark:bg-zinc-800/60 text-zinc-500 dark:text-zinc-400 text-[12px]">
            <tr>
              <th class="text-left py-2 px-3 border-b border-zinc-200 dark:border-zinc-700 min-w-[120px]">項目</th>
              <th v-for="y in histYears" :key="y"
                  class="text-right py-2 px-3 border-b border-zinc-200 dark:border-zinc-700 min-w-[64px]">
                {{ y }}
              </th>
            </tr>
          </thead>
          <tbody>
            <!-- 年度收入預算 -->
            <tr class="border-b border-zinc-100 dark:border-zinc-800">
              <td class="py-2 px-3 font-semibold text-zinc-700 dark:text-zinc-200">年度收入預算</td>
              <td v-for="y in histYears" :key="y" class="py-2 px-3 text-right">
                <span v-if="histYearTotals.get(y)" class="font-semibold">
                  {{ Math.round(histYearTotals.get(y) / 10000) }}W
                </span>
                <span v-else class="text-zinc-300 dark:text-zinc-600">—</span>
              </td>
            </tr>

            <!-- 各桶位 -->
            <template v-for="section in BUCKET_SECTIONS" :key="section.key">
              <!-- 桶位標題 -->
              <tr class="bg-zinc-100/60 dark:bg-zinc-700/40">
                <td class="py-1 px-3 font-bold text-[11px] text-zinc-500 dark:text-zinc-400 tracking-wide uppercase" colspan="99">
                  {{ section.label }}
                </td>
              </tr>
              <!-- 各類別 -->
              <tr v-for="c in classesByBucket[section.key]" :key="c.cno"
                  class="border-b border-zinc-50 dark:border-zinc-800/50 hover:bg-zinc-50 dark:hover:bg-zinc-800/20">
                <td class="py-1.5 px-3 pl-5 text-zinc-600 dark:text-zinc-300">{{ c.name }}</td>
                <td v-for="y in histYears" :key="y" class="py-1.5 px-3 text-right">
                  <span v-if="histClassBudget(y, c.cno) != null">
                    {{ Math.round(histClassBudget(y, c.cno) / 10000) }}W
                  </span>
                  <span v-else class="text-zinc-300 dark:text-zinc-600">—</span>
                </td>
              </tr>
              <!-- 桶位小計 -->
              <tr class="bg-zinc-50 dark:bg-zinc-800/30 text-[12px] font-semibold border-b border-zinc-200 dark:border-zinc-700">
                <td class="py-1 px-3 pl-5 text-zinc-500">{{ section.label }} 小計</td>
                <td v-for="y in histYears" :key="y" class="py-1 px-3 text-right text-zinc-500">
                  <span v-if="histBucketTotal(y, section.key) != null">
                    {{ Math.round(histBucketTotal(y, section.key) / 10000) }}W
                  </span>
                  <span v-else class="text-zinc-300 dark:text-zinc-600">—</span>
                </td>
              </tr>
            </template>

            <!-- 總計 -->
            <tr class="font-bold bg-zinc-100 dark:bg-zinc-800 border-t-2 border-zinc-300 dark:border-zinc-600">
              <td class="py-2 px-3">已設預算合計</td>
              <td v-for="y in histYears" :key="y" class="py-2 px-3 text-right">
                {{ (() => {
                  const total = BUCKET_SECTIONS.reduce((a, s) => a + (histBucketTotal(y, s.key) ?? 0), 0)
                  return total ? Math.round(total / 10000) + 'W' : '—'
                })() }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </template><!-- /history mode -->

  </div>
</template>
