<script setup>
import { ref, computed, shallowRef, watch, onMounted, onUnmounted, getCurrentInstance } from 'vue'
import { useMoneyStore } from './stores/money.js'
import { APP_VERSION, BUILD_TIME } from './lib/version.js'
import EntryPage from './pages/EntryPage.vue'
import StatsPage from './pages/StatsPage.vue'
import ChartPage from './pages/ChartPage.vue'
import CategoryPage from './pages/CategoryPage.vue'
import BudgetPage from './pages/BudgetPage.vue'
import AssetPage from './pages/AssetPage.vue'
import SettingsPage from './pages/SettingsPage.vue'

const store = useMoneyStore()
// setup 階段才取得得到，onMounted 的 callback 裡已經是 null
const appContext = getCurrentInstance()?.appContext
const currentTab = ref('entry')
const isDark = ref(false)
const errorCopyStatus = ref('')

const tabs = shallowRef([
  { id: 'entry', label: '記帳', component: EntryPage },
  { id: 'stats', label: '統計', component: StatsPage },
  { id: 'chart', label: '圖表', component: ChartPage },
  { id: 'category', label: '分類', component: CategoryPage },
  { id: 'budget', label: '預算', component: BudgetPage },
  { id: 'asset', label: '資產', component: AssetPage },
  { id: 'settings', label: '關於', component: SettingsPage },
])

const activeComponent = computed(
  () => tabs.value.find((t) => t.id === currentTab.value)?.component,
)

function currentPageLabel() {
  return tabs.value.find((tab) => tab.id === currentTab.value)?.label ?? currentTab.value
}

function handleWindowError(event) {
  store.recordSystemError(
    event.message || '未預期的瀏覽器錯誤',
    currentPageLabel(),
    '未處理錯誤',
    event.error?.stack || '',
  )
}

function handleUnhandledRejection(event) {
  const reason = event.reason
  store.recordSystemError(
    reason?.message || String(reason || '未處理的非同步錯誤'),
    currentPageLabel(),
    '非同步錯誤',
    reason?.stack || '',
  )
}

// Vue 的 render / watcher 錯誤不會冒泡到 window.onerror——Vue 自己接住後只印 console。
// 少了這層，元件 render 爆掉時畫面一片空白，錯誤回報卻一個字都沒有，等於白當機。
function handleVueError(err, _instance, info) {
  console.error(err)   // 保留 Vue 原本的 console 輸出，不要因為接管而變安靜
  store.recordSystemError(
    err?.message || String(err || '未預期的畫面錯誤'),
    currentPageLabel(),
    '畫面錯誤',
    [info, err?.stack].filter(Boolean).join('\n'),
    { context: 'vue:' + info },
  )
}

onMounted(() => {
  isDark.value = localStorage.getItem('theme') === 'dark'
  window.addEventListener('error', handleWindowError)
  window.addEventListener('unhandledrejection', handleUnhandledRejection)
  if (appContext) appContext.app.config.errorHandler = handleVueError
})

onUnmounted(() => {
  window.removeEventListener('error', handleWindowError)
  window.removeEventListener('unhandledrejection', handleUnhandledRejection)
})

watch(isDark, (v) => {
  document.documentElement.classList.toggle('dark', v)
  localStorage.setItem('theme', v ? 'dark' : 'light')
}, { immediate: true })

watch(() => store.error, (message) => {
  if (message) store.recordSystemError(message, currentPageLabel())
})

// 跨頁切換 tab（StatsPage 點修改 → 切到 EntryPage）
watch(() => store.requestTabSwitch, (v) => {
  if (v) {
    currentTab.value = v
    store.clearTabSwitch()
  }
})

const fileInputRef = ref(null)

function pickFile() {
  store.openFile()
}

// showOpenFilePicker 失敗時的備援：改用 <input type="file">（唯讀，無法存回磁碟）
function pickFileFallback() {
  fileInputRef.value?.click()
}

