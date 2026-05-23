<script setup>
import { ref, computed, onMounted, onUnmounted, onActivated, nextTick, watch } from 'vue'
import { AgGridVue } from 'ag-grid-vue3'
import { themeQuartz } from 'ag-grid-community'
import { useMoneyStore } from '../stores/money.js'

const store = useMoneyStore()

const gridTheme = themeQuartz.withParams({
  fontFamily: 'inherit', fontSize: 13, headerFontSize: 12,
  rowHeight: 28, headerHeight: 30, spacing: 4,
})
const gridApi = ref(null)
function onGridReady(p) { gridApi.value = p.api }

const editMno = ref(null)

const form = ref({
  cno: null,
  sno: null,
  date: new Date().toISOString().slice(0, 10),
  note: '',
  amount: '',
  mode: '現金支出',
})

const subjectsForClass = computed(() =>
  form.value.cno != null
    ? store.subjects.filter((s) => s.cno === form.value.cno)
    : [],
)

// 用函式取代 watch，避免載入列時 sno 被清掉
function setCno(cno) {
  form.value.cno = cno
  form.value.sno = null
}

const thisMonth = new Date().toISOString().slice(0, 7)
const monthlyTransactions = computed(() =>
  store.transactions.filter((r) => r.date?.startsWith(thisMonth)),
)

// 給 AG Grid 用，補上 className / subjectName
const gridRows = computed(() => monthlyTransactions.value.map((r) => ({
  ...r,
  className:   store.classMap.get(r.cno)   ?? '',
  subjectName: store.subjectMap.get(r.sno) ?? '',
})))

const columnDefs = computed(() => [
  {
    headerName: '', field: 'delete', width: 55, sortable: false,
    pinned: 'left', suppressMovable: true,
    cellRenderer: (p) => {
      const btn = document.createElement('button')
      btn.innerText = '刪除'
      btn.className = 'text-[11px] text-red-500 hover:text-red-700 hover:underline px-1 cursor-pointer'
      btn.onclick = (ev) => { ev.stopPropagation(); onDelete(p.data.mno) }
      return btn
    },
  },
  { field: 'date',        headerName: '日期',   width: 105, sort: 'desc' },
  { field: 'className',   headerName: '類別',   width: 90 },
  { field: 'subjectName', headerName: '子項目', width: 110 },
  { field: 'mode',        headerName: '類型',   width: 100 },
  { field: 'spend',       headerName: '金額',   width: 100, type: 'numericColumn', valueFormatter: (p) => fmt(p.value) },
  { field: 'note',        headerName: '備註',   flex: 1, minWidth: 150 },
])
const defaultColDef = { resizable: true, sortable: true }
const rowClassRules = {
  'entry-row-active': (p) => p.data?.mno === editMno.value,
}
function onRowClicked(p) { loadRow(p.data) }
watch(editMno, () => nextTick(() => gridApi.value?.redrawRows()))

function fmt(n) {
  if (n == null) return ''
  return Number(n).toLocaleString('en-US', { maximumFractionDigits: 2 })
}

function evalAmount(s) {
  if (s == null || s === '') return null
  const clean = String(s).trim()
  if (clean === '') return null
  if (!/^[\d\s+\-*/().]+$/.test(clean)) return null
  try {
    // eslint-disable-next-line no-new-func
    const result = Function('"use strict"; return (' + clean + ')')()
    if (typeof result !== 'number' || !isFinite(result) || result < 0) return null
    return Math.round(result * 100) / 100
  } catch {
    return null
  }
}

const amountValue = computed(() => evalAmount(form.value.amount))
const isExpression = computed(() => /[+\-*/()]/.test(form.value.amount || ''))

const canSubmit = computed(() => form.value.cno != null && amountValue.value != null)
const canAdd    = computed(() => !editMno.value && canSubmit.value)
const canUpdate = computed(() => !!editMno.value && canSubmit.value)

function resetForm() {
  form.value.cno    = null
  form.value.sno    = null
  form.value.date   = new Date().toISOString().slice(0, 10)
  form.value.note   = ''
  form.value.amount = ''
  form.value.mode   = '現金支出'
  editMno.value     = null
}

function loadRow(r) {
  form.value.cno    = r.cno
  form.value.sno    = r.sno
  form.value.date   = r.date
  form.value.note   = r.note || ''
  form.value.amount = String(r.spend)
  form.value.mode   = r.mode
  editMno.value     = r.mno
}

function onAdd() {
  if (!canAdd.value) return
  store.addTransaction({
    cno:   form.value.cno,
    sno:   form.value.sno,
    spend: amountValue.value,
    date:  form.value.date,
    note:  form.value.note,
    mode:  form.value.mode,
  })
  form.value.amount = ''
  form.value.note   = ''
}

function onUpdate() {
  if (!canUpdate.value) return
  store.updateTransaction({
    mno:   editMno.value,
    cno:   form.value.cno,
    sno:   form.value.sno,
    spend: amountValue.value,
    date:  form.value.date,
    note:  form.value.note,
    mode:  form.value.mode,
  })
  resetForm()
}

function onDelete(mno) {
  if (!window.confirm('確定刪除這筆資料？')) return
  store.deleteTransaction(mno)
  if (editMno.value === mno) resetForm()
}

