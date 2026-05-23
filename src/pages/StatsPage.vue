<script setup>
import { ref, computed, watch, watchEffect, nextTick } from 'vue'
import { AgGridVue } from 'ag-grid-vue3'
import { themeQuartz } from 'ag-grid-community'
import { useMoneyStore } from '../stores/money.js'

const store = useMoneyStore()

const gridTheme = themeQuartz.withParams({
  fontFamily: 'inherit', fontSize: 13, headerFontSize: 12,
  rowHeight: 28, headerHeight: 30, spacing: 4,
})

// ── UI 狀態 ──────────────────────────────────────────
const viewMode    = ref('year')    // 'year' | 'category'
const periodMode  = ref('current') // 'current' | 'all' | 'range'
const currentYear = new Date().getFullYear().toString()
const rangeStart  = ref(currentYear)
const rangeEnd    = ref(currentYear)
const typeFilter  = ref('現金支出') // '全部' | '現金支出' | '信用卡支出' | '收入'
const selectedKey = ref(null)
const expandedKeys = ref(new Set())
const editMode    = ref(false)
const isDirty     = ref(false)
const gridApi     = ref(null)
const selectedMno = ref(null)
const noteSearch  = ref('')
const undoStack   = ref([])     // 編修模式回上一步用，最多 20 步

// ── 拖曳分隔線 ────────────────────────────────────────
const leftWidthPct = ref(33)
const containerRef = ref(null)

function onDividerMousedown(e) {
  e.preventDefault()
  const startX   = e.clientX
  const startPct = leftWidthPct.value
  function onMove(ev) {
    if (!containerRef.value) return
    const delta = (ev.clientX - startX) / containerRef.value.offsetWidth * 100
    leftWidthPct.value = Math.max(10, Math.min(70, startPct + delta))
  }
  function onUp() {
    document.removeEventListener('mousemove', onMove)
    document.removeEventListener('mouseup', onUp)
  }
  document.addEventListener('mousemove', onMove)
  document.addEventListener('mouseup', onUp)
}

// ── 支出/收入切換 ─────────────────────────────────────
function toggleType(type) {
  typeFilter.value = typeFilter.value === type ? '全部' : type
}

// ── 期間快速設定 ──────────────────────────────────────
function setPeriod(mode) {
  periodMode.value = mode
  if (mode === 'current') {
    rangeStart.value = currentYear
    rangeEnd.value   = currentYear
  } else if (mode === 'all') {
    rangeStart.value = ''
    rangeEnd.value   = ''
  }
  // 'range'：不動輸入框，讓使用者自行輸入
}

// ── 期間計算 ─────────────────────────────────────────
const allYears = computed(() => {
  const s = new Set(store.transactions.map(t => t.date?.slice(0, 4)).filter(Boolean))
  return [...s].sort()
})
const minYear = computed(() => allYears.value[0] ?? '')
const maxYear = computed(() => allYears.value[allYears.value.length - 1] ?? '')

// ── 基礎篩選（期間 + 類型）────────────────────────────
// 期間：直接以輸入框為準；空白 = 沿用 min/max（歷年度）
const preFiltered = computed(() => {
  let r = store.transactions
  const s = rangeStart.value || minYear.value
  const e = rangeEnd.value   || maxYear.value
  if (s && e) r = r.filter(t => { const y = t.date?.slice(0, 4); return y >= s && y <= e })
  if (typeFilter.value !== '全部') r = r.filter(t => t.mode === typeFilter.value)
  return r
})

// ── 樹狀選取再篩選 ────────────────────────────────────
// key 格式: 'yr:YYYY', 'mo:YYYY-MM', 'c:N', 's:N' 以 '|' 串接
const filtered = computed(() => {
  const key = selectedKey.value
  if (!key) return preFiltered.value
  let r = preFiltered.value
  for (const p of key.split('|')) {
    if      (p.startsWith('yr:')) r = r.filter(t => t.date?.startsWith(p.slice(3)))
    else if (p.startsWith('mo:')) r = r.filter(t => t.date?.startsWith(p.slice(3)))
    else if (p.startsWith('c:'))  r = r.filter(t => t.cno === +p.slice(2))
    else if (p.startsWith('s:'))  { const n = +p.slice(2); r = r.filter(t => n === 0 ? (t.sno == null || t.sno === 0) : t.sno === n) }
  }
  return r
})

