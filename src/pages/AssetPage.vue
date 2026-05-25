<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { useMoneyStore } from '../stores/money.js'

const store = useMoneyStore()

const SECTIONS = [
  { key: '現金',               icon: '🟢', color: '#10b981', cats: ['現金'] },
  { key: '投資',               icon: '🔵', color: '#3b82f6', cats: ['投資'] },
  { key: '動產/不動產 + 貸款', icon: '🏠', color: '#f59e0b', cats: ['動產/不動產', '負債'], copyable: true, yearOnly: true },
]
const CATEGORIES = [
  { key: '現金',        color: '#10b981' },
  { key: '投資',        color: '#3b82f6' },
  { key: '動產/不動產', color: '#f59e0b' },
  { key: '負債',        color: '#ef4444' },
]

// ── 年份 ────────────────────────────────────────────
const selectedYear = ref(new Date().getFullYear())

const allYears = computed(() => {
  const s = new Set(store.assetSnapshots.map(x => Number(x.date.slice(0, 4))))
  s.add(new Date().getFullYear())
  return [...s].sort((a, b) => b - a)
})

function monthEnd(year, m) {
  const d = new Date(year, m, 0)   // m=1→1月最後一天，以此類推
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

const months = computed(() =>
  Array.from({ length: 12 }, (_, i) => ({
    m: i + 1,
    label: `${i + 1}月`,
    date: monthEnd(selectedYear.value, i + 1),
  }))
)

const yearEndDate  = computed(() => monthEnd(selectedYear.value, 12))
const prevYearEndDate = computed(() => monthEnd(selectedYear.value - 1, 12))

// ── 歷年模式 ──────────────────────────────────────────
const viewMode = ref('edit')  // 'edit' | 'history'
const CURRENT_YEAR = new Date().getFullYear()

// 有 12-31 資料的年份（升序）；KPI 用
const histYearsWithYearEnd = computed(() =>
  [...new Set(
    store.assetSnapshots.filter(s => s.date.endsWith('-12-31')).map(s => Number(s.date.slice(0, 4)))
  )].sort((a, b) => a - b)
)
// 歷年表格顯示年份：加入當年（若有任何資料）
const histYears = computed(() => {
  const years = new Set(histYearsWithYearEnd.value)
  years.add(CURRENT_YEAR)  // 當年永遠顯示欄位
  return [...years].sort((a, b) => a - b)
})
// 每年的「代表日期」：過去年用 Dec 31；當年用最新非年底月份快照
const histDisplayDates = computed(() => {
  const map = {}
  for (const y of histYears.value) {
    if (y === CURRENT_YEAR) {
      const dates = store.assetSnapshots
        .filter(s => s.date.startsWith(String(y)) && !s.date.endsWith('-12-31'))
        .map(s => s.date)
        .sort()
      map[y] = dates.at(-1) ?? null
    } else {
      map[y] = monthEnd(y, 12)
    }
  }
  return map
})
// KPI 仍用最近有資料的 Dec 31（當年未結帳年底不算）
const histLatestYearEnd = computed(() =>
  histYearsWithYearEnd.value.length ? monthEnd(histYearsWithYearEnd.value.at(-1), 12) : null
)
const histPrevYearEnd = computed(() =>
  histYearsWithYearEnd.value.length >= 2 ? monthEnd(histYearsWithYearEnd.value.at(-2), 12) : null
)

// ── Snapshot 查詢 ─────────────────────────────────
// key: `${date}:${ano}` → amount
const snapMap = computed(() => {
  const m = new Map()
  for (const s of store.assetSnapshots) m.set(`${s.date}:${s.ano}`, s.amount)
  return m
})

function getAmt(ano, date) {
  return snapMap.value.get(`${date}:${ano}`)
}

// ── 帳戶分組 ───────────────────────────────────────
const byCategory = computed(() => {
  const m = {}
  for (const c of CATEGORIES) m[c.key] = []
  for (const a of store.assetAccounts) {
    if (m[a.category]) m[a.category].push(a)
  }
  return m
})

// ── 合計 ───────────────────────────────────────────
function catTotal(cat, date) {
  return (byCategory.value[cat] || []).reduce(
    (s, a) => s + (getAmt(a.ano, date) ?? 0), 0
  )
}

// 該年最後有資料的快照日期（現金/投資 KPI 基準）
// 當年度上限：上個月底（本月還沒到月底，紀錄都是月底資料 → 用上個月）
// 若當年無資料且為當年度，回退到全域最新快照日期（月份資料）
const latestDate = computed(() => {
  // 當年度時，上限為上個月底；其他年份無上限（取該年最新）
  const isCurYear = selectedYear.value === CURRENT_YEAR
  const upperBound = isCurYear ? monthEnd(CURRENT_YEAR, new Date().getMonth()) : null
  // 只取非年底（非 12-31）月份快照，避免動産年底資料蓋過月份基準
  const inYear = [...new Set(
    store.assetSnapshots
      .filter(s => s.date.startsWith(String(selectedYear.value))
        && !s.date.endsWith('-12-31')
        && (!upperBound || s.date <= upperBound))
      .map(s => s.date)
  )].sort()
  if (inYear.length) return inYear.at(-1)
  // 當年尚無月份快照 → 回退到全域最新非年底日期（同樣套用上限）
  if (isCurYear) {
    const allDates = [...new Set(
      store.assetSnapshots
        .filter(s => !s.date.endsWith('-12-31') && (!upperBound || s.date <= upperBound))
        .map(s => s.date)
    )].sort()
    return allDates.at(-1) ?? null
  }
  return null
})

// 去年最後有資料的月份快照日期（非年底）
const prevLatestDate = computed(() => {
  const dates = [...new Set(
    store.assetSnapshots
      .filter(s => s.date.startsWith(String(selectedYear.value - 1)) && !s.date.endsWith('-12-31'))
      .map(s => s.date)
  )].sort()
  return dates.at(-1) ?? null
})

// 動產/不動產＋負債 KPI 基準：最近一次 12-31 有資料，且 ≤ 當年年底
function latestYearEndUpTo(year) {
  const limit = `${year}-12-31`
  const dates = [...new Set(
    store.assetSnapshots
      .filter(s => s.date.endsWith('-12-31') && s.date <= limit)
      .map(s => s.date)
  )].sort()
  return dates.at(-1) ?? null
}
const latestYearEnd     = computed(() => latestYearEndUpTo(selectedYear.value))
const prevLatestYearEnd = computed(() => latestYearEndUpTo(selectedYear.value - 1))

// KPI
const totalAssets = computed(() => {
  if (!latestDate.value) return 0
  const monthly = ['現金', '投資'].reduce((s, c) => s + catTotal(c, latestDate.value), 0)
  const yearEnd = latestYearEnd.value ? catTotal('動產/不動產', latestYearEnd.value) : 0
  return monthly + yearEnd
})
const totalDebts = computed(() =>
  latestYearEnd.value ? catTotal('負債', latestYearEnd.value) : 0
)
const netWorth = computed(() => totalAssets.value - totalDebts.value)

const netWorthPrev = computed(() => {
  if (!prevLatestDate.value) return null
  const monthly = ['現金', '投資'].reduce((s, c) => s + catTotal(c, prevLatestDate.value), 0)
  const yearEnd = prevLatestYearEnd.value
    ? catTotal('動產/不動產', prevLatestYearEnd.value) - catTotal('負債', prevLatestYearEnd.value)
    : 0
  return monthly + yearEnd
})
const netDiff = computed(() =>
  netWorthPrev.value != null && latestDate.value
    ? netWorth.value - netWorthPrev.value
    : null
)

// 歷年模式 KPI（全用年底資料）
const histTotalAssets = computed(() => {
  const d = histLatestYearEnd.value
  return d ? ['現金', '投資', '動產/不動產'].reduce((s, c) => s + catTotal(c, d), 0) : 0
})
const histTotalDebts = computed(() =>
  histLatestYearEnd.value ? catTotal('負債', histLatestYearEnd.value) : 0
)
const histNetWorth = computed(() => histTotalAssets.value - histTotalDebts.value)
const histNetWorthPrev = computed(() => {
  const d = histPrevYearEnd.value
  return d
    ? ['現金', '投資', '動產/不動產'].reduce((s, c) => s + catTotal(c, d), 0) - catTotal('負債', d)
    : null
})
const histNetDiff = computed(() =>
  histNetWorthPrev.value != null ? histNetWorth.value - histNetWorthPrev.value : null
)

const debtSign = (cat) => cat === '負債' ? -1 : 1

function sectionCurDate(section) {
  if (viewMode.value === 'history') return histLatestYearEnd.value
  return section.yearOnly ? yearEndDate.value : latestDate.value
}
function sectionPrevDate(section) {
  if (viewMode.value === 'history') return histPrevYearEnd.value
  return section.yearOnly ? prevYearEndDate.value : prevLatestDate.value
}

function sectionTotal(section) {
  const d = sectionCurDate(section)
  return d ? section.cats.reduce((s, c) => s + debtSign(c) * catTotal(c, d), 0) : 0
}
function sectionDiff(section) {
  const d     = sectionCurDate(section)
  const prevD = sectionPrevDate(section)
  if (!d || !prevD) return null
  const cur  = section.cats.reduce((s, c) => s + debtSign(c) * catTotal(c, d), 0)
  const prev = section.cats.reduce((s, c) => s + debtSign(c) * catTotal(c, prevD), 0)
  return cur - prev
}

// ── Inline 編輯 ────────────────────────────────────
const editing = ref({})   // key: `${ano}:${date}`

function eKey(ano, date) { return `${ano}:${date}` }

function getEditVal(ano, date) {
  const k = eKey(ano, date)
  if (k in editing.value) return editing.value[k]
  const v = getAmt(ano, date)
  return v == null ? '' : String(v)
}

// 月度格子的 fallback：該格無資料時，往前找最近一個有資料的快照（含上一年 -12-31）
// 回傳 placeholder 字串：「~50,000」表示估值；無 fallback 則 "—"
// 例外：當年度尚未到達的月份（> 上個月底）→ 空白，不顯示估值
function getMonthlyPlaceholder(ano, date) {
  if (getAmt(ano, date) != null) return '—'
  // 當年度未到月份留白
  if (date.startsWith(String(CURRENT_YEAR))) {
    const prevMonthEnd = monthEnd(CURRENT_YEAR, new Date().getMonth())
    if (date > prevMonthEnd) return ''
  }
  let best = null
  for (const s of store.assetSnapshots) {
    if (s.ano !== ano) continue
    if (s.date >= date) continue   // 只看 < target 的快照（含 -12-31）
    if (!best || s.date > best.date) best = s
  }
  return best ? `~${Math.round(best.amount).toLocaleString()}` : '—'
}
function onInput(ano, date, ev) {
  editing.value[eKey(ano, date)] = ev.target.value
}
async function commit(ano, date) {
  const k = eKey(ano, date)
  if (!(k in editing.value)) return
  const raw = editing.value[k]
  const num = (raw === '' || raw == null) ? null : Number(raw)
  if (raw !== '' && raw != null && isNaN(num)) { delete editing.value[k]; return }
  await store.upsertAssetSnapshot({ date, ano, amount: num })
  delete editing.value[k]
}

// ── 新增帳戶 ───────────────────────────────────────
const addingCat = ref(null)
const newName   = ref('')
const newNote   = ref('')

async function addAccount() {
  if (!addingCat.value || !newName.value.trim()) { addingCat.value = null; return }
  await store.upsertAssetAccount({
    category: addingCat.value,
    name:     newName.value.trim(),
    note:     newNote.value.trim() || null,
  })
  newName.value = ''; newNote.value = ''; addingCat.value = null
}
function cancelAdd() { addingCat.value = null; newName.value = ''; newNote.value = '' }

// ── 刪除帳戶 ───────────────────────────────────────
async function delAcct(a) {
  if (!confirm(`刪除「${a.name}」？所有快照也會一起刪除。`)) return
  await store.deleteAssetAccount(a.ano)
}

// ── 改名帳戶 ───────────────────────────────────────
const renamingAno = ref(null)
const renameVal   = ref('')
function startRename(a) {
  renamingAno.value = a.ano
  renameVal.value   = a.name
}
function cancelRename() {
  renamingAno.value = null
  renameVal.value   = ''
}
async function commitRename(a) {
  const name = renameVal.value.trim()
  if (!name || name === a.name) { cancelRename(); return }
  await store.upsertAssetAccount({
    ano:      a.ano,
    category: a.category,
    name,
    note:     a.note,
    order_id: a.order_id,
  })
  cancelRename()
}

// ── 複製去年到今年空白月份（動產/不動產+貸款 section） ─
async function copyFromPrevYear(section) {
  const prevDate   = sectionPrevDate(section)
  const targetDates = section.yearOnly
    ? [yearEndDate.value]
    : months.value.map(mo => mo.date)
  if (!prevDate) { alert('去年沒有資料可複製'); return }
  const items = []
  for (const cat of section.cats) {
    for (const a of (byCategory.value[cat] || [])) {
      const prevAmt = getAmt(a.ano, prevDate)
      if (prevAmt != null) {
        for (const date of targetDates) {
          if (getAmt(a.ano, date) == null)
            items.push({ date, ano: a.ano, amount: prevAmt })
        }
      }
    }
  }
  if (!items.length) { alert('今年已有資料，無需複製'); return }
  await store.bulkUpsertAssetSnapshots(items)
}

onMounted(() => { if (store.db) store.loadAssets() })
watch(() => store.db, (v) => { if (v) store.loadAssets() })

// 格式化
function fmtW(n) {
  if (n == null) return '—'
  const w = Math.abs(n) / 10000
  return (n < 0 ? '−' : '') + w.toLocaleString('en-US', { maximumFractionDigits: 1 }) + 'W'
}
function fmtDiff(n) {
  if (n == null) return '—'
  if (!n) return '±0'
  return (n >= 0 ? '+' : '') + fmtW(n)
}

const colSpan = computed(() => months.value.length + 2) // 帳戶名 + 12月 + 刪
</script>

<template>
  <div class="p-4 h-full overflow-auto space-y-4 bg-zinc-50 dark:bg-zinc-950">

    <!-- ── 工具列 ── -->
    <div class="flex items-center gap-3">
      <!-- 模式切換 -->
      <div class="flex rounded-lg overflow-hidden border border-zinc-300 dark:border-zinc-600 text-[12px]">
        <button :class="['px-3 py-1 transition-colors', viewMode === 'edit'
          ? 'bg-blue-500 text-white'
          : 'bg-white dark:bg-zinc-800 text-zinc-600 dark:text-zinc-300 hover:bg-zinc-50 dark:hover:bg-zinc-700']"
          @click="viewMode = 'edit'">編輯</button>
        <button :class="['px-3 py-1 transition-colors border-l border-zinc-300 dark:border-zinc-600', viewMode === 'history'
          ? 'bg-blue-500 text-white'
          : 'bg-white dark:bg-zinc-800 text-zinc-600 dark:text-zinc-300 hover:bg-zinc-50 dark:hover:bg-zinc-700']"
          @click="viewMode = 'history'">歷年</button>
      </div>

      <template v-if="viewMode === 'edit'">
        <span class="text-[13px] text-zinc-500">年份</span>
        <select v-model.number="selectedYear" class="field">
          <option v-for="y in allYears" :key="y" :value="y">{{ y }}</option>
        </select>
        <span v-if="latestDate" class="text-[12px] text-zinc-400">
          KPI 基準：{{ latestDate }}
          <template v-if="latestYearEnd && latestYearEnd !== latestDate">
            （動產：{{ latestYearEnd }}）
          </template>
        </span>
        <span v-else class="text-[12px] text-zinc-400">（尚無資料）</span>
      </template>
    </div>

    <!-- ── KPI（僅編輯模式）── -->
    <div v-if="viewMode === 'edit'" class="grid grid-cols-2 xl:grid-cols-4 gap-4">
      <div v-for="card in [
        { label: '總資產', value: totalAssets, color: '#3b82f6', sub: '現金 + 投資 + 動不產',   isDiff: false },
        { label: '總負債', value: totalDebts,  color: '#ef4444', sub: '房貸等負債',              isDiff: false },
        { label: '淨資產', value: netWorth,    color: '#8b5cf6', sub: '總資產 − 負債',           isDiff: false },
        { label: '較去年', value: netDiff,     color: (netDiff ?? 0) >= 0 ? '#10b981' : '#ef4444', sub: prevLatestDate ?? '無去年資料', isDiff: true },
      ]" :key="card.label"
        class="bg-white dark:bg-zinc-900 rounded-xl shadow-md p-4"
        :style="{ borderLeft: `4px solid ${card.color}` }">
        <div class="text-[12px] text-zinc-500">{{ card.label }}</div>
        <div class="text-[26px] font-bold mt-1" :style="{ color: card.color }">
          {{ card.isDiff ? fmtDiff(card.value) : fmtW(card.value) }}
        </div>
        <div class="text-[11px] text-zinc-400 mt-1">{{ card.sub }}</div>
      </div>
    </div>

    <!-- ── 各區塊 ── -->
    <div v-for="section in SECTIONS" :key="section.key"
         class="bg-white dark:bg-zinc-900 rounded-xl shadow-sm border border-zinc-200 dark:border-zinc-700 overflow-hidden">

      <!-- 區塊標題 -->
      <div class="px-5 py-3 border-b border-zinc-100 dark:border-zinc-800 flex items-center justify-between"
           :style="{ background: section.color + '15' }">
        <div class="flex items-center gap-2">
          <span>{{ section.icon }}</span>
          <span class="text-[14px] font-semibold" :style="{ color: section.color }">{{ section.key }}</span>
          <template v-if="latestDate || section.yearOnly || viewMode === 'history'">
            <span class="text-[12px] text-zinc-500">合計</span>
            <span class="text-[14px] font-bold">{{ fmtW(sectionTotal(section)) }}</span>
            <span v-if="sectionDiff(section) != null" class="text-[11px]"
                  :class="sectionDiff(section) >= 0 ? 'text-emerald-600' : 'text-red-500'">
              {{ fmtDiff(sectionDiff(section)) }}
            </span>
          </template>
        </div>
        <button v-if="section.copyable && viewMode === 'edit'"
                class="btn text-[12px] py-0.5"
                :title="section.yearOnly
                  ? `從 ${prevYearEndDate} 複製到 ${yearEndDate}`
                  : `從去年最後一筆複製到 ${selectedYear} 各空白月份`"
                @click="copyFromPrevYear(section)">
          📋 複製去年
        </button>
      </div>

      <!-- 歷年模式表格（唯讀）-->
      <div v-if="viewMode === 'history'" class="overflow-x-auto">
        <table class="text-[12px] w-full">
          <thead class="text-[11px] text-zinc-500 bg-zinc-50 dark:bg-zinc-800/30">
            <tr>
              <th class="text-left py-2 px-4 font-medium w-[150px]">帳戶名</th>
              <th v-for="y in histYears" :key="y"
                  class="text-right py-1 px-2 font-medium leading-tight">
                <div>{{ y }}</div>
                <div v-if="histDisplayDates[y] && histDisplayDates[y] !== monthEnd(y, 12)"
                     class="text-[10px] font-normal text-blue-400">
                  {{ Number(histDisplayDates[y].slice(5, 7)) }}月
                </div>
              </th>
            </tr>
          </thead>
          <tbody>
            <template v-for="cat in section.cats" :key="cat">
              <tr v-for="a in byCategory[cat]" :key="a.ano"
                  class="border-t border-zinc-100 dark:border-zinc-800 hover:bg-zinc-50 dark:hover:bg-zinc-800/30">
                <td class="py-1 px-4 truncate">{{ a.name }}</td>
                <td v-for="y in histYears" :key="y"
                    class="py-1 px-2 text-right tabular-nums">
                  {{ fmtW(getAmt(a.ano, histDisplayDates[y])) }}
                </td>
              </tr>
              <tr class="border-t border-zinc-200 dark:border-zinc-700 font-semibold bg-zinc-50/80 dark:bg-zinc-800/30">
                <td class="py-1 px-4 text-[11px] text-zinc-500">小計</td>
                <td v-for="y in histYears" :key="y"
                    class="py-1 px-2 text-right text-[11px] tabular-nums">
                  {{ fmtW(catTotal(cat, histDisplayDates[y])) }}
                </td>
              </tr>
            </template>
          </tbody>
        </table>
      </div>

      <!-- 年底單欄表格（yearOnly sections） -->
      <div v-else-if="section.yearOnly" class="overflow-x-auto">
        <table class="text-[12px] w-full">
          <thead class="text-[11px] text-zinc-500 bg-zinc-50 dark:bg-zinc-800/30">
            <tr>
              <th class="text-left py-2 px-4 font-medium w-[200px]">帳戶名</th>
              <th class="text-right py-2 px-4 font-medium w-[160px]">{{ selectedYear }} 年底</th>
              <th class="w-7"></th>
            </tr>
          </thead>
          <tbody>
            <template v-for="cat in section.cats" :key="cat">
              <tr class="bg-zinc-100/60 dark:bg-zinc-800/40">
                <td colspan="3" class="py-1 px-4 text-[11px] font-medium text-zinc-500">
                  {{ cat }}
                  <span class="ml-1 text-[10px] text-zinc-400">
                    合計 {{ fmtW(catTotal(cat, yearEndDate)) }}
                  </span>
                </td>
              </tr>
              <tr v-if="!byCategory[cat]?.length">
                <td colspan="3" class="py-3 px-4 text-center text-zinc-400 text-[12px]">
                  還沒帳戶，點下方「+ 新增帳戶」加入
                </td>
              </tr>
              <tr v-for="a in byCategory[cat]" :key="a.ano"
                  class="border-t border-zinc-100 dark:border-zinc-800 hover:bg-zinc-50 dark:hover:bg-zinc-800/30">
                <td class="py-1 px-4 truncate">
                  <input v-if="renamingAno === a.ano"
                         v-model="renameVal"
                         class="field w-full text-[12px] px-1 py-0.5" autofocus
                         @blur="commitRename(a)"
                         @keydown.enter="commitRename(a)"
                         @keydown.esc="cancelRename" />
                  <template v-else>
                    <span>{{ a.name }}</span>
                    <button class="ml-1 text-[10px] text-zinc-400 hover:text-blue-600"
                            @click="startRename(a)">(改名)</button>
                  </template>
                </td>
                <td class="py-0.5 px-2">
                  <input type="number"
                         :value="getEditVal(a.ano, yearEndDate)"
                         @input="onInput(a.ano, yearEndDate, $event)"
                         @blur="commit(a.ano, yearEndDate)"
                         @keydown.enter="$event.target.blur()"
                         class="field w-full text-right text-[11px] px-1 py-0.5"
                         placeholder="—" />
                </td>
                <td class="py-1 px-1">
                  <button class="text-[11px] text-red-500 hover:underline px-1"
                          @click="delAcct(a)">刪</button>
                </td>
              </tr>
              <tr v-if="addingCat === cat" class="bg-zinc-50 dark:bg-zinc-800/50">
                <td colspan="3" class="py-2 px-4">
                  <div class="flex items-center gap-2">
                    <input v-model="newName" placeholder="帳戶名"
                           class="field w-40" autofocus
                           @keydown.enter="addAccount" @keydown.esc="cancelAdd" />
                    <button class="btn btn-primary text-[12px]" @click="addAccount">確定</button>
                    <button class="btn text-[12px]" @click="cancelAdd">取消</button>
                  </div>
                </td>
              </tr>
              <tr class="border-t border-zinc-50 dark:border-zinc-800/50">
                <td colspan="3" class="py-1 px-4">
                  <button class="text-[11px] text-zinc-400 hover:text-blue-600"
                          @click="addingCat = cat">
                    + 新增{{ cat }}帳戶
                  </button>
                </td>
              </tr>
            </template>
          </tbody>
        </table>
      </div>

      <!-- 12月份表格 -->
      <div v-else class="overflow-x-auto">
        <table class="text-[12px] w-full table-fixed">
          <thead class="text-[11px] text-zinc-500 bg-zinc-50 dark:bg-zinc-800/30">
            <tr>
              <th class="text-left py-2 px-4 font-medium w-[120px]">帳戶名</th>
              <th v-for="mo in months" :key="mo.date"
                  class="text-right py-2 px-1 font-medium">{{ mo.label }}</th>
              <th class="w-7"></th>
            </tr>
          </thead>
          <tbody>
            <template v-for="cat in section.cats" :key="cat">

              <!-- sub-category 標題（僅多類別區塊顯示） -->
              <tr v-if="section.cats.length > 1" class="bg-zinc-100/60 dark:bg-zinc-800/40">
                <td :colspan="colSpan" class="py-1 px-4 text-[11px] font-medium text-zinc-500">
                  {{ cat }}
                  <span v-if="latestDate" class="ml-1 text-[10px] text-zinc-400">
                    合計 {{ fmtW(catTotal(cat, latestDate)) }}
                  </span>
                </td>
              </tr>

              <!-- 無帳戶提示 -->
              <tr v-if="!byCategory[cat]?.length">
                <td :colspan="colSpan" class="py-3 px-4 text-center text-zinc-400 text-[12px]">
                  還沒帳戶，點下方「+ 新增帳戶」加入
                </td>
              </tr>

              <!-- 帳戶列 -->
              <tr v-for="a in byCategory[cat]" :key="a.ano"
                  class="border-t border-zinc-100 dark:border-zinc-800 group
                         hover:bg-zinc-50 dark:hover:bg-zinc-800/30">
                <td class="py-1 px-4 truncate">
                  <input v-if="renamingAno === a.ano"
                         v-model="renameVal"
                         class="field w-full text-[12px] px-1 py-0.5" autofocus
                         @blur="commitRename(a)"
                         @keydown.enter="commitRename(a)"
                         @keydown.esc="cancelRename" />
                  <template v-else>
                    <span>{{ a.name }}</span>
                    <button class="ml-1 text-[10px] text-zinc-400 hover:text-blue-600"
                            @click="startRename(a)">(改名)</button>
                  </template>
                </td>
                <td v-for="mo in months" :key="mo.date" class="py-0.5 px-0.5">
                  <input type="number"
                         :value="getEditVal(a.ano, mo.date)"
                         @input="onInput(a.ano, mo.date, $event)"
                         @blur="commit(a.ano, mo.date)"
                         @keydown.enter="$event.target.blur()"
                         class="field w-full text-right text-[11px] px-1 py-0.5"
                         :placeholder="getMonthlyPlaceholder(a.ano, mo.date)" />
                </td>
                <td class="py-1 px-1">
                  <button class="text-[11px] text-red-500 hover:underline px-1"
                          @click="delAcct(a)">刪</button>
                </td>
              </tr>

              <!-- 新增帳戶輸入列 -->
              <tr v-if="addingCat === cat" class="bg-zinc-50 dark:bg-zinc-800/50">
                <td :colspan="colSpan" class="py-2 px-4">
                  <div class="flex items-center gap-2">
                    <input v-model="newName" placeholder="帳戶名"
                           class="field w-40" autofocus
                           @keydown.enter="addAccount" @keydown.esc="cancelAdd" />
                    <button class="btn btn-primary text-[12px]" @click="addAccount">確定</button>
                    <button class="btn text-[12px]" @click="cancelAdd">取消</button>
                  </div>
                </td>
              </tr>

              <!-- 新增帳戶按鈕列 -->
              <tr class="border-t border-zinc-50 dark:border-zinc-800/50">
                <td :colspan="colSpan" class="py-1 px-4">
                  <button class="text-[11px] text-zinc-400 hover:text-blue-600"
                          @click="addingCat = cat">
                    + 新增{{ cat }}帳戶
                  </button>
                </td>
              </tr>

            </template>
          </tbody>
        </table>
      </div>
    </div>

  </div>
</template>
