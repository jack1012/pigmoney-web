<script setup>
import { ref, watch } from 'vue'
import { useMoneyStore } from '../stores/money.js'

const store = useMoneyStore()

// ── 類別狀態 ──────────────────────────────────────────
const selectedCno    = ref(null)
const localClasses   = ref([])
const classOrderDirty = ref(false)
const newClassName   = ref('')
const editClassName  = ref('')

watch(() => store.classes, (v) => {
  localClasses.value = [...v]
  classOrderDirty.value = false
}, { immediate: true, deep: true })

function selectClass(cno) {
  selectedCno.value   = cno
  editClassName.value = store.classes.find(c => c.cno === cno)?.name ?? ''
  selectedSno.value   = null
  editSubjectName.value = ''
}

function moveClass(dir) {
  const idx = localClasses.value.findIndex(c => c.cno === selectedCno.value)
  if (idx < 0) return
  const newIdx = idx + dir
  if (newIdx < 0 || newIdx >= localClasses.value.length) return
  const arr = [...localClasses.value];
  [arr[idx], arr[newIdx]] = [arr[newIdx], arr[idx]]
  localClasses.value = arr
  classOrderDirty.value = true
}

// 成功提示
const savedMsg = ref('')
let savedTimer = null
function showSaved(msg) {
  savedMsg.value = msg
  clearTimeout(savedTimer)
  savedTimer = setTimeout(() => { savedMsg.value = '' }, 2000)
}

async function onSaveClassOrder() {
  await store.saveClassOrder(localClasses.value.map(c => c.cno))
  classOrderDirty.value = false
  showSaved('✓ 類別順序已儲存')
}

function onResetClassOrder() {
  localClasses.value = [...store.classes]
  classOrderDirty.value = false
}

async function onAddClass() {
  const name = newClassName.value.trim()
  if (!name) return
  await store.addClass(name)
  newClassName.value = ''
}

async function onRenameClass() {
  const name = editClassName.value.trim()
  if (!name || !selectedCno.value) return
  await store.renameClass(selectedCno.value, name)
}

async function onDeleteClass() {
  if (!selectedCno.value) return
  const cls = store.classes.find(c => c.cno === selectedCno.value)
  if (!window.confirm(`確定刪除類別「${cls?.name}」及其所有子項目？`)) return
  const cno = selectedCno.value
  selectedCno.value = null
  selectedSno.value = null
  await store.deleteClass(cno)
}

// ── 子項目狀態 ────────────────────────────────────────
const selectedSno      = ref(null)
const localSubjects    = ref([])
const subjectOrderDirty = ref(false)
const newSubjectName   = ref('')
const editSubjectName  = ref('')

watch(() => store.subjects, () => {
  if (selectedCno.value != null) {
    localSubjects.value = store.subjects.filter(s => s.cno === selectedCno.value)
    subjectOrderDirty.value = false
  }
}, { deep: true })

watch(selectedCno, (cno) => {
  localSubjects.value = cno != null
    ? store.subjects.filter(s => s.cno === cno)
    : []
  subjectOrderDirty.value = false
  selectedSno.value = null
  newSubjectName.value = ''
  editSubjectName.value = ''
})

function selectSubject(sno) {
  selectedSno.value   = sno
  editSubjectName.value = store.subjects.find(s => s.sno === sno)?.name ?? ''
}

function moveSubject(dir) {
  const idx = localSubjects.value.findIndex(s => s.sno === selectedSno.value)
  if (idx < 0) return
  const newIdx = idx + dir
  if (newIdx < 0 || newIdx >= localSubjects.value.length) return
  const arr = [...localSubjects.value];
  [arr[idx], arr[newIdx]] = [arr[newIdx], arr[idx]]
  localSubjects.value = arr
  subjectOrderDirty.value = true
}

async function onSaveSubjectOrder() {
  await store.saveSubjectOrder(localSubjects.value.map(s => s.sno))
  subjectOrderDirty.value = false
  showSaved('✓ 子項目順序已儲存')
}

function onResetSubjectOrder() {
  localSubjects.value = store.subjects.filter(s => s.cno === selectedCno.value)
  subjectOrderDirty.value = false
}

async function onAddSubject() {
  const name = newSubjectName.value.trim()
  if (!name || !selectedCno.value) return
  await store.addSubject(selectedCno.value, name)
  newSubjectName.value = ''
}

async function onRenameSubject() {
  const name = editSubjectName.value.trim()
  if (!name || !selectedSno.value) return
  await store.renameSubject(selectedSno.value, name)
}