// ── Grid rows ─────────────────────────────────────────
const gridRows = computed(() => {
  let rows = filtered.value
  const q = noteSearch.value.trim().toLowerCase()
  if (q) rows = rows.filter(t => (t.note || '').toLowerCase().includes(q))
  return rows.map(t => ({
    ...t,
    className:   store.classMap.get(t.cno)   ?? '',
    subjectName: store.subjectMap.get(t.sno) ?? '',
  }))
})

// ── 摘要 ─────────────────────────────────────────────
const round2 = n => Math.round(n * 100) / 100
const summary = computed(() => {
  let spend = 0, income = 0
  for (const r of gridRows.value) {
    if (r.mode === '收入') income += r.spend || 0
    else spend += r.spend || 0
  }
  return { count: gridRows.value.length, spend: round2(spend), income: round2(income), balance: round2(income - spend) }
})

// ── 樹狀資料輔助 ──────────────────────────────────────
function acc(node, isIncome, amt) {
  if (isIncome) node.income += amt; else node.spend += amt
}

// 年份模式: 年 > 月 > 項目 > 子項目
const yearTree = computed(() => {
  const map = {}
  preFiltered.value.forEach(t => {
    const yr = t.date?.slice(0, 4); const mo = t.date?.slice(0, 7)
    if (!yr) return
    const cno = t.cno ?? 0; const sno = t.sno
    const isIncome = t.mode === '收入'; const amt = t.spend || 0
    if (!map[yr]) map[yr] = { spend: 0, income: 0, months: {} }
    acc(map[yr], isIncome, amt)
    if (!map[yr].months[mo]) map[yr].months[mo] = { spend: 0, income: 0, cats: {} }
    acc(map[yr].months[mo], isIncome, amt)
    const cats = map[yr].months[mo].cats
    if (!cats[cno]) cats[cno] = { spend: 0, income: 0, subs: {} }
    acc(cats[cno], isIncome, amt)
    if (sno != null) {
      if (!cats[cno].subs[sno]) cats[cno].subs[sno] = { spend: 0, income: 0 }
      acc(cats[cno].subs[sno], isIncome, amt)
    }
  })
  return map
})

// 類別模式: 項目 > 子項目 > 年 > 月
const categoryTree = computed(() => {
  const map = {}
  preFiltered.value.forEach(t => {
    const cno = t.cno ?? 0; const sno = t.sno ?? 0
    const yr = t.date?.slice(0, 4); const mo = t.date?.slice(0, 7)
    if (!yr) return
    const isIncome = t.mode === '收入'; const amt = t.spend || 0
    if (!map[cno]) map[cno] = { spend: 0, income: 0, subs: {} }
    acc(map[cno], isIncome, amt)
    if (!map[cno].subs[sno]) map[cno].subs[sno] = { spend: 0, income: 0, years: {} }
    acc(map[cno].subs[sno], isIncome, amt)
    const yrs = map[cno].subs[sno].years
    if (!yrs[yr]) yrs[yr] = { spend: 0, income: 0, months: {} }
    acc(yrs[yr], isIncome, amt)
    if (!yrs[yr].months[mo]) yrs[yr].months[mo] = { spend: 0, income: 0 }
    acc(yrs[yr].months[mo], isIncome, amt)
  })
  return map
})

// ── AG Grid ──────────────────────────────────────────
const classValues = computed(() => store.classes.map(c => c.name))