function handleKeydown(e) {
  if (e.key === 'Escape') resetForm()
}
onMounted(() => document.addEventListener('keydown', handleKeydown))
onUnmounted(() => document.removeEventListener('keydown', handleKeydown))
// keep-alive 下每次切回此分頁都會觸發
onActivated(() => { if (store.pendingEditMno) consumePendingEdit() })

// 從統計頁過來的編輯請求
function consumePendingEdit() {
  const mno = store.pendingEditMno
  if (!mno) return
  const r = store.transactions.find(t => t.mno === mno)
  if (r) loadRow(r)
  store.clearPendingEdit()
}
watch(() => store.pendingEditMno, (v) => { if (v) consumePendingEdit() })
</script>

<template>
  <div class="flex flex-col h-full p-3 gap-3">
    <section class="panel">
      <span class="panel-title">{{ editMno ? '修改資料' : '新增資料' }}</span>
      <div class="grid grid-cols-4 gap-3">
        <!-- 類別 -->
        <div class="col-span-1 flex flex-col">
          <label class="field-label mb-1">類別</label>
          <ul class="list-box">
            <li
              v-for="c in store.classes"
              :key="c.cno"
              class="list-item"
              :class="{ selected: form.cno === c.cno }"
              @click="setCno(c.cno)"
            >
              {{ c.name }}
            </li>
          </ul>
        </div>

        <!-- 子項目 -->
        <div class="col-span-1 flex flex-col">
          <label class="field-label mb-1">子項目</label>
          <ul class="list-box">
            <li
              v-if="!form.cno"
              class="px-2 py-1.5 text-zinc-400 text-[12px] italic"
            >
              （請先選類別）
            </li>
            <li
              v-for="s in subjectsForClass"
              :key="s.sno"
              class="list-item"
              :class="{ selected: form.sno === s.sno }"
              @click="form.sno = s.sno"
            >
              {{ s.name }}
            </li>
          </ul>
        </div>

        <!-- 詳細欄位 -->
        <div class="col-span-2 grid grid-cols-[auto_1fr] gap-x-2 gap-y-2 items-center text-[13px] content-start">
          <label class="field-label">日期:</label>
          <input v-model="form.date" type="date" class="field" />

          <label class="field-label">類型:</label>
          <select v-model="form.mode" class="field">
            <option>現金支出</option>
            <option>信用卡支出</option>
            <option>收入</option>
          </select>

          <label class="field-label">金額:</label>
          <div class="flex flex-col gap-0.5">
            <input
              v-model="form.amount"
              type="text"
              placeholder="支援 +-*/"
              class="field"
              :class="{ 'border-red-400': form.amount && amountValue === null }"
            />
            <span v-if="isExpression && amountValue !== null" class="text-[11px] text-blue-600 dark:text-blue-400">
              = {{ fmt(amountValue) }}
            </span>
            <span v-else-if="form.amount && amountValue === null" class="text-[11px] text-red-500">
              算式錯誤
            </span>
          </div>

          <label class="field-label self-start mt-1">備註:</label>
          <textarea v-model="form.note" rows="4" class="field resize-none" />

          <div class="col-span-2 flex gap-2 mt-1">
            <button class="btn btn-primary flex-1" :disabled="!canAdd" @click="onAdd">新增</button>
            <button class="btn btn-primary flex-1" :disabled="!canUpdate" @click="onUpdate">修改</button>
            <button class="btn flex-1" @click="resetForm">重置 (Esc)</button>
          </div>

          <p class="col-span-2 text-[11px] text-emerald-700 dark:text-emerald-400 mt-1">
            提示：點下方列可載入修改；金額支援算式如 120+50；[Esc] 重置
          </p>
        </div>
      </div>
    </section>

    <section class="panel flex-1 min-h-0 flex flex-col">
      <span class="panel-title">本月（{{ monthlyTransactions.length }} 筆）</span>
      <div class="flex-1 min-h-0 border-2 border-blue-400 dark:border-blue-500">
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
          @grid-ready="onGridReady"
          @row-clicked="onRowClicked"
        />
      </div>
    </section>
  </div>
</template>

<style scoped>
.list-box {
  border: 1px solid #d4d4d8;
  border-radius: 3px;
  background: #fff;
  height: 220px;
  overflow-y: auto;
  font-size: 14px;
}
:global(.dark) .list-box {
  border-color: #3f3f46;
  background: #18181b;
}

.list-item {
  padding: 5px 10px;
  cursor: pointer;
  user-select: none;
  line-height: 1.4;
}
.list-item:hover {
  background: #f4f4f5;
}
:global(.dark) .list-item:hover {
  background: #27272a;
}
.list-item.selected {
  background: #2563eb;
  color: #fff;
}
.list-item.selected:hover {
  background: #1d4ed8;
}
</style>

<style>
/* 記帳頁：選中列反白（同統計頁） */
.entry-row-active.ag-row {
  background-color: #dbeafe !important;
}
.entry-row-active.ag-row:hover {
  background-color: #bfdbfe !important;
}
.dark .entry-row-active.ag-row {
  background-color: rgba(30, 64, 175, 0.35) !important;
}
.dark .entry-row-active.ag-row:hover {
  background-color: rgba(30, 64, 175, 0.5) !important;
}
</style>
