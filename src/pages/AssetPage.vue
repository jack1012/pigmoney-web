<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { useMoneyStore } from '../stores/money.js'

const store = useMoneyStore()

const CATEGORIES = [
  { key: '現金',       icon: '🟢', color: '#10b981' },
  { key: '投資',       icon: '🔵', color: '#3b82f6' },
  { key: '動產/不動產', icon: '🟠', color: '#f59e0b' },
  { key: '負債',       icon: '🔴', color: '#ef4444' },
]

// ── 日期選擇 ──────────────────────────────────────
function lastDayOfMonth(yyyymm) {
  const [y, m] = yyyymm.split('-').map(Number)
  return new Date(y, m, 0).toISOString().slice(0, 10)
}
function thisMonthEnd() {
  const d = new Date()
  return lastDayOfMonth(`${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`)
}

const selectedDate = ref(thisMonthEnd())

// ── 所有 snapshot 日期（去重 + 排序） ──────────────
const allDates = computed(() => {
  const s = new Set(store.assetSnapshots.map(x => x.date))
  return [...s].sort().reverse()
})

// ── 當前日期的資產 lookup ─────────────────────────
const snapshotMap = computed(() => {
  const m = new Map()
  for (const s of store.assetSnapshots) {
    if (s.date === selectedDate.value) m.set(s.ano, s.amount)
  }
  return m
})
function getAmount(ano) { return snapshotMap.value.get(ano) }

// 上一個 snapshot 日期 (用於複製/比較)
const prevDate = computed(() => {
  const idx = allDates.value.indexOf(selectedDate.value)
  if (idx === -1) {
    // 當前日期還沒 snapshot：找最近的舊日期
    return allDates.value.find(d => d < selectedDate.value)
  }
  return allDates.value[idx + 1]
})
const prevSnapshotMap = computed(() => {
  if (!prevDate.value) return new Map()
  const m = new Map()
  for (const s of store.assetSnapshots) {
    if (s.date === prevDate.value) m.set(s.ano, s.amount)
  }
  return m
})

// ── 分組顯示 ──────────────────────────────────────
const accountsByCategory = computed(() => {
  const m = {}
  for (const c of CATEGORIES) m[c.key] = []
  for (const a of store.assetAccounts) {
    if (m[a.category]) m[a.category].push(a)
  }
  return m
})

function categoryTotal(cat) {
  return accountsByCategory.value[cat].reduce(
    (sum, a) => sum + (getAmount(a.ano) ?? 0), 0
  )
}

const totalAssets = computed(() =>
  ['現金', '投資', '動產/不動產'].reduce((s, c) => s + categoryTotal(c), 0)
)
const totalDebts = computed(() => categoryTotal('負債'))   // 負數
const netWorth = computed(() => totalAssets.value + totalDebts.value)

// 對比上次
function diffWithPrev(cat) {
  const cur = categoryTotal(cat)
  let prev = 0
  for (const a of accountsByCategory.value[cat]) {
    prev += prevSnapshotMap.value.get(a.ano) ?? 0
  }
  return cur - prev
}
const netWorthPrev = computed(() => {
  let s = 0
  for (const c of CATEGORIES) {
    for (const a of accountsByCategory.value[c.key]) {
      s += prevSnapshotMap.value.get(a.ano) ?? 0
    }
  }
  return s
})
const netDiff = computed(() => netWorth.value - netWorthPrev.value)

// ── 編輯（inline，blur 即存） ─────────────────────
const editing = ref({})
function getEditValue(ano) {
  if (ano in editing.value) return editing.value[ano]
  const v = getAmount(ano)
  return v == null ? '' : String(v)
}
function onInput(ano, ev) { editing.value[ano] = ev.target.value }
async function commitEdit(ano) {
  if (!(ano in editing.value)) return
  const raw = editing.value[ano]
  const num = (raw === '' || raw == null) ? null : Number(raw)
  if (raw !== '' && raw != null && isNaN(num)) {
    delete editing.value[ano]
    return
  }
  await store.upsertAssetSnapshot({ date: selectedDate.value, ano, amount: num })
  delete editing.value[ano]
}

// ── 新增帳戶 ──────────────────────────────────────
const addingCategory = ref(null)
const newAccountName = ref('')
const newAccountNote = ref('')
async function commitNewAccount() {
  if (!addingCategory.value || !newAccountName.value.trim()) {
    addingCategory.value = null
    return
  }
  await store.upsertAssetAccount({
    category: addingCategory.value,
    name: newAccountName.value.trim(),
    note: newAccountNote.value.trim() || null,
  })
  newAccountName.value = ''
  newAccountNote.value = ''
  addingCategory.value = null
}
function cancelNewAccount() {
  addingCategory.value = null
  newAccountName.value = ''
  newAccountNote.value = ''
}