const columnDefs = computed(() => {
  const e = editMode.value
  return [
    {
      headerName: '', field: 'delete', width: 55, sortable: false, editable: false,
      pinned: 'left', suppressMovable: true,
      cellRenderer: (p) => {
        const btn = document.createElement('button')
        btn.innerText = '刪除'
        btn.className = 'text-[11px] text-red-500 hover:text-red-700 hover:underline px-1 cursor-pointer'
        btn.onclick = (ev) => {
          ev.stopPropagation()
          if (window.confirm(`確定刪除這筆資料？\n${p.data.date} ${p.data.className}/${p.data.subjectName} ${fmt(p.data.spend)}`)) {
            store.deleteTransaction(p.data.mno)
            if (selectedMno.value === p.data.mno) selectedMno.value = null
          }
        }
        return btn
      }
    },
    { field: 'date',        headerName: '日期',   width: 105, editable: e, cellEditor: 'agTextCellEditor', sort: 'desc' },
    { field: 'mode',        headerName: '類型',   width: 100, editable: e, cellEditor: 'agSelectCellEditor',
      cellEditorParams: { values: ['現金支出', '信用卡支出', '收入'] } },
    { field: 'className',   headerName: '類別',   width: 90,  editable: e, cellEditor: 'agSelectCellEditor',
      cellEditorParams: { values: classValues.value } },
    { field: 'subjectName', headerName: '子項目', width: 110, editable: e, cellEditor: 'agSelectCellEditor',
      cellEditorParams: p => ({ values: store.subjects.filter(s => s.cno === p.data.cno).map(s => s.name) }) },
    { field: 'spend',       headerName: '金額',   width: 95,  editable: e, cellEditor: 'agTextCellEditor',
      type: 'numericColumn', valueFormatter: p => fmt(p.value) },
    { field: 'note',        headerName: '備註',   flex: 1, minWidth: 150, editable: e, cellEditor: 'agTextCellEditor' },
    {
      headerName: '', field: 'editInEntry', width: 60, sortable: false, editable: false,
      pinned: 'right', suppressMovable: true,
      cellRenderer: (p) => {
        const btn = document.createElement('button')
        btn.innerText = '✏ 修改'
        btn.className = 'text-[11px] text-blue-600 hover:text-blue-800 hover:underline px-1 cursor-pointer'
        btn.title = '到記帳頁編輯這筆'
        btn.onclick = (ev) => {
          ev.stopPropagation()
          store.requestEditInEntry(p.data.mno)
        }
        return btn
      }
    },
  ]
})

const defaultColDef = { resizable: true, sortable: true }

const rowClassRules = {
  'stats-row-active': p => p.data?.mno === selectedMno.value,
}

function onGridReady(p)    { gridApi.value = p.api }
function onRowClicked(p)   { selectedMno.value = p.data.mno }

watch(selectedMno, () => nextTick(() => gridApi.value?.redrawRows()))

function onCellValueChanged(p) {
  isDirty.value = true
  const data = p.data
  // 改動前先把 store 裡原始資料 snapshot 進 undo stack
  const oldTxn = store.transactions.find(t => t.mno === data.mno)
  if (oldTxn) {
    undoStack.value.push({
      mno: oldTxn.mno, cno: oldTxn.cno, sno: oldTxn.sno,
      spend: oldTxn.spend, date: oldTxn.date,
      note: oldTxn.note, mode: oldTxn.mode,
    })
    if (undoStack.value.length > 20) undoStack.value.shift()
  }

  let cno = data.cno, sno = data.sno
  if (p.colDef.field === 'className') {
    const cls = store.classes.find(c => c.name === p.newValue)
    if (!cls) return
    cno = cls.cno; sno = null
    p.node.setDataValue('cno', cls.cno)
    p.node.setDataValue('subjectName', '')
  } else if (p.colDef.field === 'subjectName') {
    const sub = store.subjects.find(s => s.name === p.newValue && s.cno === data.cno)
    sno = sub ? sub.sno : null
  }
  store.updateTransaction({ mno: data.mno, cno, sno, spend: parseFloat(data.spend) || 0, date: data.date, note: data.note, mode: data.mode })
}

async function onUndo() {
  if (undoStack.value.length === 0) return
  const old = undoStack.value.pop()
  await store.updateTransaction(old)
  selectedMno.value = old.mno
  nextTick(() => gridApi.value?.redrawRows())
}

watch(editMode, () => { gridApi.value?.setGridOption('columnDefs', columnDefs.value) })

