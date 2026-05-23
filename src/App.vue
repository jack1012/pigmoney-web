<script setup>
import { ref, computed, shallowRef, watch, onMounted } from 'vue'
import { useMoneyStore } from './stores/money.js'
import EntryPage from './pages/EntryPage.vue'
import StatsPage from './pages/StatsPage.vue'
import ChartPage from './pages/ChartPage.vue'
import CategoryPage from './pages/CategoryPage.vue'
import BudgetPage from './pages/BudgetPage.vue'
import SettingsPage from './pages/SettingsPage.vue'

const store = useMoneyStore()
const currentTab = ref('entry')
const isDark = ref(false)

const tabs = shallowRef([
  { id: 'entry', label: '記帳', component: EntryPage },
  { id: 'stats', label: '統計', component: StatsPage },
  { id: 'chart', label: '圖表', component: ChartPage },
  { id: 'category', label: '分類', component: CategoryPage },
  { id: 'budget', label: '預算', component: BudgetPage },
  { id: 'settings', label: '關於', component: SettingsPage },
])

const activeComponent = computed(
  () => tabs.value.find((t) => t.id === currentTab.value)?.component,
)

onMounted(() => {
  isDark.value = localStorage.getItem('theme') === 'dark'
})

watch(isDark, (v) => {
  document.documentElement.classList.toggle('dark', v)
  localStorage.setItem('theme', v ? 'dark' : 'light')
}, { immediate: true })

// 跨頁切換 tab（StatsPage 點修改 → 切到 EntryPage）
watch(() => store.requestTabSwitch, (v) => {
  if (v) {
    currentTab.value = v
    store.clearTabSwitch()
  }
})

function pickFile() {
  store.openFile()
}

function switchTab(id) {
  currentTab.value = id
}
</script>

<template>
  <div class="flex flex-col h-screen">
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
        <span v-if="store.lastSaved" class="text-xs text-emerald-600 dark:text-emerald-400">
          已存 {{ store.lastSaved }}
        </span>
        <span v-else-if="store.fileName" class="text-xs text-zinc-500 dark:text-zinc-400">
          {{ store.fileName }}
        </span>
        <button class="btn" @click="pickFile">
          {{ store.fileName ? '更換檔案' : '開啟 .sqlite' }}
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
    <div v-if="store.error" class="m-3 p-2 rounded border border-red-300 bg-red-50 dark:bg-red-900/20 dark:border-red-700 text-red-800 dark:text-red-300 text-sm">
      {{ store.error }}
    </div>

    <main class="flex-1 min-h-0 overflow-hidden bg-white dark:bg-zinc-950">
      <div
        v-if="!store.db && currentTab !== 'settings'"
        class="h-full flex items-center justify-center text-zinc-500"
      >
        <div class="text-center">
          <p class="mb-3 text-sm">請先到「關於」分頁載入 money*.sqlite 檔</p>
          <button class="btn btn-primary" @click="currentTab = 'settings'">
            前往關於
          </button>
        </div>
      </div>

      <keep-alive v-else>
        <component :is="activeComponent" :key="currentTab" />
      </keep-alive>
    </main>
  </div>
</template>