// ── 刪除帳戶 ──────────────────────────────────────
async function deleteAcct(a) {
  if (!confirm(`刪除「${a.name}」？\n所有歷史 snapshot 也會一起刪除。`)) return
  await store.deleteAssetAccount(a.ano)
}

// ── 複製動產/不動產 上次 snapshot ─────────────────
async function copyRealEstateFromPrev() {
  if (!prevDate.value) { alert('沒有上一次 snapshot 可複製'); return }
  const items = []
  for (const a of accountsByCategory.value['動產/不動產']) {
    const prevAmt = prevSnapshotMap.value.get(a.ano)
    if (prevAmt != null) {
      items.push({ date: selectedDate.value, ano: a.ano, amount: prevAmt })
    }
  }
  if (!items.length) { alert('上次 snapshot 沒有動產/不動產資料'); return }
  await store.bulkUpsertAssetSnapshots(items)
}

// ── 新增 snapshot 日期 ────────────────────────────
const showAddDate = ref(false)
const newDate = ref(thisMonthEnd())
function openAddDate() {
  showAddDate.value = true
  newDate.value = thisMonthEnd()
}
function applyAddDate() {
  selectedDate.value = newDate.value
  showAddDate.value = false
}

// 載入
onMounted(() => { if (store.db) store.loadAssets() })
watch(() => store.db, (v) => { if (v) store.loadAssets() })

// 格式化
function fmt(n) {
  if (n == null || isNaN(n)) return '—'
  return Number(n).toLocaleString('en-US', { maximumFractionDigits: 0 })
}
function fmtW(n) {
  if (n == null || isNaN(n)) return '—'
  const w = n / 10000
  const sign = w >= 0 ? '' : '−'
  return sign + Math.abs(w).toLocaleString('en-US', { maximumFractionDigits: 1 }) + 'W'
}
function fmtDiff(n) {
  if (!n) return ''
  return (n >= 0 ? '+' : '') + fmtW(n)
}
</script>