// ── 樹狀操作 ─────────────────────────────────────────
function toggleExpand(key) {
  const next = new Set(expandedKeys.value)
  next.has(key) ? next.delete(key) : next.add(key)
  expandedKeys.value = next
}

// 視覺反白立即更新，AG Grid 延一幀再算
function selectKey(key) {
  selectedKey.value = selectedKey.value === key ? null : key
  nextTick(() => gridApi.value?.redrawRows())
}

watch(viewMode, () => {
  selectedKey.value = null
  expandFirstLevel()
})

// 資料初次載入時展開第一層
watch(() => store.transactions.length, (len) => {
  if (len > 0 && expandedKeys.value.size === 0) expandFirstLevel()
}, { immediate: true })

function expandAll() {
  const keys = new Set()
  if (viewMode.value === 'year') {
    Object.entries(yearTree.value).forEach(([yr, yData]) => {
      keys.add(`yr:${yr}`)
      Object.entries(yData.months).forEach(([mo, mData]) => {
        keys.add(`mo:${mo}`)
        Object.keys(mData.cats).forEach(cno => {
          const ck = `mo:${mo}|c:${cno}`
          if (Object.keys(mData.cats[cno].subs).length > 0) keys.add(ck)
        })
      })
    })
  } else {
    Object.entries(categoryTree.value).forEach(([cno, cData]) => {
      keys.add(`c:${cno}`)
      Object.entries(cData.subs).forEach(([sno, sData]) => {
        keys.add(`c:${cno}|s:${sno}`)
        Object.keys(sData.years).forEach(yr => keys.add(`c:${cno}|s:${sno}|yr:${yr}`))
      })
    })
  }
  expandedKeys.value = keys
}

function collapseAll() {
  expandedKeys.value = new Set()
}

function expandFirstLevel() {
  const keys = new Set()
  if (viewMode.value === 'year') {
    Object.keys(yearTree.value).forEach(yr => keys.add(`yr:${yr}`))
  } else {
    Object.keys(categoryTree.value).forEach(cno => keys.add(`c:${cno}`))
  }
  expandedKeys.value = keys
}

// ── 格式化 ───────────────────────────────────────────
function fmt(n) {
  if (n == null) return ''
  return Number(n).toLocaleString('en-US', { maximumFractionDigits: 2 })
}

function nodeAmt(node) {
  if (typeFilter.value === '收入') return fmt(node.income)
  if (typeFilter.value === '全部') {
    const net = node.income - node.spend
    return (net >= 0 ? '+' : '') + fmt(net)
  }
  return fmt(node.spend) // 現金支出 or 信用卡支出
}

function nodeAmtClass(node) {
  if (typeFilter.value === '收入') return 'text-emerald-600 dark:text-emerald-400'
  if (typeFilter.value === '全部') {
    return node.income >= node.spend
      ? 'text-emerald-600 dark:text-emerald-400'
      : 'text-red-500 dark:text-red-400'
  }
  return 'text-red-500 dark:text-red-400'
}

const monthLabel = mo => mo.slice(5) + '月'

function sanitizeYear(e) {
  const v = e.target.value.replace(/\D/g, '')
  e.target.value = v
  periodMode.value = 'range'   // 手動輸入 → 切換為自訂模式
  return v
}
</script>