// ── 匯出 / 匯入 ───────────────────────────────────────
function onExport() {
  const data = {
    version: 1,
    classes: store.classes.map(c => ({ name: c.name, order_id: c.order_id })),
    subjects: store.subjects.map(s => ({
      className: store.classMap.get(s.cno) ?? '',
      name: s.name,
      order_id: s.order_id,
    })),
  }
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
  const url  = URL.createObjectURL(blob)
  const a    = document.createElement('a')
  a.href = url
  a.download = 'pigmoney-categories.json'
  a.click()
  URL.revokeObjectURL(url)
}

async function onImport() {
  const input = document.createElement('input')
  input.type = 'file'
  input.accept = '.json'
  input.onchange = async (e) => {
    const file = e.target.files[0]
    if (!file) return
    try {
      const data = JSON.parse(await file.text())
      if (!Array.isArray(data.classes) || !Array.isArray(data.subjects)) {
        alert('格式不正確，請使用本系統匯出的 JSON 檔')
        return
      }
      if (!window.confirm(`確定要以「${file.name}」完全取代現有的類別與子項目？\n原有資料將被清除，且無法還原。`)) return
      await store.importCategories(data)
      selectedCno.value = null
      selectedSno.value = null
      showSaved('✓ 設定檔已匯入')
    } catch {
      alert('匯入失敗：檔案解析錯誤')
    }
  }
  input.click()
}

async function onDeleteSubject() {
  if (!selectedSno.value) return
  const sub = store.subjects.find(s => s.sno === selectedSno.value)
  if (!window.confirm(`確定刪除子項目「${sub?.name}」？\n相關消費的子項目將自動設為空白。`)) return
  const sno = selectedSno.value
  selectedSno.value = null
  await store.deleteSubject(sno)
}
</script>

