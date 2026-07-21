# pigmoney-web 開發備忘錄

## 技術架構
- Vue 3 + Vite + Pinia
- sql.js（WASM，瀏覽器端 SQLite）
- Tailwind CSS v4
- AG Grid v35（統計頁）
- 資料檔：`.data/money_merged.sqlite`

---

## v2.1.0 — 存檔機制修復 (2026-07-21)

- **Bug fix**：修復 File System Access API 在背景同步或檔案狀態變更時發生的 `InvalidStateError`（存檔失敗）問題。
- **存檔機制強化**：
  - 寫入前主動呼叫 `fileHandle.getFile()` 刷新控制代碼快取狀態。
  - 增加自動重試（Auto-Retry）機制，延遲 150ms 後重試 `createWritable()`。
  - 寫入後同步更新磁碟修改時間戳記 `diskLastModified`，避開 `checkDiskReload` 誤判。
- **開發日誌**：於 `SettingsPage.vue` 更新開發日誌與版本號標籤 `v2.1.0 (2026-07-21)`。

---

## v2.0.0 — 預算管理系統大改版與全站優化 (2026-05-23 ~ 2026-05-24)

### db.js — budget schema migration
- 新增 `budget_year`、`budget_item`、`budget_project`、`budget_class_bucket` 四張表
- 舊檔開啟時自動補欄位（ALTER TABLE IF NOT EXISTS 模式）

### BudgetPage UI 改版與雙模式
- 版面順序：收入預估 → 年度設定 → 6 KPI → 月例行預算表
- 四大桶位（生活/固定/想要/投資）、比例金額雙向綁定
- 存款推算 = 預估收入 − 預算支出
- 歷年橫向比對模式，全站 Keep-Alive 與跨頁連動

---

## v1.2.0 — 全站財務術語規範與對帳系統 (2026-05-31)

- 雙軌財務術語對齊（實際收入/實際支出、資金轉移/資金回收、淨收益/淨投資、理論現金變動/實際現金變動/實際資金變動）
- 現金變動雙線對帳圖（Δ實際 vs Δ理論）與 2×2 關於頁重構

---

## v1.1.0 — 視覺化分析圖表與拆帳法 (2026-05-25 ~ 2026-05-29)

- Chart.js 圖表頁（Tab A 當年 / Tab B 歷年）建置
- 投資拆帳法、AssetPage 資產月度快照追蹤、README CFO 操作指南

---

## v1.0.0 — 核心記帳與基礎架構上線 (2026-05-20 ~ 2026-05-22)

- Vue 3 + Vite + Pinia 專案創立與 sql.js WASM SQLite 瀏覽器整合
- EntryPage 記帳、StatsPage 統計、CategoryPage 分類與 File System Access API 本機自動存檔

---

## 下一階段：月例行預算表版面調整（待開始）

- 繼續調整月例行預算的欄位、版面與互動細節
- 待討論：各區塊小計是否要有進度條、算式欄顯示方式等

---

## 資料庫重要資訊
- `uno = 1`（jack）
- 收入 class：`cno = 13`
- 收入子項目 sno：62=怡亭薪水、63=政德薪水、64=投資利得、65=利息、66=資本利得、67=育兒津貼、68=其他
- budget_item 的 `month=0` 代表年度預算（非月份）
- 金額單位：元（NTD）
