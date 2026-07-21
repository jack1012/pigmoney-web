# 專案 AI 共用開發規範

本檔是本專案唯一的 AI 協作規範來源，適用於 Codex、Claude 與其他 AI 開發工具。
其他工具專用入口檔只可指向本檔，不得複製規則內容，以免不同步。

These rules apply to every task in this project unless explicitly overridden.
Bias: caution over speed on non-trivial work. Use judgment on trivial tasks.

## Rule 1 — Think Before Coding
State assumptions explicitly. If uncertain, ask rather than guess.
Present multiple interpretations when ambiguity exists.
Push back when a simpler approach exists.
Stop when confused. Name what's unclear.

## Rule 2 — Simplicity First
Minimum code that solves the problem. Nothing speculative.
No features beyond what was asked. No abstractions for single-use code.
Test: would a senior engineer say this is overcomplicated? If yes, simplify.

## Rule 3 — Surgical Changes
Touch only what you must. Clean up only your own mess.
Don't "improve" adjacent code, comments, or formatting.
Don't refactor what isn't broken. Match existing style.

## Rule 4 — Goal-Driven Execution
Define success criteria. Loop until verified.
Don't follow steps. Define success and iterate.
Strong success criteria let you loop independently.

## Rule 5 — Use the model only for judgment calls
Use me for: classification, drafting, summarization, extraction.
Do NOT use me for: routing, retries, deterministic transforms.
If code can answer, code answers.

## Rule 6 — Token budgets are not advisory
Per-task: 4,000 tokens. Per-session: 30,000 tokens.
If approaching budget, summarize and start fresh.
Surface the breach. Do not silently overrun.

## Rule 7 — Surface conflicts, don't average them
If two patterns contradict, pick one (more recent / more tested).
Explain why. Flag the other for cleanup.
Don't blend conflicting patterns.

## Rule 8 — Read before you write
Before adding code, read exports, immediate callers, shared utilities.
"Looks orthogonal" is dangerous. If unsure why code is structured a way, ask.

## Rule 9 — Tests verify intent, not just behavior
Tests must encode WHY behavior matters, not just WHAT it does.
A test that can't fail when business logic changes is wrong.

## Rule 10 — Checkpoint after every significant step
Summarize what was done, what's verified, what's left.
Don't continue from a state you can't describe back.
If you lose track, stop and restate.

## Rule 11 — Match the codebase's conventions, even if you disagree
Conformance > taste inside the codebase.
If you genuinely think a convention is harmful, surface it. Don't fork silently.

## Rule 12 — Fail loud
"Completed" is wrong if anything was skipped silently.
"Tests pass" is wrong if any were skipped.
Default to surfacing uncertainty, not hiding it.

## Rule 13 — Ask before executing unfamiliar commands
If unsure how to run a command in this environment (PATH, shell, permissions),
stop and ask the user rather than guessing or using a workaround silently.

---

# 專案：pigmoney-web

家庭財務分析 Web App。瀏覽器端 SQLite（sql.js）+ Vue 3 + Pinia。
以下講「程式怎麼運作」；財務領域操作指南看 `README.md`。溝通一律繁體中文（台灣）。

## 指令

```bash
npm run dev       # Vite 開發伺服器
npm run build     # 打包到 dist/
npm run preview   # 預覽 build 結果
```

無測試、無 lint 腳本。部署目標為 GitHub Pages，`vite.config.js` 設 `base: '/pigmoney-web/'`。

## 架構

Vue 3 `<script setup>` Composition API，單一 Pinia store 管所有狀態與 DB 存取。

```
src/
  main.js            # createApp + Pinia + AG Grid module 註冊
  App.vue            # tab 切換外殼（keep-alive），無 router
  style.css          # Tailwind v4 + dark mode
  lib/
    db.js            # sql.js 初始化 + ensureBudgetSchema（建/補表）
    modeLabel.js     # mode 的 DB 值 → UI 顯示文字映射
  stores/
    money.js         # ★ 核心：唯一的 store，所有 DB 讀寫都走這裡
  pages/
    EntryPage.vue    記帳（AG Grid 列表 + 新增/編輯）
    StatsPage.vue    年度支出統計
    ChartPage.vue    圖表（Tab A 年度 / Tab B 歷年）— 全檔最大、computed 最密
    CategoryPage.vue 類別/子項目管理（拖曳排序）
    BudgetPage.vue   預算（編輯 + 歷年模式）
    AssetPage.vue    資產快照（編輯 + 歷年模式）
    SettingsPage.vue 開啟/匯入 DB、開發日誌
```

頁面間不用 router，由 `App.vue` 的 `currentTab` 切換 `<component :is>`，全部 `<keep-alive>`。
跨頁切換透過 store 的 `requestTabSwitch` / `requestEditInEntry`。

## 資料流（重要）

**所有 DB 寫入都必須經過 `money.js` store 的 action，元件不可直接碰 `db`。**
每個寫入 action 的尾巴都會呼叫 `saveFile()` 把整個 DB export 回磁碟。

