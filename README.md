# pigmoney-web

家庭財務分析 Web App — Vue 3 + Vite + Pinia + sql.js（瀏覽器端 SQLite）

---

## 技術棧

| 層級 | 套件 |
|------|------|
| UI 框架 | Vue 3 (Composition API `<script setup>`) |
| 打包 | Vite 8 |
| 狀態管理 | Pinia |
| 資料庫 | sql.js（WASM SQLite，File System Access API 持久化） |
| 樣式 | Tailwind CSS v4 + dark mode |
| 表格 | AG Grid (Community) |
| 圖表 | Chart.js（待接入） |

---

## 頁面功能

| 頁面 | 狀態 | 說明 |
|------|------|------|
| 記帳（EntryPage） | ✅ 完成 | 交易新增 / 編輯 / AG Grid 列表 |
| 類別（CategoryPage） | ✅ 完成 | 類別 & 子項目管理、拖曳排序 |
| 預算（BudgetPage） | ✅ 完成 | 編輯模式 + 歷年模式；KPI 卡片；桶位細項表 |
| 資產（AssetPage） | ✅ 完成 | 編輯模式 + 歷年模式；快照管理；淨資產 KPI |
| 統計（StatsPage） | ✅ 完成 | 年度支出統計 |
| 圖表（ChartPage） | 🔜 下一步 | 趨勢折線圖 / 桶位分佈 / 淨資產成長 |
| 設定（SettingsPage） | ✅ 完成 | 開啟 / 匯入 DB 檔案 |

---

## 工作紀錄

### 2026-05-24（第三階段）

**AssetPage — 修正 histDisplayDates Bug**
- 歷年模式 2026 欄位資料空白，原因：`histDisplayDates` 未排除 `-12-31` 日期，
  導致 `2026-12-31`（動產複製產生的年底快照）排在最後被選中，現金/投資資料均為零
- 修正：在當年度篩選條件加入 `&& !s.date.endsWith('-12-31')`，與 `latestDate` 邏輯一致

**BudgetPage — 編輯模式 + 歷年模式**
- 移除按鈕：「複製 N 年」、「📊 統計初值」、「🤖 AI 分析」
- 保留：「📥 匯出 JSON」
- 新增模式切換（編輯 / 歷年）
- 歷年模式：跨年度橫向比較表，欄為年份，列為各桶位類別預算，附小計與總計
- Store 新增 `loadAllBudgets()`、`allBudgetYearMetas`、`allBudgetItems`

---

### 2026-05-23（第二階段）

**AssetPage — 歷年模式**
- 加入「編輯 / 歷年」模式切換
- 歷年模式：2019–當年，各帳戶跨年橫向對照，唯讀
- 當年欄位使用最新非年底月份快照，顯示月份 badge
- KPI 僅在編輯模式顯示

**AssetPage — KPI 日期修正**
- `latestDate`、`prevLatestDate` 排除 `-12-31`，避免年底快照干擾現金/投資查詢
- `sectionCurDate` / `sectionPrevDate` 依 `viewMode` 切換對應日期

---

### 2026-05-22（第一階段）

**AssetPage — 初版建立**
- 動產/不動產+負債改為「年底年度單欄」模式
- KPI 混合日期邏輯：現金/投資用最新月份；動產/負債用最近年底
- 汽車折舊公式修正：2020 = 1,680,000，每年 × 0.8
- 資料日期修正腳本：`fix_snapshot_dates.py`（移動 9–11 月快照、刪除錯誤年初資料）

---

## 下一步任務

- [ ] 🔜 **圖表頁（ChartPage）**
  - 淨資產成長折線圖（年度）
  - 各桶位預算 vs 實際支出分佈
  - 收支趨勢（月別）
  - 考慮使用 Chart.js（已安裝）或切換 AG Charts

- [ ] 資產頁：2026 當年度歷年顯示「月份 badge」驗證（UI 確認）
- [ ] 預算歷年模式：加入「收入預算 vs 實際」對照列（optional）