<template>
  <div class="p-4 h-full overflow-auto space-y-4 bg-zinc-50 dark:bg-zinc-950">

    <!-- ── 工具列 ── -->
    <div class="flex items-center gap-2 flex-wrap">
      <span class="text-[13px] text-zinc-500 mr-1">快照日期</span>
      <select v-model="selectedDate" class="field">
        <option v-for="d in allDates" :key="d" :value="d">{{ d }}</option>
        <option v-if="!allDates.includes(selectedDate)" :value="selectedDate">{{ selectedDate }} (新)</option>
      </select>
      <button class="btn" @click="openAddDate">+ 新增日期</button>
    </div>

    <!-- 新增日期面板 -->
    <div v-if="showAddDate" class="bg-white dark:bg-zinc-900 rounded-xl border border-zinc-200 dark:border-zinc-700 px-5 py-3 flex items-center gap-3">
      <span class="text-[13px] text-zinc-500">建立新 snapshot 日期：</span>
      <input v-model="newDate" type="date" class="field" />
      <button class="btn btn-primary" @click="applyAddDate">套用</button>
      <button class="btn" @click="showAddDate = false">取消</button>
    </div>

    <!-- ── KPI ── -->
    <div class="grid grid-cols-2 xl:grid-cols-4 gap-4">
      <div v-for="card in [
        { label: '總資產', value: totalAssets, color: '#3b82f6', sub: '現金 + 投資 + 動不產' },
        { label: '總負債', value: totalDebts,  color: '#ef4444', sub: '房貸等' },
        { label: '淨資產', value: netWorth,    color: '#8b5cf6', sub: '總資產 + 負債(負數)' },
        { label: '較上次',  value: netDiff,    color: netDiff >= 0 ? '#10b981' : '#ef4444', sub: prevDate || '無歷史' },
      ]" :key="card.label"
        class="bg-white dark:bg-zinc-900 rounded-xl shadow-md p-4"
        :style="{ borderLeft: `4px solid ${card.color}` }">
        <div class="text-[12px] text-zinc-500">{{ card.label }}</div>
        <div class="text-[26px] font-bold mt-1" :style="{ color: card.color }">
          {{ card.label === '較上次' ? fmtDiff(card.value) : fmtW(card.value) }}
        </div>
        <div class="text-[11px] text-zinc-400 mt-1">{{ card.sub }}</div>
      </div>
    </div>

    <!-- ── 各類別區塊 ── -->
    <div v-for="cat in CATEGORIES" :key="cat.key"
         class="bg-white dark:bg-zinc-900 rounded-xl shadow-sm border border-zinc-200 dark:border-zinc-700 overflow-hidden">

      <!-- 標題列 -->
      <div class="px-5 py-3 border-b border-zinc-100 dark:border-zinc-800 flex items-center justify-between"
           :style="{ background: cat.color + '15' }">
        <div class="flex items-center gap-2">
          <span class="text-[14px]">{{ cat.icon }}</span>
          <span class="text-[14px] font-semibold" :style="{ color: cat.color }">{{ cat.key }}</span>
          <span class="text-[12px] text-zinc-500">合計</span>
          <span class="text-[14px] font-bold">{{ fmtW(categoryTotal(cat.key)) }}</span>
          <span v-if="diffWithPrev(cat.key)" class="text-[11px]"
                :class="diffWithPrev(cat.key) >= 0 ? 'text-emerald-600' : 'text-red-500'">
            {{ fmtDiff(diffWithPrev(cat.key)) }}
          </span>
        </div>
        <div class="flex items-center gap-2">
          <button v-if="cat.key === '動產/不動產' && prevDate"
                  class="btn text-[12px] py-0.5"
                  @click="copyRealEstateFromPrev"
                  :title="`從 ${prevDate} 複製`">
            📋 複製上次
          </button>
          <button class="btn text-[12px] py-0.5"
                  @click="addingCategory = cat.key">
            + 新增帳戶
          </button>
        </div>
      </div>

      <!-- 新增帳戶輸入列 -->
      <div v-if="addingCategory === cat.key"
           class="px-5 py-3 bg-zinc-50 dark:bg-zinc-800/50 border-b border-zinc-100 dark:border-zinc-800 flex items-center gap-2">
        <input v-model="newAccountName" placeholder="帳戶名（例：政德-玉山）"
               class="field w-48" @keydown.enter="commitNewAccount"
               @keydown.esc="cancelNewAccount" autofocus />
        <input v-model="newAccountNote" placeholder="備註（可空）"
               class="field flex-1" @keydown.enter="commitNewAccount" />
        <button class="btn btn-primary text-[12px]" @click="commitNewAccount">確定</button>
        <button class="btn text-[12px]" @click="cancelNewAccount">取消</button>
      </div>

      <!-- 帳戶列表 -->
      <table class="w-full text-[13px]">
        <thead class="text-[12px] text-zinc-500 bg-zinc-50 dark:bg-zinc-800/30">
          <tr>
            <th class="text-left  py-2 px-5 font-medium w-[35%]">帳戶名</th>
            <th class="text-right py-2 px-3 font-medium w-[18%]">當下金額</th>
            <th class="text-right py-2 px-3 font-medium w-[15%]">上次</th>
            <th class="text-right py-2 px-3 font-medium w-[12%]">變動</th>
            <th class="text-left  py-2 px-3 font-medium">備註</th>
            <th class="w-12"></th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="!accountsByCategory[cat.key].length">
            <td colspan="6" class="py-3 px-5 text-center text-zinc-400 text-[12px]">
              還沒帳戶，點右上「+ 新增帳戶」加入
            </td>
          </tr>
          <tr v-for="a in accountsByCategory[cat.key]" :key="a.ano"
              class="border-t border-zinc-100 dark:border-zinc-800 hover:bg-zinc-50 dark:hover:bg-zinc-800/30">
            <td class="py-1.5 px-5">{{ a.name }}</td>
            <td class="py-1.5 px-3 text-right">
              <input type="number"
                     :value="getEditValue(a.ano)"
                     @input="onInput(a.ano, $event)"
                     @blur="commitEdit(a.ano)"
                     @keydown.enter="$event.target.blur()"
                     class="field w-32 text-right" placeholder="—" />
            </td>
            <td class="py-1.5 px-3 text-right text-zinc-400 text-[12px]">
              {{ prevSnapshotMap.get(a.ano) != null ? fmt(prevSnapshotMap.get(a.ano)) : '' }}
            </td>
            <td class="py-1.5 px-3 text-right text-[12px]"
                :class="(() => {
                  const cur = getAmount(a.ano), prev = prevSnapshotMap.get(a.ano)
                  if (cur == null || prev == null) return 'text-zinc-400'
                  return (cur - prev) >= 0 ? 'text-emerald-600' : 'text-red-500'
                })()">
              <template v-if="getAmount(a.ano) != null && prevSnapshotMap.get(a.ano) != null">
                {{ fmtDiff(getAmount(a.ano) - prevSnapshotMap.get(a.ano)) }}
              </template>
            </td>
            <td class="py-1.5 px-3 text-zinc-500 text-[12px]">{{ a.note }}</td>
            <td class="py-1.5 px-2 text-right">
              <button class="text-[11px] text-red-500 hover:underline" @click="deleteAcct(a)">刪</button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

  </div>
</template>
