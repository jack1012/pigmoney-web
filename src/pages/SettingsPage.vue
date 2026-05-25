<script setup>
import { useMoneyStore } from '../stores/money.js'

const store = useMoneyStore()
</script>

<template>
  <div class="p-3 flex flex-col gap-3">
    <section class="panel">
      <span class="panel-title">資料庫</span>
      <div class="grid grid-cols-12 gap-x-3 gap-y-2 items-center text-[13px]">
        <label class="field-label col-span-2 text-right">目前載入:</label>
        <code class="col-span-10 text-[12px] text-zinc-700 dark:text-zinc-300">
          {{ store.fileName || '（尚未載入）' }}
        </code>

        <div class="col-span-12 flex gap-2 flex-wrap">
          <button class="btn btn-primary" @click="store.openFile()">載入 .sqlite 檔</button>
          <button class="btn" :disabled="!store.fileHandle" @click="store.saveFile()">手動存檔</button>
          <span v-if="store.lastSaved" class="text-xs text-emerald-600 dark:text-emerald-400 self-center">
            已存 {{ store.lastSaved }}
          </span>
          <button class="btn" disabled>匯出 JSON</button>
          <button class="btn" disabled>匯出 Excel</button>
        </div>
      </div>
    </section>

    <section v-if="store.db" class="panel">
      <span class="panel-title">資料庫狀態</span>
      <dl class="grid grid-cols-[120px_1fr] gap-y-1 text-[13px] max-w-md">
        <dt class="text-zinc-500">交易筆數</dt>
        <dd>{{ store.transactions.length }} 筆</dd>
        <dt class="text-zinc-500">類別數量</dt>
        <dd>{{ store.classes.length }} 個</dd>
        <dt class="text-zinc-500">子項目數量</dt>
        <dd>{{ store.subjects.length }} 個</dd>
      </dl>
    </section>

    <!-- 關於 + 開發清單 並排 -->
    <div class="grid grid-cols-2 gap-3 items-start">
      <section class="panel">
        <span class="panel-title">開發日誌</span>
        <div class="text-[12px] text-zinc-600 dark:text-zinc-400 space-y-3 max-h-60 overflow-y-auto pr-1">
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
                <li>· 資產頁：加 inline「(改名)」按鈕、DB 改名：房屋→桃園房屋、汽車→Model 3、Model 3 折舊</li>
                <li>· 資料補錄：2021 年 6 筆股票買進（台積電 4 筆 + 易飛網 + 雄獅，合計 244 萬，對應該年投資資產年增）+ 2023 年 1 筆迅得</li>
                <li>· 資料補錄：2013 年 55 筆股票買進（富邦金/玉山金/台積電/中石化/國泰金/群創/南光/世界/群益證/元富證 等，合計約 295 萬）</li>
                <li>· 記帳哲學確立：投資採 A 法（全額進出），mode='信用卡支出' 區分資產搬移 vs 一般消費</li>
                <li>· Store 新增 ChartPage 用 SQL 聚合：yearCnoSpend / yearCnoSnoSpend / yearMonthCnoSpend / yearMonthInvest / yearInvestSpend</li>
                <li>· Chart.js valueLabelPlugin 自製 — 預算數字標柱頂上方（灰）、實際數字標柱底部</li>
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
                <li>· 預算頁：收入歸類修正（82 筆政德薪水 → 怡亭薪水）</li>
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
                <li>· 資料：購車項目合併（11/74 共 36,180 → 15/240，總計 1,646,110；budget_item 累加）</li>
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
                <li>· 資料：教育新增子項目「博士班」(cno=5, sno=264)，2025/2026 預算各 40000；才藝費註記移除博士班字樣</li>
                <li>· 資料重組：購車 (15/74、15/240) 合併並改名「交通工具」搬到 cno=21 專案項目-（共 5 筆 $1,646,110）</li>
                <li>· 資料重組：屋頂整修 (15/204) 改名「房屋工程」搬到 cno=21（1 筆 $171,000）</li>
                <li>· 資料重組：新洗衣機 (15/206) 合併至 cno=21/256 衛生設備（2024-2026 預算相加）</li>
                <li>· 資料重組：旅遊準備金 (15/251) 合併至 15/210 旅遊票卷</li>
                <li>· 資料清理：刪除無交易子項目 15/110 IPHONE17、15/238 生活用品、15/249 其他</li>
                <li>· 旅遊專案改名規則：年份-地點 — 102 拆 2024-香港迪士尼 + 2026-香港迪士尼；244/106/109 → 2023/2025/2026-美國LA之旅</li>
                <li>· 旅遊專案拆分：250 出國 41 筆拆成 2009-希臘 / 2010-韓國 / 2011-土耳其 / 2012-峇里島 / 2013-韓國 / 2014-美國（含 2013 護照+機票+2014 國際駕照），250 子項目已刪</li>
                <li>· 資料備份：data/budget_export.json、money_merged.sqlite.bak_before_merge_purchase、bak_before_2026_notes、bak_before_class_budget、bak_before_cleanup_merge、bak_before_split_overseas</li>
                <li>· 版本管理：git init + .gitignore（排除 *.sqlite/*.bak/截圖/個人 csv/docx/json/暫存腳本），第一個 commit 鎖住 26 個 source/config/docs</li>
                <li>· GitHub repo 建立：jack1012/pigmoney-web（初為 private，部署需要改 public）</li>
                <li>· GitHub Pages 部署：vite.config.js 加 base '/pigmoney-web/'，建 .github/workflows/deploy.yml（push 到 master 自動 build + deploy）</li>
                <li>· 線上網址：<a href="https://jack1012.github.io/pigmoney-web/" target="_blank" class="text-blue-500 underline">jack1012.github.io/pigmoney-web</a>（每次 git push 自動更新，約 30-60 秒）</li>
              </ul>
            </div>
          </div>

          <p class="text-zinc-400">jack · uno = 1</p>
        </div>
      </section>

      <section class="panel">
        <span class="panel-title">開發清單</span>
        <ul class="text-[12px] space-y-1.5 leading-relaxed max-h-60 overflow-y-auto pr-1">
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
            <span class="text-zinc-500">資料補錄：2013 / 2021 / 2023 股票買進交易（63 筆）</span>
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
