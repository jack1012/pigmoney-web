<script setup>
import { useMoneyStore } from '../stores/money.js'

const store = useMoneyStore()

function errorTime(value) {
  return new Date(value).toLocaleString('zh-TW', {
    month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit',
  })
}

async function copyErrorReport(report) {
  try {
    await navigator.clipboard.writeText(store.formatSystemErrorReport(report))
  } catch {
    alert('複製失敗，請改用「匯出全部」下載文字檔')
  }
}

function exportErrorReports() {
  const content = store.errorReports
    .map((report) => store.formatSystemErrorReport(report))
    .join('\n\n------------------------------\n\n')
  const blob = new Blob([content], { type: 'text/plain;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `pigmoney-error-reports-${new Date().toISOString().slice(0, 10)}.txt`
  link.click()
  URL.revokeObjectURL(url)
}

function clearErrorReports() {
  if (confirm('確定清除全部系統錯誤紀錄？')) store.clearSystemErrorReports()
}

function exportReportSource() {
  store.loadAllBudgets()
  const payload = {
    packageType: 'pigmoney-source',
    schemaVersion: 1,
    generatedAt: new Date().toISOString(),
    transactions: store.transactions,
    classes: store.classes,
    subjects: store.subjects,
    classBuckets: store.classBuckets,
    assetAccounts: store.assetAccounts,
    assetSnapshots: store.assetSnapshots,
    budgetItems: store.allBudgetItems,
  }
  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `pigmoney-source-${new Date().toISOString().slice(0, 10)}.json`
  link.click()
  URL.revokeObjectURL(url)
}
</script>

<template>
  <div class="p-3">

    <!-- 2×2 全頁：Cell 1~4 等高 -->
    <div class="grid grid-cols-2 grid-rows-2 gap-3 h-[calc(100vh-1.5rem)]">

      <!-- Cell 1：資料庫 + 資料庫狀態（並列）+ 各頁面說明（下方）-->
      <div class="flex flex-col gap-3 h-full min-h-0">
        <!-- 資料庫 | 資料庫狀態 並列 -->
        <div class="flex-none grid grid-cols-2 gap-3 items-start">
          <section class="panel">
            <span class="panel-title">資料庫</span>
            <div class="grid grid-cols-12 gap-x-3 gap-y-2 items-center text-[13px]">
              <label class="field-label col-span-2 text-right whitespace-nowrap">目前載入:</label>
              <code class="col-span-10 text-[12px] text-zinc-700 dark:text-zinc-300 truncate">
                {{ store.fileName || '（尚未載入）' }}
              </code>

              <div class="col-span-12 flex gap-1.5 flex-wrap">
                <button class="btn btn-primary !text-[11px] !py-0.5 !px-2" @click="store.openFile()">載入 .sqlite 檔</button>
                <button class="btn !text-[11px] !py-0.5 !px-2" :disabled="!store.fileHandle" @click="store.saveFile()">手動存檔</button>
                <span v-if="store.lastSaved" class="text-[11px] text-emerald-600 dark:text-emerald-400 self-center">
                  已存 {{ store.lastSaved }}
                </span>
                <button class="btn !text-[11px] !py-0.5 !px-2" :disabled="!store.db" @click="exportReportSource">匯出年報資料</button>
                <button class="btn !text-[11px] !py-0.5 !px-2" disabled>匯出 Excel</button>
              </div>
            </div>
          </section>

          <section v-if="store.db" class="panel">
            <span class="panel-title">資料庫狀態</span>
            <dl class="grid grid-cols-[auto_1fr] gap-y-1 text-[13px]">
              <dt class="text-zinc-500 pr-3">交易筆數</dt>
              <dd>{{ store.transactions.length }} 筆</dd>
              <dt class="text-zinc-500 pr-3">類別數量</dt>
              <dd>{{ store.classes.length }} 個</dd>
              <dt class="text-zinc-500 pr-3">子項目數量</dt>
              <dd>{{ store.subjects.length }} 個</dd>
            </dl>
          </section>

          <section class="panel col-span-2">
            <div class="flex items-center gap-2 mb-1.5">
              <span class="panel-title !mb-0">系統錯誤回報</span>
              <span class="text-[11px] text-zinc-400">保留最近 {{ store.errorReports.length }} / 20 筆</span>
              <div class="ml-auto flex gap-1.5">
                <button class="btn !text-[11px] !py-0.5 !px-2" :disabled="!store.errorReports.length" @click="exportErrorReports">匯出全部</button>
                <button class="btn !text-[11px] !py-0.5 !px-2" :disabled="!store.errorReports.length" @click="clearErrorReports">清除</button>
              </div>
            </div>
            <p v-if="!store.errorReports.length" class="text-[11px] text-zinc-400">
              目前沒有錯誤紀錄。錯誤只保存在這台瀏覽器，不會自動上傳。
            </p>
            <div v-else class="max-h-24 overflow-y-auto space-y-1 pr-1">
              <div
                v-for="report in store.errorReports"
                :key="report.id"
                class="grid grid-cols-[105px_55px_1fr_auto] gap-2 items-center text-[11px] border-b border-zinc-100 dark:border-zinc-700 pb-1"
              >
                <span class="text-zinc-400">{{ errorTime(report.occurredAt) }}</span>
                <span class="text-zinc-500">{{ report.page }}</span>
                <span class="truncate text-red-600 dark:text-red-400" :title="report.message">{{ report.message }}</span>
                <button class="btn !text-[10px] !py-0 !px-1.5" @click="copyErrorReport(report)">複製</button>
              </div>
            </div>
          </section>
        </div>

        <!-- 各頁面說明 -->
        <section class="panel flex-1 flex flex-col min-h-0 overflow-hidden">
          <span class="panel-title">📚 各頁面說明</span>
          <div class="text-[12px] text-zinc-600 dark:text-zinc-400 space-y-2.5 flex-1 min-h-0 overflow-y-auto pr-1 mt-1">

            <div class="flex gap-2 items-start">
              <span class="shrink-0 font-semibold text-emerald-600 dark:text-emerald-400 w-10">記帳</span>
              <span>日常收支入帳工具。選擇類別與子項目、輸入金額（支援四則運算）、選擇交易類型後送出。新增/修改/刪除後即時寫回 .sqlite。</span>
            </div>

            <div class="flex gap-2 items-start">
              <span class="shrink-0 font-semibold text-blue-500 w-10">統計</span>
              <span>流水帳瀏覽與修改。左側樹狀導覽（年份模式 / 類別模式）篩選，右側 AG Grid 表格可直接編修。支援期間篩選、類型快篩（實際支出 / 實際收入 / 資金轉移 / 資金回收）。</span>
            </div>

            <div class="flex gap-2 items-start">
              <span class="shrink-0 font-semibold text-purple-500 w-10">圖表</span>
              <span>視覺化財務分析。Tab A 當年分析：KPI 綜覽、月別收支/投資/現金變動、支出明細與 Top 10。Tab B 歷年趨勢：跨年收支/淨投資折線、收入結構、現金使用趨勢、年度數據比對表。</span>
            </div>

            <div class="flex gap-2 items-start">
              <span class="shrink-0 font-semibold text-amber-500 w-10">分類</span>
              <span>管理類別與子項目的樹狀結構。支援新增、修改、刪除、排序（上移/下移/儲存）、設定檔 JSON 匯出與匯入。</span>
            </div>

            <div class="flex gap-2 items-start">
              <span class="shrink-0 font-semibold text-rose-500 w-10">預算</span>
              <span>設定各類別與子項目的年度預算目標。樹狀表格即時計算，可一鍵將統計歷史數據填入作為初始預算。圖表頁的實際支出圖表會對照此處設定值。</span>
            </div>

            <div class="flex gap-2 items-start">
              <span class="shrink-0 font-semibold text-cyan-500 w-10">資產</span>
              <span>追蹤每月底資產快照（現金、股票、房產、負債）。KPI 顯示淨資產與各類資產總值，折線圖呈現月度變化趨勢。快照資料也是圖表頁「實際現金變動」的計算來源。</span>
            </div>

            <div class="flex gap-2 items-start">
              <span class="shrink-0 font-semibold text-zinc-500 w-10">關於</span>
              <span>資料庫操作（載入/存檔）、資料庫狀態、本頁說明、財務專有名詞定義、開發日誌與開發清單。</span>
            </div>

          </div>
        </section>
      </div><!-- /Cell 1 -->

      <!-- Cell 2：專有名詞說明 -->
      <section class="panel h-full flex flex-col min-h-0 overflow-hidden">
        <span class="panel-title">📖 專有名詞說明</span>
        <div class="text-[12px] text-zinc-600 dark:text-zinc-400 space-y-3 flex-1 min-h-0 overflow-y-auto pr-1">

          <!-- 觀測視角說明（全寬） -->
          <div class="grid grid-cols-2 gap-x-3 gap-y-0.5 text-[11px]">
            <div class="flex gap-1.5 items-start">
              <span class="font-semibold text-blue-500 whitespace-nowrap mt-0.5">實際（Cash-based）</span>
              <span class="text-zinc-400">銀行帳戶現金進出，日常記帳用</span>
            </div>
            <div class="flex gap-1.5 items-start">
              <span class="font-semibold text-purple-500 whitespace-nowrap mt-0.5">實質（Accrual-based）</span>
              <span class="text-zinc-400">穿透現金看財富結構，年底財報用</span>
            </div>
          </div>

          <!-- 兩軌並排 -->
          <div class="grid grid-cols-2 gap-3">
            <!-- 左：實質改變軌道 -->
            <div class="space-y-1.5">
              <p class="text-[10px] text-zinc-400 font-medium uppercase tracking-wide">① 實質改變軌道（影響淨資產）</p>
              <div class="rounded border-l-2 border-emerald-400 pl-2 py-0.5 bg-emerald-50 dark:bg-emerald-950/30">
                <div class="font-semibold text-emerald-600 dark:text-emerald-400 text-[11px]">實際收入　<span class="font-normal text-zinc-400">Real Income</span></div>
                <div class="text-[10px] leading-relaxed text-zinc-500">外部資金流入，淨資產增加。薪水、獎金、股利、利息。</div>
              </div>
              <div class="rounded border-l-2 border-red-400 pl-2 py-0.5 bg-red-50 dark:bg-red-950/30">
                <div class="font-semibold text-red-500 text-[11px]">實際支出　<span class="font-normal text-zinc-400">Actual Expense</span></div>
                <div class="text-[10px] leading-relaxed text-zinc-500">現金流出永遠消失，淨資產縮水。衣食住行、稅費、房貸利息。</div>
              </div>
            </div>

            <!-- 右：資金搬家軌道 -->
            <div class="space-y-1.5">
              <p class="text-[10px] text-zinc-400 font-medium uppercase tracking-wide">② 資金搬家軌道（不影響淨資產）</p>
              <div class="rounded border-l-2 border-orange-400 pl-2 py-0.5 bg-orange-50 dark:bg-orange-950/30">
                <div class="font-semibold text-orange-500 text-[11px]">資金轉移　<span class="font-normal text-zinc-400">Capital Transfer</span></div>
                <div class="text-[10px] leading-relaxed text-zinc-500">現金移往投資或消滅負債，淨資產不變。買股票、還房貸本金。</div>
              </div>
              <div class="rounded border-l-2 border-violet-400 pl-2 py-0.5 bg-violet-50 dark:bg-violet-950/30">
                <div class="font-semibold text-violet-500 text-[11px]">資金回收　<span class="font-normal text-zinc-400">Capital Recovery</span></div>
                <div class="text-[10px] leading-relaxed text-zinc-500">投出的本金變現回到現金，淨資產不變。賣股本金、收回借款。</div>
              </div>
            </div>
          </div>

          <!-- 衍生指標（對齊上方兩欄） -->
          <div class="border-t border-zinc-100 dark:border-zinc-700 pt-2 grid grid-cols-2 gap-x-3 text-[11px]">
            <!-- 左：對齊①實質改變軌道 -->
            <div class="space-y-1.5">
              <div class="rounded border-l-2 border-amber-400 pl-2 py-0.5 bg-amber-50 dark:bg-amber-950/30">
                <div class="font-semibold text-amber-500">淨收益　<span class="font-normal text-zinc-400">Net Surplus</span></div>
                <div class="text-[10px] text-zinc-500">= 實際收入 − 實際支出</div>
              </div>
              <div class="rounded border-l-2 border-cyan-400 pl-2 py-0.5 bg-cyan-50 dark:bg-cyan-950/30">
                <div class="font-semibold text-cyan-500">實際現金變動　<span class="font-normal text-zinc-400">Cash Change</span></div>
                <div class="text-[10px] text-zinc-500">= 年底現金快照 − 年初現金快照　<span class="text-zinc-400">（實際量到）</span></div>
              </div>
            </div>
            <!-- 右：對齊②資金搬家軌道 -->
            <div class="space-y-1.5">
              <div class="rounded border-l-2 border-purple-400 pl-2 py-0.5 bg-purple-50 dark:bg-purple-950/30">
                <div class="font-semibold text-purple-500">淨投資　<span class="font-normal text-zinc-400">Net Investment</span></div>
                <div class="text-[10px] text-zinc-500">= 資金轉移 − 資金回收</div>
              </div>
              <div class="rounded border-l-2 border-teal-400 pl-2 py-0.5 bg-teal-50 dark:bg-teal-950/30">
                <div class="font-semibold text-teal-500">實際資金變動　<span class="font-normal text-zinc-400">Asset Change</span></div>
                <div class="text-[10px] text-zinc-500">= 實際現金變動 + 股票增減　<span class="text-zinc-400">（快照合計）</span></div>
              </div>
            </div>
          </div>

          <!-- 對帳工具 -->
          <div class="border-t border-zinc-100 dark:border-zinc-700 pt-2 text-[11px]">
            <p class="text-[10px] text-zinc-400 font-medium uppercase tracking-wide mb-1.5">④ 對帳工具</p>
            <div class="rounded border border-dashed border-zinc-300 dark:border-zinc-600 pl-2 pr-3 py-1.5 bg-zinc-50 dark:bg-zinc-800/40">
              <div class="flex flex-wrap gap-x-3 gap-y-0.5 items-baseline">
                <span class="font-semibold text-zinc-600 dark:text-zinc-300 whitespace-nowrap">理論實際現金變動</span>
                <span class="text-zinc-400">= 淨收益 − 淨投資　<span class="text-zinc-300 dark:text-zinc-600">（交易記錄推算）</span></span>
              </div>
              <div class="text-[10px] text-zinc-500 mt-0.5 leading-relaxed">
                根據 DB 已記錄的交易，理論上現金應該變動多少。<br>
                <span class="font-medium text-zinc-600 dark:text-zinc-400">實際現金變動 − 理論實際現金變動 = 未記錄的現金流</span>（如定期定額薪資直扣、現金交易漏記）。<br>
                兩者差距越大，代表帳目越不完整。
              </div>
            </div>
          </div>

          <!-- 備註 -->
          <div class="text-[10px] text-zinc-400">
            💡 定期定額投資由薪資直接扣款（不經銀行），故實際收入 = 實領薪資；年底財報補認列實質收入（含扣款）。
          </div>
        </div>
      </section>

      <!-- Cell 3：開發日誌 -->
      <section class="panel h-full flex flex-col min-h-0 overflow-hidden">
        <span class="panel-title">開發日誌</span>
        <div class="text-[12px] text-zinc-600 dark:text-zinc-400 space-y-3 flex-1 min-h-0 overflow-y-auto pr-1">
          <p class="font-medium text-zinc-800 dark:text-zinc-200">家庭記帳本 v2.1.0 (2026-07-21) — 豬頭記帳網頁版</p>

          <div class="space-y-3">
            <div>
              <p class="text-emerald-600 dark:text-emerald-400 font-semibold mb-0.5">v2.1.0 (2026-07-21) — 磁碟存檔防護與系統錯誤追蹤</p>
              <ul class="space-y-0.5 leading-relaxed pl-2">
                <li>· <strong>存檔機制強化與修復</strong>：修復 File System Access API 在背景同步或檔案狀態變更時發生的 InvalidStateError（存檔失敗）錯誤</li>
                <li>· 寫入檔案前主動刷新 fileHandle 控制代碼快取狀態，並建立自動重試 (Auto-Retry) 機制</li>
                <li>· 存檔完成後同步更新磁碟修改時間戳記，避免 checkDiskReload 誤判</li>
                <li>· 整合錯誤回報紀錄與技術細節追蹤</li>
              </ul>
            </div>
            <div>
              <p class="text-blue-600 dark:text-blue-400 font-semibold mb-0.5">v2.0.0 (2026-05-23 ~ 2026-05-24) — 預算管理系統大改版與全站優化</p>
              <ul class="space-y-0.5 leading-relaxed pl-2">
                <li>· <strong>預算 schema 建立</strong>：`budget_year` / `budget_item` / `budget_project` / `budget_class_bucket` 自動建表與 migration</li>
                <li>· <strong>預算頁 BudgetPage 創立</strong>：四大桶位（生活/固定/想要/投資）、比例金額雙向綁定、樹狀表格 inline 編輯、KPI 卡片、編輯/歷年雙模式</li>
                <li>· <strong>跨頁連動編修</strong>：統計頁點擊「✏ 修改」連動帶入記帳頁；App 全站 `&lt;keep-alive&gt;` 狀態留存</li>
                <li>· <strong>全站 UI 強化與維護</strong>：全站 active 頁籤樣式、AG Grid 樣式統一、隱藏 number spinner、數字允許 0 輸入</li>
                <li>· <strong>自動化 CI/CD 部署</strong>：GitHub repository 創立與 GitHub Actions 自動建置部署至 GitHub Pages</li>
              </ul>
            </div>
            <div>
              <p class="text-purple-600 dark:text-purple-400 font-semibold mb-0.5">v1.2.0 (2026-05-31) — 全站財務術語規範與對帳系統</p>
              <ul class="space-y-0.5 leading-relaxed pl-2">
                <li>· <strong>全站財務術語統一化</strong>：建立雙軌名詞表（實際收入/實際支出、資金轉移/資金回收、淨收益/淨投資、理論現金變動/實際現金變動/實際資金變動）</li>
                <li>· <strong>圖表頁對帳雙線圖</strong>：新增「理論現金變動」（= 淨收益−淨投資 累積折線），資料表加 Δ實際 vs Δ理論 對照列</li>
                <li>· <strong>關於/設定頁重構</strong>：SettingsPage 2×2 全頁等高格局，新增專有名詞說明與對帳工具說明面板</li>
                <li>· <strong>圖表月別維度修正</strong>：月別淨收益/淨投資標籤加「(月)」、修正缺月假月減問題</li>
                <li>· <strong>資料庫清理</strong>：清理全庫重複交易，修正 32 筆類別歸類錯誤</li>
              </ul>
            </div>
            <div>
              <p class="text-amber-600 dark:text-amber-400 font-semibold mb-0.5">v1.1.0 (2026-05-25 ~ 2026-05-29) — 視覺化分析圖表與拆帳法升級</p>
              <ul class="space-y-0.5 leading-relaxed pl-2">
                <li>· <strong>圖表頁 ChartPage 建置</strong>：Chart.js 整合，包含 Tab A 當年 KPI / 月別收支 / 支出明細 / Top 10 排行與 Tab B 歷年趨勢與比對表</li>
                <li>· <strong>投資拆帳法</strong>：賣股本金改算「資金回收/轉移」，獲利/配息算「實際收入」；新增 `modeLabel.js` 映射</li>
                <li>· <strong>資產頁 AssetPage 建立</strong>：資產帳戶管理與每月 snapshot 快照追蹤</li>
                <li>· <strong>CFO 指南與文件</strong>：撰寫 README 家庭 CFO 操作指南與雙軌財報規範</li>
              </ul>
            </div>
            <div>
              <p class="text-zinc-600 dark:text-zinc-400 font-semibold mb-0.5">v1.0.0 (2026-05-20 ~ 2026-05-22) — 核心記帳與基礎架構上線</p>
              <ul class="space-y-0.5 leading-relaxed pl-2">
                <li>· <strong>基礎架構</strong>：建立 Vue 3 + Vite + Pinia 專案，整合 sql.js 瀏覽器端 WASM SQLite 資料庫</li>
                <li>· <strong>記帳頁 EntryPage</strong>：三欄式介面、四則運算求值、表單驗證、本月資料載入與編修</li>
                <li>· <strong>統計頁 StatsPage</strong>：AG Grid v35 列表、四層樹狀導覽、拖曳分隔線、編修模式與期間動態篩選</li>
                <li>· <strong>分類頁 CategoryPage</strong>：類別與子項目兩層 CRUD、拖曳與按鈕排序、JSON 設定檔匯出與匯入</li>
                <li>· <strong>本機自動存檔</strong>：整合 HTML5 File System Access API 即時寫回 .sqlite 檔案</li>
              </ul>
            </div>
          </div>

          <p class="text-zinc-400">本機單一使用者模式</p>
        </div>
      </section>

      <!-- Cell 4：開發清單 -->
      <section class="panel h-full flex flex-col min-h-0 overflow-hidden">
        <span class="panel-title">開發清單</span>
        <ul class="text-[12px] space-y-1.5 leading-relaxed flex-1 min-h-0 overflow-y-auto pr-1">
          <li class="flex gap-2">
            <span class="text-emerald-600 shrink-0">✓</span>
            <span class="text-zinc-500">基礎架構（Vue 3 + Vite + Pinia）</span>
          </li>
          <li class="flex gap-2">
            <span class="text-emerald-600 shrink-0">✓</span>
            <span class="text-zinc-500">SQLite 讀取（sql.js WASM）</span>
          </li>
          <li class="flex gap-2">
            <span class="text-emerald-600 shrink-0">✓</span>
            <span class="text-zinc-500">記帳頁：新增 / 修改 / 刪除</span>
          </li>
          <li class="flex gap-2">
            <span class="text-emerald-600 shrink-0">✓</span>
            <span class="text-zinc-500">記帳頁：金額算式、表單驗證</span>
          </li>
          <li class="flex gap-2">
            <span class="text-emerald-600 shrink-0">✓</span>
            <span class="text-zinc-500">記帳頁：本月顯示、點列載入、Esc 重置</span>
          </li>
          <li class="flex gap-2">
            <span class="text-emerald-600 shrink-0">✓</span>
            <span class="text-zinc-500">統計頁：AG Grid 列表（唯讀）</span>
          </li>
          <li class="flex gap-2">
            <span class="text-emerald-600 shrink-0">✓</span>
            <span class="text-zinc-500">深色模式切換</span>
          </li>
          <li class="flex gap-2 mt-1">
            <span class="text-emerald-600 shrink-0">✓</span>
            <span class="text-zinc-500">寫回磁碟（File System Access API，自動存檔）</span>
          </li>
          <li class="flex gap-2">
            <span class="text-emerald-600 shrink-0">✓</span>
            <span class="text-zinc-500">分類頁：類別/子項目 CRUD + 排序 + 匯出/匯入</span>
          </li>
          <li class="flex gap-2">
            <span class="text-emerald-600 shrink-0">✓</span>
            <span class="text-zinc-500">統計頁：樹狀導覽 + 拖曳分隔 + 編修模式</span>
          </li>
          <li class="flex gap-2">
            <span class="text-emerald-600 shrink-0">✓</span>
            <span class="text-zinc-500">統計頁：選取高亮、期間整合、版面細節優化</span>
          </li>
          <li class="flex gap-2">
            <span class="text-emerald-600 shrink-0">✓</span>
            <span class="text-zinc-500">預算頁：KPI 卡片、桶位細項表、比例金額雙向綁定</span>
          </li>
          <li class="flex gap-2">
            <span class="text-emerald-600 shrink-0">✓</span>
            <span class="text-zinc-500">預算頁：編輯 / 歷年模式切換</span>
          </li>
          <li class="flex gap-2">
            <span class="text-emerald-600 shrink-0">✓</span>
            <span class="text-zinc-500">資產頁：快照管理（現金 / 投資 / 動產 / 負債）</span>
          </li>
          <li class="flex gap-2">
            <span class="text-emerald-600 shrink-0">✓</span>
            <span class="text-zinc-500">資產頁：編輯 / 歷年模式切換</span>
          </li>
          <li class="flex gap-2">
            <span class="text-emerald-600 shrink-0">✓</span>
            <span class="text-zinc-500">GitHub Pages 部署（push 自動更新）</span>
          </li>
          <li class="flex gap-2">
            <span class="text-emerald-600 shrink-0">✓</span>
            <span class="text-zinc-500">圖表頁 Tab A：KPI 四卡 + 預算 vs 實際 + 月別收支 + 細部 tab + 支出/收入明細 + Top 10</span>
          </li>
          <li class="flex gap-2">
            <span class="text-emerald-600 shrink-0">✓</span>
            <span class="text-zinc-500">圖表頁 Tab B：歷年收支結餘 3 圖 + 大類年際趨勢 + 年度數據比對表</span>
          </li>
          <li class="flex gap-2">
            <span class="text-emerald-600 shrink-0">✓</span>
            <span class="text-zinc-500">資料補錄：歷史投資交易整理與核對</span>
          </li>
          <li class="flex gap-2">
            <span class="text-emerald-600 shrink-0">✓</span>
            <span class="text-zinc-500">全站財務術語統一化（實際收入/支出、資金轉移/回收、淨收益/淨投資、理論現金變動/實際現金變動/實際資金變動）</span>
          </li>
          <li class="flex gap-2">
            <span class="text-emerald-600 shrink-0">✓</span>
            <span class="text-zinc-500">圖表頁：全面術語更名 + 現金變動雙線圖（Δ實際 vs Δ理論）</span>
          </li>
          <li class="flex gap-2">
            <span class="text-emerald-600 shrink-0">✓</span>
            <span class="text-zinc-500">關於頁：2×2 等高格局 + 各頁面說明 + 專有名詞說明面板</span>
          </li>
          <li class="flex gap-2">
            <span class="text-emerald-600 shrink-0">✓</span>
            <span class="text-zinc-500">DB 清理：32 筆 mode=現金支出/cno=13 錯誤歸類修正</span>
          </li>
          <li class="flex gap-2">
            <span class="text-emerald-600 shrink-0">✓</span>
            <span class="text-zinc-500">圖表頁：月別淨收益/淨投資 — 標籤加「(月)」+ 資料表改月度值 + 修正缺月假月減 + 淨收益回歸「實際收入−實際支出」</span>
          </li>
          <li class="flex gap-2">
            <span class="text-emerald-600 shrink-0">✓</span>
            <span class="text-zinc-500">存檔機制：File System Access API 快取刷新與寫入自動重試修復 (v0.1.1 2026-07-21)</span>
          </li>
          <li class="flex gap-2 mt-2">
            <span class="text-blue-500 shrink-0">▶</span>
            <span class="text-zinc-700 dark:text-zinc-200 font-medium">圖表頁 Tab B 歷年趨勢 深化</span>
          </li>
          <li class="flex gap-2 mt-2">
            <span class="text-blue-500 shrink-0">▶</span>
            <span class="text-zinc-700 dark:text-zinc-200 font-medium">投資真實損益區塊（年底資產年增 − 淨投入 = 已實現+未實現）</span>
          </li>
          <li class="flex gap-2">
            <span class="text-zinc-300 shrink-0">○</span>
            <span class="text-zinc-400">圖表頁：股票賣出 sno 新增（區分「投資利得」與「股票賣出」）</span>
          </li>
          <li class="flex gap-2">
            <span class="text-zinc-300 shrink-0">○</span>
            <span class="text-zinc-400">money-2.sqlite 補錄評估（449 筆獨有交易，特別是 2019 年 345 筆）</span>
          </li>
          <li class="flex gap-2">
            <span class="text-zinc-300 shrink-0">○</span>
            <span class="text-zinc-400">完整鍵盤導航（方向鍵 + Shift+Enter）</span>
          </li>
        </ul>
      </section>
    </div>
  </div>
</template>