<template>
  <div class="flex flex-col h-full overflow-hidden">

    <!-- 上方篩選列 -->
    <div class="flex flex-wrap items-center gap-x-3 gap-y-1 px-3 py-2 border-b border-zinc-200 dark:border-zinc-700 text-[13px] shrink-0">
      <!-- 檢視模式 -->
      <div class="flex gap-1">
        <button class="btn" :class="viewMode === 'year'     ? 'btn-primary' : ''" @click="viewMode = 'year'">年份模式</button>
        <button class="btn" :class="viewMode === 'category' ? 'btn-primary' : ''" @click="viewMode = 'category'">類別模式</button>
      </div>

      <div class="w-px h-4 bg-zinc-300 dark:bg-zinc-600" />

      <!-- 類型 -->
      <div class="flex gap-1">
        <button class="btn" :class="typeFilter === '現金支出'  ? 'btn-primary' : ''" @click="toggleType('現金支出')">現金支出</button>
        <button class="btn" :class="typeFilter === '信用卡支出' ? 'btn-primary' : ''" @click="toggleType('信用卡支出')">信用卡</button>
        <button class="btn" :class="typeFilter === '收入'      ? 'btn-primary' : ''" @click="toggleType('收入')">收入</button>
      </div>

      <div class="w-px h-4 bg-zinc-300 dark:bg-zinc-600" />

      <!-- 期間按鈕 + 年份輸入框：同一組 -->
      <div class="flex items-center gap-1">
        <span class="text-zinc-400 text-[12px] shrink-0">期間:</span>
        <button class="btn" :class="periodMode === 'current' ? 'btn-primary' : ''" @click="setPeriod('current')">當年度</button>
        <button class="btn" :class="periodMode === 'all'     ? 'btn-primary' : ''" @click="setPeriod('all')">歷年度</button>
        <button class="btn" :class="periodMode === 'range'   ? 'btn-primary' : ''" @click="setPeriod('range')">年度區間</button>
        <input :value="rangeStart" @input="rangeStart = sanitizeYear($event)" type="text" inputmode="numeric" :placeholder="minYear" class="field w-16 text-center ml-1" />
        <span class="text-zinc-400">～</span>
        <input :value="rangeEnd"   @input="rangeEnd = sanitizeYear($event)"   type="text" inputmode="numeric" :placeholder="maxYear" class="field w-16 text-center" />
      </div>
    </div>

    <!-- 主體：左樹 + 分隔線 + 右表格 -->
    <div ref="containerRef" class="flex flex-1 min-h-0">

      <!-- 左側樹狀 -->
      <div
        class="shrink-0 border-r border-zinc-200 dark:border-zinc-700 flex flex-col"
        :style="{ width: leftWidthPct + '%' }"
      >
      <div class="flex-1 overflow-y-auto text-[13px]">
        <!-- 年份模式: 年 > 月 > 項目 > 子項目 -->
        <template v-if="viewMode === 'year'">
          <div v-for="(yData, yr) in yearTree" :key="yr">

            <!-- L1: 年 -->
            <div
              class="flex items-center pr-2 py-1 cursor-pointer hover:bg-zinc-50 dark:hover:bg-zinc-800"
              :class="selectedKey === `yr:${yr}` ? 'bg-blue-200 dark:bg-blue-700 text-blue-900 dark:text-blue-100 font-semibold' : ''"
              @click="selectKey(`yr:${yr}`)"
            >
              <span class="pl-1 w-5 shrink-0 text-zinc-400 text-[11px]" @click.stop="toggleExpand(`yr:${yr}`)">
                {{ expandedKeys.has(`yr:${yr}`) ? '▼' : '▶' }}
              </span>
              <span class="flex-1 truncate font-medium">{{ yr }}年</span>
              <span class="text-[11px] shrink-0 ml-1 tabular-nums" :class="nodeAmtClass(yData)">{{ nodeAmt(yData) }}</span>
            </div>

            <template v-if="expandedKeys.has(`yr:${yr}`)">
              <div v-for="(mData, mo) in yData.months" :key="mo">

                <!-- L2: 月 -->
                <div
                  class="flex items-center pr-2 py-0.5 cursor-pointer hover:bg-zinc-50 dark:hover:bg-zinc-800 pl-5"
                  :class="selectedKey === `mo:${mo}` ? 'bg-blue-200 dark:bg-blue-700 text-blue-900 dark:text-blue-100 font-semibold' : ''"
                  @click="selectKey(`mo:${mo}`)"
                >
                  <span class="w-4 shrink-0 text-zinc-400 text-[11px]" @click.stop="toggleExpand(`mo:${mo}`)">
                    {{ expandedKeys.has(`mo:${mo}`) ? '▼' : '▶' }}
                  </span>
                  <span class="flex-1 truncate">{{ monthLabel(mo) }}</span>
                  <span class="text-[11px] shrink-0 ml-1 tabular-nums" :class="nodeAmtClass(mData)">{{ nodeAmt(mData) }}</span>
                </div>

                <template v-if="expandedKeys.has(`mo:${mo}`)">
                  <div v-for="(cData, cno) in mData.cats" :key="cno">

                    <!-- L3: 項目 -->
                    <div
                      class="flex items-center pr-2 py-0.5 cursor-pointer hover:bg-zinc-50 dark:hover:bg-zinc-800 pl-9"
                      :class="selectedKey === `mo:${mo}|c:${cno}` ? 'bg-blue-200 dark:bg-blue-700 text-blue-900 dark:text-blue-100 font-semibold' : ''"
                      @click="selectKey(`mo:${mo}|c:${cno}`)"
                    >
                      <span
                        v-if="Object.keys(cData.subs).length > 0"
                        class="w-4 shrink-0 text-zinc-400 text-[11px]"
                        @click.stop="toggleExpand(`mo:${mo}|c:${cno}`)"
                      >{{ expandedKeys.has(`mo:${mo}|c:${cno}`) ? '▼' : '▶' }}</span>
                      <span v-else class="w-4 shrink-0" />
                      <span class="flex-1 truncate">{{ store.classMap.get(+cno) }}</span>
                      <span class="text-[11px] shrink-0 ml-1 tabular-nums" :class="nodeAmtClass(cData)">{{ nodeAmt(cData) }}</span>
                    </div>

                    <template v-if="expandedKeys.has(`mo:${mo}|c:${cno}`)">
                      <!-- L4: 子項目（葉） -->
                      <div
                        v-for="(sData, sno) in cData.subs"
                        :key="sno"
                        class="flex items-center pr-2 py-0.5 cursor-pointer hover:bg-zinc-50 dark:hover:bg-zinc-800 pl-14"
                        :class="selectedKey === `mo:${mo}|c:${cno}|s:${sno}` ? 'bg-blue-200 dark:bg-blue-700 text-blue-900 dark:text-blue-100 font-semibold' : ''"
                        @click="selectKey(`mo:${mo}|c:${cno}|s:${sno}`)"
                      >
                        <span class="w-4 shrink-0" />
                        <span class="flex-1 truncate text-zinc-600 dark:text-zinc-400">{{ store.subjectMap.get(+sno) }}</span>
                        <span class="text-[11px] shrink-0 ml-1 tabular-nums" :class="nodeAmtClass(sData)">{{ nodeAmt(sData) }}</span>
                      </div>
                    </template>

                  </div>
                </template>
              </div>
            </template>
          </div>
        </template>

        <!-- 類別模式: 項目 > 子項目 > 年 > 月 -->
        <template v-else>
          <div v-for="(cData, cno) in categoryTree" :key="cno">

            <!-- L1: 項目 -->
            <div
              class="flex items-center pr-2 py-1 cursor-pointer hover:bg-zinc-50 dark:hover:bg-zinc-800"
              :class="selectedKey === `c:${cno}` ? 'bg-blue-200 dark:bg-blue-700 text-blue-900 dark:text-blue-100 font-semibold' : ''"
              @click="selectKey(`c:${cno}`)"
            >
              <span class="pl-1 w-5 shrink-0 text-zinc-400 text-[11px]" @click.stop="toggleExpand(`c:${cno}`)">
                {{ expandedKeys.has(`c:${cno}`) ? '▼' : '▶' }}
              </span>
              <span class="flex-1 truncate font-medium">{{ store.classMap.get(+cno) }}</span>
              <span class="text-[11px] shrink-0 ml-1 tabular-nums" :class="nodeAmtClass(cData)">{{ nodeAmt(cData) }}</span>
            </div>

            <template v-if="expandedKeys.has(`c:${cno}`)">
              <div v-for="(sData, sno) in cData.subs" :key="sno">

                <!-- L2: 子項目 -->
                <div
                  class="flex items-center pr-2 py-0.5 cursor-pointer hover:bg-zinc-50 dark:hover:bg-zinc-800 pl-5"
                  :class="selectedKey === `c:${cno}|s:${sno}` ? 'bg-blue-200 dark:bg-blue-700 text-blue-900 dark:text-blue-100 font-semibold' : ''"
                  @click="selectKey(`c:${cno}|s:${sno}`)"
                >
                  <span class="w-4 shrink-0 text-zinc-400 text-[11px]" @click.stop="toggleExpand(`c:${cno}|s:${sno}`)">
                    {{ expandedKeys.has(`c:${cno}|s:${sno}`) ? '▼' : '▶' }}
                  </span>
                  <span class="flex-1 truncate">{{ store.subjectMap.get(+sno) || '（未分類）' }}</span>
                  <span class="text-[11px] shrink-0 ml-1 tabular-nums" :class="nodeAmtClass(sData)">{{ nodeAmt(sData) }}</span>
                </div>

                <template v-if="expandedKeys.has(`c:${cno}|s:${sno}`)">
                  <div v-for="(yData, yr) in sData.years" :key="yr">

                    <!-- L3: 年 -->
                    <div
                      class="flex items-center pr-2 py-0.5 cursor-pointer hover:bg-zinc-50 dark:hover:bg-zinc-800 pl-9"
                      :class="selectedKey === `c:${cno}|s:${sno}|yr:${yr}` ? 'bg-blue-200 dark:bg-blue-700 text-blue-900 dark:text-blue-100 font-semibold' : ''"
                      @click="selectKey(`c:${cno}|s:${sno}|yr:${yr}`)"
                    >
                      <span class="w-4 shrink-0 text-zinc-400 text-[11px]" @click.stop="toggleExpand(`c:${cno}|s:${sno}|yr:${yr}`)">
                        {{ expandedKeys.has(`c:${cno}|s:${sno}|yr:${yr}`) ? '▼' : '▶' }}
                      </span>
                      <span class="flex-1 truncate">{{ yr }}年</span>
                      <span class="text-[11px] shrink-0 ml-1 tabular-nums" :class="nodeAmtClass(yData)">{{ nodeAmt(yData) }}</span>
                    </div>

                    <template v-if="expandedKeys.has(`c:${cno}|s:${sno}|yr:${yr}`)">
                      <!-- L4: 月（葉） -->
                      <div
                        v-for="(mData, mo) in yData.months"
                        :key="mo"
                        class="flex items-center pr-2 py-0.5 cursor-pointer hover:bg-zinc-50 dark:hover:bg-zinc-800 pl-14"
                        :class="selectedKey === `c:${cno}|s:${sno}|mo:${mo}` ? 'bg-blue-200 dark:bg-blue-700 text-blue-900 dark:text-blue-100 font-semibold' : ''"
                        @click="selectKey(`c:${cno}|s:${sno}|mo:${mo}`)"
                      >
                        <span class="w-4 shrink-0" />
                        <span class="flex-1 truncate text-zinc-600 dark:text-zinc-400">{{ monthLabel(mo) }}</span>
                        <span class="text-[11px] shrink-0 ml-1 tabular-nums" :class="nodeAmtClass(mData)">{{ nodeAmt(mData) }}</span>
                      </div>
                    </template>

                  </div>
                </template>
              </div>
            </template>
          </div>
        </template>
      </div>

        <!-- 全部展開 / 全部收闔 -->
        <div class="flex gap-1 px-2 py-1.5 border-t border-zinc-200 dark:border-zinc-700 shrink-0">
          <button class="btn flex-1 text-[12px]" @click="expandAll">全部展開</button>
          <button class="btn flex-1 text-[12px]" @click="collapseAll">全部收闔</button>
        </div>
      </div>

      <!-- 拖曳分隔線 -->
      <div
        class="w-1 shrink-0 cursor-col-resize bg-zinc-200 dark:bg-zinc-700 hover:bg-blue-400 dark:hover:bg-blue-600 transition-colors"
        @mousedown="onDividerMousedown"
      />

      <!-- 右側 -->
      <div class="flex flex-col flex-1 min-w-0">

        <!-- 操作列 -->
        <div class="flex items-center gap-2 px-3 py-1.5 border-b border-zinc-100 dark:border-zinc-800 shrink-0">
          <div class="flex items-center gap-1">
            <button class="btn" :class="!editMode ? 'btn-primary' : ''" @click="editMode = false; isDirty = false">瀏覽模式</button>
            <button class="btn" :class="editMode  ? 'btn-primary' : ''" @click="editMode = true">編修模式</button>
            <span v-if="editMode && isDirty" class="text-[12px] text-red-500 dark:text-red-400 ml-1 font-medium">● 有修改</span>
            <button v-if="editMode"
                    class="btn ml-1"
                    :disabled="undoStack.length === 0"
                    :title="`還原最近一次修改（剩 ${undoStack.length} 步可還原）`"
                    @click="onUndo">
              ↶ 回上一步 <span v-if="undoStack.length > 0" class="text-[11px] text-zinc-400 ml-0.5">({{ undoStack.length }})</span>
            </button>
          </div>
        </div>

        <!-- 摘要列 -->
        <div class="flex flex-wrap gap-x-4 gap-y-0.5 px-3 py-1.5 border-b border-zinc-100 dark:border-zinc-800 text-[13px] shrink-0">
          <span class="text-zinc-500">共 <b class="text-zinc-800 dark:text-zinc-200">{{ summary.count }}</b> 筆</span>
          <span class="text-zinc-500">支出 <b class="text-red-600 dark:text-red-400">{{ fmt(summary.spend) }}</b></span>
          <span class="text-zinc-500">收入 <b class="text-emerald-600 dark:text-emerald-400">{{ fmt(summary.income) }}</b></span>
          <span class="text-zinc-500">結餘 <b :class="summary.balance >= 0 ? 'text-emerald-700 dark:text-emerald-300' : 'text-red-700 dark:text-red-300'">{{ fmt(summary.balance) }}</b></span>
        </div>

        <!-- 表格 -->
        <div
          class="flex-1 min-h-0 border-2 transition-colors duration-150"
          :class="editMode ? 'border-red-400 dark:border-red-600 is-edit-mode' : 'border-blue-400 dark:border-blue-500 is-browse-mode'"
        >
          <AgGridVue
            class="h-full w-full"
            :theme="gridTheme"
            :rowData="gridRows"
            :columnDefs="columnDefs"
            :defaultColDef="defaultColDef"
            :rowClassRules="rowClassRules"
            :getRowId="p => String(p.data.mno)"
            rowSelection="single"
            :animateRows="false"
            :stopEditingWhenCellsLoseFocus="true"
            @grid-ready="onGridReady"
            @row-clicked="onRowClicked"
            @cell-value-changed="onCellValueChanged"
          />
        </div>

        <!-- 下方搜尋列 -->
        <div class="flex items-center gap-2 px-3 py-1.5 border-t border-zinc-200 dark:border-zinc-700 shrink-0">
          <label class="text-[12px] text-zinc-500 shrink-0">搜尋備註:</label>
          <input
            v-model="noteSearch"
            type="text"
            placeholder="輸入關鍵字…"
            class="field flex-1"
          />
          <button
            v-if="noteSearch"
            class="btn text-[12px]"
            @click="noteSearch = ''"
          >清除</button>
        </div>
      </div>
    </div>
  </div>
</template>

<style>
/* 統計頁：選中列反白 */
.stats-row-active.ag-row {
  background-color: #dbeafe !important;
}
.stats-row-active.ag-row:hover {
  background-color: #bfdbfe !important;
}
.dark .stats-row-active.ag-row {
  background-color: rgba(30, 64, 175, 0.35) !important;
}
.dark .stats-row-active.ag-row:hover {
  background-color: rgba(30, 64, 175, 0.5) !important;
}

/* 選中格子：瀏覽=藍框，編修=紅框 */
.is-browse-mode .ag-cell-focus {
  outline: 2px solid #3b82f6 !important;
  outline-offset: -2px !important;
}
.dark .is-browse-mode .ag-cell-focus {
  outline-color: #60a5fa !important;
}
.is-edit-mode .ag-cell-focus {
  outline: 2px solid #ef4444 !important;
  outline-offset: -2px !important;
}
.dark .is-edit-mode .ag-cell-focus {
  outline-color: #f87171 !important;
}
</style>
