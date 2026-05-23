# pigmoney-web 開發備忘錄

## 技術架構
- Vue 3 + Vite + Pinia
- sql.js（WASM，瀏覽器端 SQLite）
- Tailwind CSS v4
- AG Grid v35（統計頁）
- 資料檔：`data/money_merged.sqlite`

---

## 第一階段：預算功能建立（完成）

### db.js — budget schema migration
- 新增 `budget_year`、`budget_item`、`budget_project`、`budget_class_bucket` 四張表
- 舊檔開啟時自動補欄位（ALTER TABLE IF NOT EXISTS 模式）

### money.js — budget CRUD + 歷史統計
- `loadBudget(year)`、`upsertBudgetYear`、`upsertBudgetItem`、`bulkUpsertBudgetItems`
- `copyBudgetFromYear`（含年度比例複製）
- `historicalSpend(cno, sno, years)` 回傳中位數/平均/最新年
- `actualSpend`、`actualIncome`
- `classBuckets` 桶位對應（life / fixed / want / save / income）

### BudgetPage — 初版功能
- 樹狀表格（類別 → 子項目），inline 編輯，支援算式
- KPI 四大桶位卡片
- 存款推算
- 「📊 統計初值」一鍵以 3 年中位數填入空格
- 「複製上年」按鈕

---

## 第二階段：資料修正 & UI 優化（完成）

### 資料修正
- **Bug fix**：`copyBudgetFromYear` 引用已刪除的 `income` 欄位 → 已修正為含 ratio 欄位
- **收入歸類修正**：直接對 SQLite 執行 UPDATE，將政德薪水中符合以下規則的 82 筆改歸怡亭薪水
  - 備註含「怡亭」或「分紅」
  - 金額 ≥ 60,000
- **各年度比例設定**（budget_year，2020–2026）：
  | 年 | 生活 | 固定 | 想要 | 投資 | 依據 |
  |---|---|---|---|---|---|
  | 2020 | 15% | 25% | 20% | 40% | 總240W |
  | 2021 | 24% | 24% | 12% | 40% | 總250W |
  | 2022 | 18% | 18% | 9%  | 55% | 總330W |
  | 2023 | 15% | 17% | 15% | 53% | 總400W |
  | 2024 | 15% | 17% | 15% | 53% | 同2023 |
  | 2025 | 15% | 17% | 15% | 53% | 同2023 |
  | 2026 | 18% | 18% | 25% | 40% | 總400W |
- **收入預估寫入**（budget_item，依各年預算檔）：
  | 年 | 怡亭薪水 | 政德薪水 | 投資利得 | 育兒津貼 | 資本利得 |
  |---|---|---|---|---|---|
  | 2021 | 209W | 50W | 7W | 6W | — |
  | 2022 | 230W | 60W | 30W | — | 10W |
  | 2023 | 300W | 60W | 30W | 10W | — |
  | 2024 | 300W | 60W | 40W | 8.4W | — |
  | 2025 | 300W | 60W | 40W | 8.4W | — |
  | 2026 | 300W | 60W | 40W | — | — |
- **備份**：`data/budget_export.json`（budget_year / budget_item / budget_class_bucket）

### BudgetPage UI 改版
- 版面順序：收入預估 → 年度設定 → 6 KPI → 月例行預算表
- 收入預估表改為橫向（子項目為欄），拿掉「實際」與「差距」
- 年度設定：比例欄位標籤「儲蓄投資」改為「投資」
- 年度總收入預算輸入改為**萬為單位**（輸入 400 = 4,000,000）
- 6 張 KPI（單橫列）：總收入預算 / 生活類 / 固定類 / 想要 / 投資 / 存款推算
  - 移除「已用」顯示，只保留預算面數字
  - 存款推算 = 預估收入 − 預算支出
- 月例行預算表：
  - 移除「桶」欄
  - 依四大區塊（生活類 / 固定類 / 想要 / 投資）加 section header
  - 每區塊底部有小計列
- **Bug fix**：`yearTotalBudget` 排除 income bucket，避免收入類別被計入支出總計
- **全站**：`.field[type=number]` 隱藏 spinner 上下箭頭

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