<template>
  <div class="p-3 flex flex-col h-full overflow-hidden text-[13px]">
    <!-- 工具列 -->
    <div class="flex items-center gap-2 mb-3 pb-2 border-b border-zinc-200 dark:border-zinc-700 shrink-0">
      <button class="btn" @click="onExport">匯出設定</button>
      <button class="btn" @click="onImport">匯入設定</button>
      <span v-if="savedMsg" class="text-[12px] text-emerald-600 dark:text-emerald-400 ml-1">{{ savedMsg }}</span>
    </div>
    <div class="grid grid-cols-3 gap-4 flex-1 min-h-0">

    <!-- ── 類別 ── -->
    <div class="flex flex-col min-h-0">
      <p class="text-[14px] font-medium text-zinc-700 dark:text-zinc-300 mb-2">類別</p>
      <div class="flex gap-2 flex-1 min-h-0">
        <ul class="list-box flex-1 min-h-0">
          <li
            v-for="c in localClasses"
            :key="c.cno"
            class="list-item"
            :class="{ selected: selectedCno === c.cno }"
            @click="selectClass(c.cno)"
          >{{ c.name }}</li>
        </ul>
        <div class="flex flex-col gap-1 shrink-0 w-[100px]">
          <button class="btn w-full" :disabled="!selectedCno" @click="moveClass(-1)">上移</button>
          <button class="btn w-full" :disabled="!selectedCno" @click="moveClass(1)">下移</button>
          <button class="btn w-full" :disabled="!classOrderDirty" @click="onSaveClassOrder">儲存順序</button>
          <button class="btn w-full" :disabled="!classOrderDirty" @click="onResetClassOrder">還原順序</button>
          <button class="btn w-full mt-2 text-red-600 border-red-300 hover:bg-red-50 dark:hover:bg-red-950 disabled:text-zinc-300 disabled:border-zinc-200"
            :disabled="!selectedCno" @click="onDeleteClass">刪除類別</button>
        </div>
      </div>
      <div class="grid grid-cols-[1fr_100px] gap-x-2 gap-y-1 mt-2 shrink-0">
        <input v-model="newClassName" class="field" placeholder="新類別名稱" @keyup.enter="onAddClass"/>
        <button class="btn" :disabled="!newClassName.trim()" @click="onAddClass">新增類別</button>
        <input v-model="editClassName" class="field" placeholder="修改名稱" :disabled="!selectedCno" @keyup.enter="onRenameClass"/>
        <button class="btn" :disabled="!selectedCno || !editClassName.trim()" @click="onRenameClass">修改類別</button>
      </div>
    </div>

    <!-- ── 子項目 ── -->
    <div class="flex flex-col min-h-0">
      <p class="text-[14px] font-medium text-zinc-700 dark:text-zinc-300 mb-2">子項目</p>
      <div class="flex gap-2 flex-1 min-h-0">
        <ul class="list-box flex-1 min-h-0">
          <li v-if="!selectedCno" class="px-2 py-1.5 text-zinc-400 italic text-[12px]">（請先選類別）</li>
          <li
            v-for="s in localSubjects"
            :key="s.sno"
            class="list-item"
            :class="{ selected: selectedSno === s.sno }"
            @click="selectSubject(s.sno)"
          >{{ s.name }}</li>
        </ul>
        <div class="flex flex-col gap-1 shrink-0 w-[100px]">
          <button class="btn w-full" :disabled="!selectedSno" @click="moveSubject(-1)">上移</button>
          <button class="btn w-full" :disabled="!selectedSno" @click="moveSubject(1)">下移</button>
          <button class="btn w-full" :disabled="!subjectOrderDirty" @click="onSaveSubjectOrder">儲存順序</button>
          <button class="btn w-full" :disabled="!subjectOrderDirty" @click="onResetSubjectOrder">還原順序</button>
          <button class="btn w-full mt-2 text-red-600 border-red-300 hover:bg-red-50 dark:hover:bg-red-950 disabled:text-zinc-300 disabled:border-zinc-200"
            :disabled="!selectedSno" @click="onDeleteSubject">刪除子項目</button>
        </div>
      </div>
      <div class="grid grid-cols-[1fr_100px] gap-x-2 gap-y-1 mt-2 shrink-0">
        <input v-model="newSubjectName" class="field" placeholder="新子項目名稱" :disabled="!selectedCno" @keyup.enter="onAddSubject"/>
        <button class="btn" :disabled="!selectedCno || !newSubjectName.trim()" @click="onAddSubject">新增子項目</button>
        <input v-model="editSubjectName" class="field" placeholder="修改名稱" :disabled="!selectedSno" @keyup.enter="onRenameSubject"/>
        <button class="btn" :disabled="!selectedSno || !editSubjectName.trim()" @click="onRenameSubject">修改子項目</button>
      </div>
    </div>

    <!-- ── 說明 ── -->
    <div class="flex flex-col min-h-0">
      <p class="text-[14px] font-medium text-zinc-700 dark:text-zinc-300 mb-2">分類設定說明</p>
      <div class="flex-1 min-h-0 overflow-y-auto border border-zinc-200 dark:border-zinc-700 rounded p-3 text-[12px] text-zinc-600 dark:text-zinc-400 leading-relaxed space-y-3">

        <div>
          <p class="font-medium text-zinc-700 dark:text-zinc-300 mb-1">類別與子項目</p>
          <p>分類分為兩層：<b>類別</b>（如食、衣、住、行）與<b>子項目</b>（如早餐、午餐、晚餐）。記帳時必須選擇類別，子項目可以留空。</p>
        </div>

        <div>
          <p class="font-medium text-zinc-700 dark:text-zinc-300 mb-1">新增</p>
          <p>在下方輸入框填入名稱後，按對應按鈕或 Enter 新增。新增子項目前須先在左側選取對應類別。</p>
        </div>

        <div>
          <p class="font-medium text-zinc-700 dark:text-zinc-300 mb-1">修改</p>
          <p>點選項目後，下方輸入框會自動填入現有名稱，改寫後按「修改類別」或「修改子項目」（或 Enter）送出。</p>
        </div>

        <div>
          <p class="font-medium text-zinc-700 dark:text-zinc-300 mb-1">排序</p>
          <p>選取項目後，用「上移」「下移」調整位置。調整完按「儲存順序」寫入，或按「還原順序」放棄。排序會影響記帳頁的顯示順序。</p>
        </div>

        <div>
          <p class="font-medium text-zinc-700 dark:text-zinc-300 mb-1">刪除</p>
          <ul class="space-y-0.5 pl-2">
            <li>· 刪除<b>子項目</b>：相關消費的子項目欄位自動設為空白。</li>
            <li>· 刪除<b>類別</b>：所有對應子項目一併刪除，消費記錄本身保留。</li>
          </ul>
        </div>

        <div>
          <p class="font-medium text-zinc-700 dark:text-zinc-300 mb-1">儲存</p>
          <p>所有設定都儲存在 .sqlite 檔案中，換電腦只需帶同一個檔案，分類設定會完整保留。</p>
        </div>

      </div>
    </div>

    </div><!-- /grid -->
  </div><!-- /flex-col -->
</template>

<style scoped>
.list-box {
  border: 1px solid #d4d4d8;
  border-radius: 3px;
  background: #fff;
  overflow-y: auto;
  font-size: 13px;
}
:global(.dark) .list-box {
  border-color: #3f3f46;
  background: #18181b;
}

.list-item {
  padding: 4px 10px;
  cursor: pointer;
  user-select: none;
  line-height: 1.5;
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
