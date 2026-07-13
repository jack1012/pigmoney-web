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
          <p class="font-medium text-zinc-800 dark:text-zinc-200">家庭記帳本 v0.1 — 豬頭記帳網頁版</p>

          <div class="space-y-3">
            <div>
              <p class="text-zinc-400 font-medium mb-0.5">2026-05-20</p>
              <ul class="space-y-0.5 leading-relaxed pl-2">
                <li>· 建立專案（Vue 3 + Vite + Pinia）</li>
                <li>· 整合 sql.js，在瀏覽器讀取 .sqlite</li>
                <li>· 確立 6 分頁架構與整體版面</li>
                <li>· 深色模式切換（Tailwind v4 @custom-variant dark）</li>
              </ul>
            </div>
            <div>
              <p class="text-zinc-400 font-medium mb-0.5">2026-05-21</p>
              <ul class="space-y-0.5 leading-relaxed pl-2">
                <li>· 統計頁：AG Grid v35，改用 ThemeAPI 避免 CSS 衝突</li>
                <li>· 記帳頁：三欄版面（類別 / 子項目 / 輸入）</li>
                <li>· 記帳頁：金額欄支援四則運算（白名單 regex + Function 求值）</li>
                <li>· 記帳頁：表單驗證，新增寫入記憶體 DB</li>
              </ul>
            </div>
            <div>
              <p class="text-zinc-400 font-medium mb-0.5">2026-05-22</p>
              <ul class="space-y-0.5 leading-relaxed pl-2">
                <li>· 記帳頁：顯示本月資料（全月，非限 15 筆）</li>
                <li>· 記帳頁：點列載入修改、Esc 重置</li>
                <li>· 記帳頁：刪除按鈕（confirm 確認）</li>
                <li>· 設定頁：開發日誌 + 開發清單</li>
                <li>· 自動存檔：新增/修改/刪除後即時寫回本機 .sqlite（File System Access API）</li>
                <li>· 統計頁：左側四層樹狀導覽（年份模式 / 類別模式）</li>
                <li>· 統計頁：左右面板可拖曳分隔線，預設 1:2 比例</li>
                <li>· 統計頁：支出 / 收入快速切換篩選</li>
                <li>· 統計頁：AG Grid 編修模式（類別下拉、金額、備註直接修改）</li>
                <li>· 統計頁：期間篩選（當年度 / 歷年度 / 年度區間）</li>
                <li>· 統計頁：選中列藍底反白；格子框瀏覽藍 / 編修紅（2px outline）</li>
                <li>· 統計頁：年份輸入框常駐，僅允許正整數（即時清洗）</li>
                <li>· 統計頁：預設年份區間為當年度</li>
                <li>· 統計頁：左側樹狀預設展開第一層（載入及切換模式時）</li>
                <li>· 統計頁：期間按鈕與年份輸入整合同組，點按鈕更新輸入框</li>
                <li>· 統計頁：操作列（瀏覽/編修）移至摘要列上方</li>
                <li>· 分類頁：類別 / 子項目兩層 CRUD（新增、修改、刪除）</li>
                <li>· 分類頁：排序（上移 / 下移 / 儲存順序 / 還原順序）</li>
                <li>· 分類頁：設定檔匯出 / 匯入（JSON，完全取代模式）</li>
                <li>· 分類頁：三欄等寬版面，listbox 隨視窗高度自動伸縮</li>
              </ul>
            </div>
            <div>
              <p class="text-zinc-400 font-medium mb-0.5">2026-05-25</p>
              <ul class="space-y-0.5 leading-relaxed pl-2">
                <li>· <strong>圖表頁 ChartPage 大幅建置 + 改造</strong>（Chart.js 整合）</li>
                <li>· Tab A 年度資料：年份 dropdown（移至 Tab 同行、遞減排列）+ KPI 四卡（收入 / 一般支出 / 投資 / 結餘）</li>
                <li>· Tab A：🎯 實際支出圖表（4 桶位）— 灰底寬柱（已設預算）+ 半透明窄柱（實際）重疊；柱頂金額標籤；超支 X 軸字變紅</li>
                <li>· Tab A：📅 月別收支（柱+結餘折線在前）— 4 series（收入/一般支出/投資/結餘）+ 下方 4 行月別數值表</li>
                <li>· Tab A：🔍 實際支出圖表 各項細部 — 4 桶位 tab 切換、每 class 不同色（12 色調色盤）</li>
                <li>· Tab A：🧾 實際支出明細表（原當年支出結構） — 加「金額/百分比」模式切換、「顯示預算」toggle、視覺化欄灰底+彩柱、加「預算」欄</li>
                <li>· Tab A：💵 實際收入明細表 — 加「預算」欄、顯示預算 toggle、視覺化欄灰底+彩柱</li>
                <li>· Tab A：🏆 Top 10 子項排行（跨類別，含大類色點）</li>
                <li>· Tab B 歷年趨勢：年度範圍選擇器（起≤訖，動態過濾選項）+ 3 個 LV2 區塊</li>
                <li>· Tab B LV2-1：📈 歷年收支結餘 — 收支柱+結餘線、儲蓄率折線、收入結構堆疊、各大類年際趨勢折線</li>
                <li>· Tab B LV2-3：📋 年度數據比對表 — 4 主指標 + 收入細項 3 行（薪資/投資獲利/其他）+ 支出 4 桶位拆解列、當年欄藍底高亮</li>
                <li>· <strong>聚焦收支主題</strong>：移除 Tab A 當年資產組成、Tab B LV2-2 歷年資產組成、LV2-3 資產 3 指標列、KPI 淨資產卡</li>
                <li>· 預算 bug 修正：sno=0（class 總額）與 sno&gt;0（子項）重複加總 — 採 BudgetPage histClassBudget 規則（優先 sno=0，無則加總 sno&gt;0）</li>
                <li>· 資產頁：編輯模式 latestDate 加「上個月底」上限（本月未到月底時 KPI 不抓未完整資料）</li>
                <li>· 資產頁：getMonthlyPlaceholder 當年度未到月份留白；既有月份顯示「~上月值」估值</li>
                <li>· 資產頁：加 inline「(改名)」按鈕，整理不動產、交通工具與折舊項目名稱</li>
                <li>· 資料補錄：補齊部分歷史投資交易，並核對對應年度的投資資產變動</li>
                <li>· 資料補錄：補齊較早年度投資交易，完成年度投資紀錄核對</li>
                <li>· 記帳哲學確立：投資採 A 法（全額進出），mode='信用卡支出' 區分資產搬移 vs 一般消費</li>
                <li>· Store 新增 ChartPage 用 SQL 聚合：yearCnoSpend / yearCnoSnoSpend / yearMonthCnoSpend / yearMonthInvest / yearInvestSpend</li>
                <li>· Chart.js valueLabelPlugin 自製 — 預算數字標柱頂上方（灰）、實際數字標柱底部</li>
              </ul>
            </div>
            <div>
              <p class="text-zinc-400 font-medium mb-0.5">2026-05-29</p>
              <ul class="space-y-0.5 leading-relaxed pl-2">
                <li>· <strong>投資記帳改用拆帳法</strong>：賣股本金 = 投資收入（資產搬移），獲利/配息 = 真實收入</li>
                <li>· DB mode 欄保留原字串（信用卡支出 / 信用卡收入）以相容豬頭記帳.exe；UI 一律顯示「投資支出 / 投資收入」</li>
                <li>· 新增 lib/modeLabel.js — MODE_LABEL 映射 / MODE_OPTIONS 下拉 / isInvestTransfer() helper</li>
                <li>· EntryPage：mode 下拉改用 MODE_OPTIONS、AG Grid 類型欄走 modeLabel</li>
                <li>· StatsPage：類型篩選加「投資收入」按鈕、AG Grid editor 加 信用卡收入 選項、類型欄 valueFormatter 走 modeLabel</li>
                <li>· ChartPage：yearInvestSpend / yearMonthInvest 改算「淨投資」= 信用卡支出 − 信用卡收入</li>
                <li>· 賣股拆兩筆：本金 → mode='信用卡收入'/cno=14/sno=101；獲利 → mode='收入'/cno=13/sno=66 資本利得</li>
                <li>· 配息/股利 → 維持 cno=13/sno=64 投資利得（既有用法不變）</li>
                <li>· <strong>資料補錄</strong>：歷年賣股逐筆拆帳，移除重複合併紀錄並修正配息誤分類</li>
                <li>· cno=22「資本損失」改名「投資損失」（sno=272 股票 / 273 基金 保留）</li>
                <li>· ChartPage：yearExpense 排除投資桶(save) + 投資損失(cno=22)，一般支出真正乾淨</li>
                <li>· ChartPage：KPI 4 卡 → 5 卡（加投資損益）；新增 yearInvestPnL = sno=64 + sno=66 − cno=22</li>
                <li>· ChartPage：實際支出明細採 curExpenseDetailGroups（排除 save + cno=22）；月別系列同步處理</li>
                <li>· ChartPage：Tab B 年度比對表「總支出」改名「一般支出」</li>
                <li>· ChartPage：EXPENSE_GROUPS 第 4 桶位「投資」→「投資損失」(cno=22)，紫色維持；4 區塊（圖表/細部/明細/月別）同步</li>
                <li>· ChartPage：月別 series invest → invloss；結餘公式改 sur = inc − exp（純消費視角）</li>
                <li>· ChartPage：curBudgetByBucket cno=22 直接歸 invloss 桶；FOUR_BUCKET_KEYS 改 'life/fixed/want'</li>
                <li>· ChartPage：新增 yearInvestLoss / yearMonthInvestLoss computed</li>
                <li>· ChartPage Tab B：「投資變化」圖改名「資金變化」（內容不變）</li>
                <li>· ChartPage Tab B 比對表大改：加「　投資損失」進一般支出細項；一般支出總額 = 生活+固定+想要+投資損失；結餘 = 收入 − 一般支出</li>
                <li>· ChartPage Tab B 比對表：移除「儲蓄率」「投資」列；新增「資金變動」+「　現金」+「　股票」3 列（年底 YoY）</li>
                <li>· ChartPage Tab B：新增 yearEndStockByYear / histStockGrowth computed</li>
                <li>· Top 10 子項排行：排除 bucket=save (cno=14 投資)</li>
                <li>· <strong>asset_account.category 合併</strong>：21 筆「現金/投資」UPDATE 為「資金」；DB schema 不變</li>
                <li>· isStockAccount(name) helper：name 含「股票/基金/保單」視為股票類</li>
                <li>· ChartPage：anoName / isStockAccount 加入；yearAssets / yearEndCashByYear / yearEndStockByYear 用 name 細分</li>
                <li>· AssetPage：byCategory 把「資金」依 name 分到邏輯桶「現金/投資」；addAccount 邏輯桶→DB category 映射；UI 仍維持 4 邏輯桶顯示</li>
                <li>· <strong>ChartPage KPI 5→4 卡</strong>：收入 / 支出 / 結餘 / 資金變化；移除「投資」「投資損益」</li>
                <li>· 「一般支出」統一改名「支出」（KPI / 月別 / Tab B 收支圖 / 比對表）</li>
                <li>· 支出定義改為 = 生活+固定+想要+投資損失（yearExpense 包含 cno=22）</li>
                <li>· 結餘公式 = 收入 − 支出；月別 sur 同步</li>
                <li>· 「資金變動」KPI = (cash + stock) YoY；過去年份用 12-31 vs 12-31（同 Tab B 比對表），當前年份 fallback 最新月度 vs 上年 12-31（KPI 副標標註日期 + 星號提示）</li>
                <li>· 全頁名稱統一「資金變動」（取代「資金變化」）：KPI 卡 + Tab B 圖 panel-title</li>
                <li>· Tab A 底部新增「💧 月別資金變動」圖：現金/投資（從 snapshot YoY）+ 實際投資買入/賣出（從 money 表 mode='信用卡支出/收入'）+ 合計線；snapshot 缺月顯示 — </li>
                <li>· 月別資金變動新增「定期定額帳戶」line series（粉 #ec4899）：追蹤專用投資帳戶月增</li>
                <li>· DB 重組（方案 A）：投資擴為「投資/資產轉換」類別；新增房貸本金與借款子項，移動親友借款及房貸紀錄；利息項目獨立保留</li>
                <li>· README 重寫：以家庭 CFO 操作指南取代舊「記帳哲學」段落；雙軌分類（紅/綠/白）+ 自由現金流 + 年度資產負債表</li>
                <li>· KPI 4 卡改名（CFO 統一名詞）：實質收入 / 實質支出 / 淨收益 / 實際現金變動；公式：淨收益 = 實質收入 − 實質支出；實際現金變動 = 淨收益 + (投資收入 − 投資支出)，純現金流不含未實現損益</li>
                <li>· Tab B 比對表名詞同步：總收入→實質收入；支出→實質支出；結餘→淨收益（「資金變動」保留，asset_snapshot 來源不同）</li>
                <li>· 補錄股票本金回流：歷年賣股本金逐筆對齊，並區分獲利與損失</li>
                <li>· 新增動產購置子項；家庭交通工具由一般專案支出改列資產搬移</li>
                <li>· overviewRows / histYearData 簡化（exp 已含 loss，不再 expWithLossAt）</li>
              </ul>
            </div>
            <div>
              <p class="text-zinc-400 font-medium mb-0.5">2026-05-24</p>
              <ul class="space-y-0.5 leading-relaxed pl-2">
                <li>· 資產頁：修正歷年模式 2026 欄位空白 — histDisplayDates 未排除 -12-31 快照，導致年底空資料被選中，現金/投資顯示「—」；補上 &amp;&amp; !date.endsWith('-12-31') 篩選</li>
                <li>· 預算頁：移除「複製上年」「統計初值」「AI 分析」按鈕</li>
                <li>· 預算頁：加入「編輯 / 歷年」模式切換（同資產頁設計）</li>
                <li>· 預算頁：歷年模式 — 跨年度橫向比較表，欄為年份，列為各桶位類別預算，含小計與總計，唯讀</li>
                <li>· Store：新增 loadAllBudgets()、allBudgetYearMetas、allBudgetItems</li>
              </ul>
            </div>
            <div>
              <p class="text-zinc-400 font-medium mb-0.5">2026-05-23</p>
              <ul class="space-y-0.5 leading-relaxed pl-2">
                <li>· 預算頁：budget schema（budget_year / budget_item / budget_project / budget_class_bucket）</li>
                <li>· 預算頁：樹狀表格 inline 編輯，支援算式</li>
                <li>· 預算頁：修正家庭成員薪資的收入歸類</li>
                <li>· 預算頁：2020–2026 年度比例設定、收入預估寫入</li>
                <li>· 預算頁：版面重整 — 收入預估（橫式）→ 年度設定 → 6 KPI → 月例行預算表</li>
                <li>· 預算頁：6 KPI 橫列，含總收入/生活/固定/想要/投資/存款推算</li>
                <li>· 預算頁：月例行預算表依四大桶位分區塊，各區塊有小計</li>
                <li>· 預算頁：年度總預算 / 收入預估輸入以萬為單位</li>
                <li>· 預算頁：KPI 進度條改為 200% 尺度，超標段紅色從中線往右延伸（兩段式 split bar）</li>
                <li>· 預算頁：年度設定改成 4列 6欄 grid（標頭/比例/金額/已設預算/KPI 對齊一致）</li>
                <li>· 預算頁：比例 ↔ 金額雙向綁定（改任一邊另一邊自動算）</li>
                <li>· 預算頁：存款推算欄三列各自計算說明（總收入−四桶位 / 100%−四桶位% / 設定預算−已設預算）</li>
                <li>· 預算頁：已設預算區塊（原月例行預算表）改為預設只顯示第一階層，每類別 ▶/▼ 展開子項目，含全部展開/收合</li>
                <li>· 預算頁：上下兩區塊以「細項預算編列」分隔線區分</li>
                <li>· 資料：合併交通工具相關項目，並正確累加 budget_item</li>
                <li>· 統計頁：編修模式加「↶ 回上一步」按鈕（undo stack 20 步）</li>
                <li>· 統計頁：刪除按鈕移到每列最左（pinned），confirm 顯示完整資訊</li>
                <li>· 記帳頁：本月清單改用 AG Grid，樣式統一同統計頁；刪除按鈕在最左；選中列藍底反白</li>
                <li>· 全站：tab active 強化（藍底 + 藍頂線 + 粗體藍字），「設定」改為「關於」</li>
                <li>· 全站：number input 隱藏上下箭頭</li>
                <li>· 全站：分頁狀態保留（keep-alive 包 component，篩選/捲動/選取切換分頁不會重置）</li>
                <li>· 統計頁：每列加「✏ 修改」按鈕（pinned right），跨頁切到記帳頁帶入該筆資料編輯</li>
                <li>· 跨頁通訊：money store 加 pendingEditMno / requestTabSwitch + 對應 actions，App 監聽切 tab、EntryPage 用 onActivated 接收</li>
                <li>· 記帳頁：金額允許 0（從 &gt; 0 改為 &ge; 0），紀錄 0 元也可以</li>
                <li>· 預算頁：細項預算編列大改版 — 設定預算/細項預算欄分流（類別/子項目 input 各自管），移除「2026 已用」、移除算式欄</li>
                <li>· 預算頁：vs 預算 → 設定 − 細項 差額（負數紅色提醒分配超支）</li>
                <li>· 預算頁：月均 fallback (設定 || 細項) / 12</li>
                <li>· 預算頁：「全部展開/全部收合」拆成兩個按鈕</li>
                <li>· 預算頁：上下兩區塊間加「細項預算編列」分隔線</li>
                <li>· 預算頁：註記欄（textarea 多行，rows 依文字行數自動調整）</li>
                <li>· DB schema：budget_item 加 note 欄位 + ALTER TABLE migration</li>
                <li>· money store：新增 upsertBudgetItemNote、exportBudgetYearJson actions</li>
                <li>· 預算頁：工具列「📥 匯出 JSON」按鈕，匯出當前年度預算（含 budget_year/budget_item/buckets + class/subject 名稱）</li>
                <li>· 資料填入：2020–2026 各年度類別設定預算 77 筆</li>
                <li>· 資料填入：2020–2026 類別 + 子項目註記（含算式/說明，多行 textarea 顯示）約 200+ 筆</li>
                <li>· 資料：教育類新增進修子項目，並調整相關預算註記</li>
                <li>· 資料重組：合併交通工具相關預算與項目，移至專案類別</li>
                <li>· 資料重組：房屋工程相關項目重新分類</li>
                <li>· 資料重組：家用設備項目合併，跨年度預算正確累加</li>
                <li>· 資料重組：合併重複的旅遊預算項目</li>
                <li>· 資料清理：刪除無交易的未使用子項目</li>
                <li>· 旅遊專案改名規則：依年份與主題統一命名</li>
                <li>· 旅遊專案拆分：歷年海外旅遊依年度拆分，刪除舊彙總子項目</li>
                <li>· 資料備份：建立預算與資料調整前的完整備份</li>
                <li>· 版本管理：git init + .gitignore（排除 *.sqlite/*.bak/截圖/個人 csv/docx/json/暫存腳本），第一個 commit 鎖住 26 個 source/config/docs</li>
                <li>· GitHub repository 建立，並完成部署權限設定</li>
                <li>· GitHub Pages 部署：vite.config.js 加 base '/pigmoney-web/'，建 .github/workflows/deploy.yml（push 到 master 自動 build + deploy）</li>
                <li>· GitHub Pages 線上版本：每次 git push 後自動更新</li>
              </ul>
            </div>
            <div>
              <p class="text-zinc-400 font-medium mb-0.5">2026-05-31</p>
              <ul class="space-y-0.5 leading-relaxed pl-2">
                <li>· <strong>全站財務術語統一化</strong>：建立 CLAUDE.md 操作定義表（4 核心術語 + 5 衍生指標）</li>
                <li>· 術語更名：實質收入→實際收入、投資支出→資金轉移、投資收入→資金回收、淨值現金→理論現金變動、現金變動→實際現金變動、資金變動→實際資金變動</li>
                <li>· ChartPage：10+ 個 panel-title 全面對齊新術語（淨收益(實際收支) / 淨投資(實際投資) / 現金變動(實際 VS 理論) / 歷年 實際收入/實際支出/淨收益 / 現金使用 趨勢 等）</li>
                <li>· ChartPage：KPI 淨投資公式說明改為「資金轉移 − 資金回收（正 = 淨流出）」</li>
                <li>· ChartPage：現金變動面板新增第二條線「理論現金變動」（= 淨收益−淨投資 累積折線），資料表加 Δ實際 / Δ理論 月度對照列</li>
                <li>· ChartPage：Tab B 年度比對表 — 資金變動→實際資金變動、現金→實際現金變動、股票→實際股票變動</li>
                <li>· DB 資料修正：32 筆 mode=現金支出 且 cno=13（收入類）錯誤歸類 — 29 筆移至 cno=1 食，1 筆改 mode=收入，1 筆改 cno=3 電子用品，1 筆刪除</li>
                <li>· StatsPage：類型篩選按鈕更名並重排（實際支出 / 實際收入 / 資金轉移 / 資金回收）</li>
                <li>· SettingsPage 版面大改：2×2 全頁等高格局（grid-rows-2，h=100vh-1.5rem）；資料庫+資料庫狀態並列；新增「📚 各頁面說明」；「📖 專有名詞說明」收錄完整術語定義與對帳工具說明</li>
                <li>· DB 重複記錄全庫清理：移除完全重複資料，並還原經確認的真實交易</li>
                <li>· 年度對帳分析：確認一筆<strong>已知缺口</strong>，來源為境外現金支出未經銀行帳戶；列為會計註記，不修改原始資料</li>
                <li>· <strong>下午：月別淨收益/淨投資圖修正</strong> — 圖例與資料表標籤全加「(月)」：淨收益(月)/實際收入(月)/實際支出(月)、淨投資(月)/資金轉移(月)/資金回收(月)，明確區分月度 vs 累積折線</li>
                <li>· 月別資料表改顯示「月度值」而非累積：淨收益表改用 curMonthlySeries.sur；淨投資表新增 curMonthInvNet computed；累積量僅保留給上方折線圖</li>
                <li>· 修正淨收益(月)異常：增加快照存在旗標，定期定額帳戶缺月時不再被誤判為巨額月減</li>
                <li>· 修正淨收益(月)公式：移除定期定額帳戶月增項，回歸「實際收入 − 實際支出」；修正年底月份誤顯示為正值</li>
                <li>· 建立專案 codebase CLAUDE.md（pigmoney-web 根目錄，非上午的術語定義表）：指令/架構/資料流/DB schema/mode 值映射/財務名詞/node 腳本/慣例，附於 12 條規則之下</li>
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