```
元件 → store action（db.run 改記憶體 DB）→ refreshAll()/loadXxx() → saveFile()
```

- `saveFile()` 用 **File System Access API**（`createWritable`）→ **只支援 Chrome / Edge**。
- `openFile()` 用 `showOpenFilePicker`，存 `fileHandle` 以便後續回寫。
- `checkDiskReload()`：tab 切換時比對磁碟 `lastModified`，外部改檔會自動重載（給 node 腳本改完 DB 後在 UI 看得到）。
- DB 是 sql.js 記憶體實例；不存檔 = 改動只在記憶體。

## DB Schema

兩組來源：

**① 舊表（豬頭記帳.exe 沿用，勿改結構）** — 全部用 `uno=1`（`JACK_UNO`）過濾：

| 表 | 重點欄位 |
|----|---------|
| `money` | `mno`(PK), `cno`, `sno`, `spend`, `date`('YYYY-MM-DD'), `note`, `mode`, `uno` |
| `class` | `cno`(PK), `name`, `order_id`, `uno` |
| `subject` | `sno`(PK), `cno`, `name`, `order_id`, `uno` |

**② 新表（`lib/db.js` 的 `ensureBudgetSchema` 自動建/補欄位）**：
`budget_year`, `budget_item`, `budget_project`, `budget_class_bucket`, `asset_account`, `asset_snapshot`。

- `budget_class_bucket(cno, bucket)`：bucket ∈ `life|fixed|want|save`；收入類別特殊標 `income`（見 store `DEFAULT_BUCKET_BY_NAME`）。
- `asset_snapshot(date, ano, amount)`：每月/年底資產快照。
- `asset_account(ano, category, name, ...)`：**category 現行值是 `資金`（現金+股票合併）、`動產/不動產`、`負債`**。
  > ⚠️ `db.js` 的 schema 註解寫舊值（`現金/投資/...`）已過時，以實際資料的 `資金` 為準。
  > 股票 vs 現金靠帳戶名稱判斷（`isStockAccount(name)`），不是靠 category。

開新檔或舊檔缺表時，`openDbFromFile` 會自動跑 migration，安全冪等。

## `mode` 欄位 — DB 值 vs 顯示值（易踩雷）

`money.mode` 在 DB 端保留**舊中文值**以相容豬頭記帳.exe，UI 顯示另用 `lib/modeLabel.js` 映射：

| DB 值（寫入用這個） | UI 顯示 | 財務意義 |
|------|---------|---------|
| `現金支出` | 現金支出 | 實際支出 |
| `信用卡支出` | 投資支出 | 資金轉移（買股本金，cno=14）|
| `信用卡收入` | 投資收入 | 資金回收（賣股本金，cno=14）|
| `收入` | 收入 | 實際收入 |

寫 SQL 一律用左欄 DB 值；給使用者看一律過 `modeLabel()`。**不要把顯示文字寫進 DB。**

## 財務名詞（UI 標籤/圖例/欄名一律照這張表，不得混用舊稱）

| 術語 | 定義 | 判定 |
|------|------|------|
| **實際收入** | 外部流入，淨資產增加 | 薪資類 / `mode='收入'` |
| **實際支出** | 流出後消失，淨資產縮水 | `mode='現金支出'`（非 cno=14）|
| **資金轉移** | 現金換成其他資產，淨資產不變 | `mode='信用卡支出'`（cno=14）|
| **資金回收** | 本金變現回現金，淨資產不變 | `mode='信用卡收入'`（cno=14）|

衍生：**淨收益 = 實際收入 − 實際支出**；**淨投資 = 資金轉移 − 資金回收**。

> 已知重點 cno：`13` = 收入、`14` = 投資（買賣股，bucket `save`）。
> 怡亭-凱基定期定額股票（`ano=18`）**不入 money 表**，只反映在 asset_snapshot；
> 它不屬於「實際收入/支出」，請勿把它的月增量加進淨收益。完整領域說明見 `README.md`。

## 用 node 腳本查/改 DB（debug 常用）

App 實際開的是使用者自選的檔；離線分析的標準工作檔是 `.data/money_merged.sqlite`。

- node 腳本路徑用 **正斜線**：`D:/Projects/pigmoney-web/.data/money_merged.sqlite`。
- 改 DB 前先備份（`.data/` 內已有多個 `money_merged.backup-*.sqlite` 範例）。
- 改完檔後，UI 端在 tab 切換時會經 `checkDiskReload()` 自動重載。
- `.data/` 另有歷史/分庫檔（`money2025.sqlite`、`money-1/2.sqlite` 等），勿誤當主檔。

## 慣例

- 繁體中文註解與 UI 文案。
- 金額單位：DB 存「元」整數；UI 常以「萬」顯示（除以 10000）。
- 改動要外科手術式（見上方 13 條規則）：只動該動的，不順手重排/重構鄰近碼，配合既有風格。
- ChartPage.vue 的 computed 互相依賴密集，改公式前先讀清楚資料怎麼一路算出來，別只看單一分支臆測。