function onFileInputChange(e) {
  const file = e.target.files?.[0]
  if (file) store.openFileFromBlob(file)
  e.target.value = ''   // 重設，才能重複選同一個檔
}

// 拖曳進入視窗時登入頁的投放區要亮起來；dragenter/dragleave 會在子元素間重複觸發，用計數器抵銷
const dragDepth = ref(0)
const isDragging = computed(() => dragDepth.value > 0)

function onDrop(e) {
  e.preventDefault()
  dragDepth.value = 0
  store.openFileFromDrop(e.dataTransfer)
}

// build 時間（ISO）轉成當地時間顯示；dev 模式沒有注入時間就原樣顯示
const buildTimeLabel = computed(() => {
  const d = new Date(BUILD_TIME)
  return Number.isNaN(d.getTime())
    ? BUILD_TIME
    : d.toLocaleString('zh-TW', { hour12: false, dateStyle: 'short', timeStyle: 'short' })
})

const landingFeatures = [
  { icon: 'M12 11c0-1.1.9-2 2-2h0a2 2 0 0 1 2 2v2H8v-2a2 2 0 0 1 2-2h0M6 13h12v6H6z', label: '資料不上傳', desc: '全部在瀏覽器內運算' },
  { icon: 'M4 12l5 5L20 6', label: '直接存回原檔', desc: '每次修改自動寫回' },
  { icon: 'M4 6h16M4 12h16M4 18h10', label: '相容豬頭記帳', desc: '沿用舊版資料庫格式' },
]

// 登出：關閉檔案回登入頁；還有沒寫進磁碟的修改時先確認，避免無聲丟資料
async function logout() {
  if (!(await store.closeFile())) {
    if (!window.confirm('目前有尚未寫入磁碟的修改，登出後會遺失。確定要登出嗎？')) return
    await store.closeFile({ force: true })
  }
  currentTab.value = 'entry'
}

function switchTab(id) {
  currentTab.value = id
  store.checkDiskReload()
}

async function copyLatestErrorReport() {
  const report = store.errorReports.find((item) => item.message === store.error)
    ?? store.recordSystemError(store.error, currentPageLabel())
  if (!report) return
  try {
    await navigator.clipboard.writeText(store.formatSystemErrorReport(report))
    errorCopyStatus.value = '已複製'
  } catch {
    errorCopyStatus.value = '複製失敗'
  }
  setTimeout(() => { errorCopyStatus.value = '' }, 2000)
}

function openErrorReports() {
  currentTab.value = 'settings'
}
</script>

<template>
  <div
    class="flex flex-col h-screen"
    @dragenter.prevent="dragDepth++"
    @dragleave="dragDepth = Math.max(0, dragDepth - 1)"
    @dragover.prevent
    @drop="onDrop"
  >
    <header class="flex items-end gap-0 px-3 pt-1 bg-zinc-100 dark:bg-zinc-900 border-b border-zinc-300 dark:border-zinc-700">
      <h1 class="text-base font-semibold mr-4 pb-2 self-center text-zinc-700 dark:text-zinc-200">家庭記帳本</h1>

      <nav class="flex gap-0.5">
        <button
          v-for="t in tabs"
          :key="t.id"
          class="tab"
          :class="{ active: currentTab === t.id }"
          :disabled="!store.db && t.id !== 'settings'"
          @click="switchTab(t.id)"
        >
          {{ t.label }}
        </button>
      </nav>

      <div class="ml-auto flex items-center gap-2 pb-1.5 self-center">
        <span v-if="store.unsavedConflict" class="text-xs text-amber-500" title="檔案被外部修改，且本機有未存檔修改，已停止自動重載">⚠ 未存檔衝突</span>
        <span v-if="store.diskReloaded" class="text-xs text-cyan-500">↻ 已同步</span>
        <span v-else-if="store.lastSaved" class="text-xs text-emerald-600 dark:text-emerald-400">
          已存 {{ store.lastSaved }}
        </span>
        <span v-else-if="store.fileName" class="text-xs text-zinc-500 dark:text-zinc-400">
          {{ store.fileName }}
        </span>
        <span v-if="store.pickerFailed && store.db" class="text-xs text-amber-600 dark:text-amber-400">
          選檔被瀏覽器中止，請改拖曳檔案到視窗
        </span>
        <button class="btn" @click="pickFile">
          {{ store.fileName ? '更換檔案' : '開啟 .sqlite' }}
        </button>
        <button v-if="store.db" class="btn" title="關閉檔案並回到登入頁" @click="logout">登出</button>
        <!-- showOpenFilePicker 被 Chrome 中止後顯示，提供 <input type="file"> 備援 -->
        <button
          v-if="store.pickerFailed"
          class="btn btn-primary"
          :disabled="store.loading"
          @click="pickFileFallback"
        >
          換用傳統選檔
        </button>
        <button
          class="btn"
          :title="isDark ? '切到亮色' : '切到暗色'"
          @click="isDark = !isDark"
        >
          {{ isDark ? '☀' : '☾' }}
        </button>
      </div>
    </header>

    <div v-if="store.loading" class="p-2 text-sm text-zinc-500">載入中…</div>
    <div v-if="store.error" class="m-3 p-2 rounded border border-red-300 bg-red-50 dark:bg-red-900/20 dark:border-red-700 text-red-800 dark:text-red-300 text-sm flex items-center gap-2">
      <span class="flex-1">{{ store.error }}</span>
      <span v-if="errorCopyStatus" class="text-xs">{{ errorCopyStatus }}</span>
      <button class="btn !text-[11px] !py-0.5 !px-2" @click="copyLatestErrorReport">複製回報</button>
      <button class="btn !text-[11px] !py-0.5 !px-2" @click="openErrorReports">查看紀錄</button>
      <button class="btn !text-[11px] !py-0.5 !px-2" title="關閉錯誤訊息" @click="store.dismissError()">關閉</button>
    </div>

    <main class="flex-1 min-h-0 overflow-hidden bg-white dark:bg-zinc-950">
      <!-- 登入頁：未載入資料庫時的首頁，主動作是「拖曳 / 選擇 .sqlite」 -->
      <div
        v-if="!store.db && currentTab !== 'settings'"
        class="landing h-full overflow-y-auto flex px-4 py-8"
      >
        <div class="w-full max-w-xl m-auto">
          <!-- 品牌 -->
          <div class="text-center mb-6">
            <div class="mx-auto mb-3 w-14 h-14 rounded-2xl bg-gradient-to-br from-blue-500 to-indigo-600 shadow-lg shadow-blue-500/30 flex items-center justify-center">
              <svg viewBox="0 0 24 24" class="w-8 h-8 text-white" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                <ellipse cx="12" cy="6" rx="7" ry="3" />
                <path d="M5 6v6c0 1.7 3.1 3 7 3s7-1.3 7-3V6" />
                <path d="M5 12v6c0 1.7 3.1 3 7 3s7-1.3 7-3v-6" />
              </svg>
            </div>
            <h2 class="text-2xl font-bold tracking-tight text-zinc-800 dark:text-zinc-100">家庭記帳本</h2>
            <p class="mt-1 text-sm text-zinc-500 dark:text-zinc-400">豬頭記帳網頁版 · 記帳、預算、資產與圖表分析</p>
          </div>

          <!-- 投放區：整個視窗都能放，這裡負責視覺回饋 -->
          <div
            class="dropzone rounded-2xl border-2 border-dashed p-8 text-center transition-colors"
            :class="isDragging
              ? 'border-blue-500 bg-blue-50 dark:bg-blue-950/40'
              : 'border-zinc-300 dark:border-zinc-700 bg-zinc-50/70 dark:bg-zinc-900/60'"
          >
            <svg viewBox="0 0 24 24" class="mx-auto w-10 h-10 mb-3 transition-colors" :class="isDragging ? 'text-blue-500' : 'text-zinc-400'" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
              <path d="M12 16V4m0 0L7 9m5-5 5 5" />
              <path d="M4 16v3a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-3" />
            </svg>
            <p class="text-base font-medium text-zinc-700 dark:text-zinc-200">
              {{ isDragging ? '放開滑鼠，開始載入' : '把 money*.sqlite 拖到這裡' }}
            </p>
            <p class="mt-1 text-xs text-zinc-400">拖曳開啟的檔案可直接存回原檔</p>

            <div class="my-4 flex items-center gap-3 text-xs text-zinc-400" aria-hidden="true">
              <span class="flex-1 h-px bg-zinc-200 dark:bg-zinc-700"></span>或<span class="flex-1 h-px bg-zinc-200 dark:bg-zinc-700"></span>
            </div>

            <button class="btn btn-primary !px-6 !py-2 !text-sm !rounded-lg" :disabled="store.loading" @click="pickFile">
              <svg v-if="store.loading" class="animate-spin w-4 h-4 mr-2" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                <circle cx="12" cy="12" r="9" stroke="currentColor" stroke-width="3" opacity="0.25" />
                <path d="M21 12a9 9 0 0 0-9-9" stroke="currentColor" stroke-width="3" stroke-linecap="round" />
              </svg>
              {{ store.loading ? '載入中…' : '選擇 .sqlite 檔案' }}
            </button>
          </div>

          <!-- 選檔視窗被瀏覽器中止（Chrome 157 已知問題）時的引導 -->
          <div
            v-if="store.pickerFailed"
            class="mt-4 rounded-xl border border-amber-300 dark:border-amber-700 bg-amber-50 dark:bg-amber-900/20 p-4 text-left text-xs leading-relaxed text-amber-800 dark:text-amber-300"
          >
            <p class="font-semibold mb-1">選檔視窗被瀏覽器中止（Chrome 157 已知問題）</p>
            <p>
              請改<strong>把 .sqlite 檔拖進這個視窗</strong>，一樣可以存檔。
              下方「傳統選檔」只能唯讀，改動不會寫回檔案。
            </p>
            <!-- showOpenFilePicker 失敗後備援，唯讀，不支援自動存檔 -->
            <button
              class="mt-2 underline underline-offset-2 hover:no-underline disabled:opacity-50"
              :disabled="store.loading"
              @click="pickFileFallback"
            >
              換用傳統選檔（唯讀）
            </button>
          </div>

          <!-- 特色 -->
          <ul class="mt-6 grid grid-cols-1 sm:grid-cols-3 gap-3">
            <li
              v-for="f in landingFeatures"
              :key="f.label"
              class="flex sm:flex-col items-center sm:items-center gap-3 sm:gap-1.5 rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 px-3 py-3 text-left sm:text-center"
            >
              <svg viewBox="0 0 24 24" class="w-5 h-5 shrink-0 text-blue-600 dark:text-blue-400" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                <path :d="f.icon" />
              </svg>
              <div>
                <p class="text-[13px] font-medium text-zinc-700 dark:text-zinc-200">{{ f.label }}</p>
                <p class="text-[11px] text-zinc-400">{{ f.desc }}</p>
              </div>
            </li>
          </ul>

          <p class="mt-6 text-center text-[11px] text-zinc-400">
            v{{ APP_VERSION }} · build {{ buildTimeLabel }} · 需使用 Chrome 或 Edge
          </p>
        </div>
      </div>

      <keep-alive v-else>
        <component :is="activeComponent" :key="currentTab" />
      </keep-alive>
    </main>

    <!-- showOpenFilePicker 備援：由 pickFileFallback() 觸發，使用者不直接看到 -->
    <input
      ref="fileInputRef"
      type="file"
      accept=".sqlite,.db"
      class="hidden"
      @change="onFileInputChange"
    />
  </div>
</template>
