import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { openDbFromFile, rowsToObjects, ensureBudgetSchema } from '../lib/db.js'

const JACK_UNO = 1

export const useMoneyStore = defineStore('money', () => {
  const db = ref(null)
  const fileName = ref('')
  const fileHandle = ref(null)
  const loading = ref(false)
  const error = ref('')
  const lastSaved = ref('')

  const classes = ref([])
  const subjects = ref([])
  const transactions = ref([])

  // 跨頁編輯：StatsPage 點「修改」→ 切到 EntryPage 帶入此 mno
  const pendingEditMno = ref(null)
  const requestTabSwitch = ref(null) // App.vue 監聽，值為 'entry' 等
  function requestEditInEntry(mno) {
    pendingEditMno.value = mno
    requestTabSwitch.value = 'entry'
  }
  function clearPendingEdit() { pendingEditMno.value = null }
  function clearTabSwitch()   { requestTabSwitch.value = null }

  // ── 資產狀態 ────────────────────────────────────────
  const assetAccounts = ref([])    // [{ano, category, name, note, order_id}]
  const assetSnapshots = ref([])   // [{date, ano, amount}]

  async function loadAssets() {
    if (!db.value) return
    assetAccounts.value = rowsToObjects(db.value.exec(
      'SELECT ano, category, name, note, order_id FROM asset_account ORDER BY category, order_id, ano'
    ))
    assetSnapshots.value = rowsToObjects(db.value.exec(
      'SELECT date, ano, amount FROM asset_snapshot ORDER BY date'
    ))
  }

  async function upsertAssetAccount({ ano, category, name, note, order_id }) {
    if (!db.value) return
    if (ano) {
      db.value.run(
        'UPDATE asset_account SET category=?, name=?, note=?, order_id=? WHERE ano=?',
        [category, name, note ?? null, order_id ?? 0, ano]
      )
    } else {
      const maxOrder = assetAccounts.value
        .filter(a => a.category === category)
        .reduce((m, a) => Math.max(m, a.order_id ?? 0), 0)
      db.value.run(
        'INSERT INTO asset_account (category, name, note, order_id) VALUES (?, ?, ?, ?)',
        [category, name, note ?? null, order_id ?? (maxOrder + 1)]
      )
    }
    await loadAssets(); await saveFile()
  }

  async function deleteAssetAccount(ano) {
    if (!db.value) return
    db.value.run('DELETE FROM asset_snapshot WHERE ano=?', [ano])
    db.value.run('DELETE FROM asset_account WHERE ano=?', [ano])
    await loadAssets(); await saveFile()
  }

  async function upsertAssetSnapshot({ date, ano, amount }) {
    if (!db.value) return
    if (amount == null || amount === '' || Number.isNaN(Number(amount))) {
      db.value.run('DELETE FROM asset_snapshot WHERE date=? AND ano=?', [date, ano])
    } else {
      db.value.run(
        `INSERT INTO asset_snapshot (date, ano, amount) VALUES (?, ?, ?)
         ON CONFLICT(date, ano) DO UPDATE SET amount=excluded.amount`,
        [date, ano, Math.round(Number(amount))]
      )
    }
    await loadAssets(); await saveFile()
  }

  async function bulkUpsertAssetSnapshots(items) {
    if (!db.value || !items?.length) return
    for (const { date, ano, amount } of items) {
      if (amount == null || amount === '' || Number.isNaN(Number(amount))) continue
      db.value.run(
        `INSERT INTO asset_snapshot (date, ano, amount) VALUES (?, ?, ?)
         ON CONFLICT(date, ano) DO UPDATE SET amount=excluded.amount`,
        [date, ano, Math.round(Number(amount))]
      )
    }
    await loadAssets(); await saveFile()
  }

  async function deleteAssetSnapshotDate(date) {
    if (!db.value) return
    db.value.run('DELETE FROM asset_snapshot WHERE date=?', [date])
    await loadAssets(); await saveFile()
  }

  // ── 預算狀態 ────────────────────────────────────────
  const budgetYear = ref(new Date().getFullYear())
  const budgetYearMeta = ref(null)   // { year, total, note, ratio_life, ratio_fixed, ratio_save } | null
  const budgetItems = ref([])        // [{ year, cno, sno, month, amount, formula }]
  const allBudgetYearMetas = ref([]) // 歷年 budget_year：[{ year, total }]
  const allBudgetItems = ref([])     // 歷年 budget_item (month=0)：[{ year, cno, sno, amount }]
  const classBuckets = ref({})       // { [cno]: 'life'|'fixed'|'save' }

  // 預設桶位（依類別名稱，初次使用時自動套入）
  // 收入 → 獨立追蹤（income），不進任何支出桶
  const DEFAULT_BUCKET_BY_NAME = {
    '食': 'life', '衣': 'life', '生活': 'life', '交通': 'life', '教育': 'life', '娛樂': 'life',
    '特殊': 'fixed', '稅金': 'fixed', '房屋': 'fixed', '車': 'fixed', '保險': 'fixed',
    '專案項目': 'want', '專案項目-': 'want',
    '投資': 'save',
    '收入': 'income',   // 特殊值：收入追蹤，不算在支出桶
  }

  // 桶位顯示設定
  const BUCKETS = [
    { key: 'life',  label: '生活類',  color: 'emerald' },
    { key: 'fixed', label: '固定類',  color: 'blue'    },
    { key: 'want',  label: '想要',    color: 'amber'   },
    { key: 'save',  label: '儲蓄投資', color: 'violet'  },
  ]

  const classMap = computed(
    () => new Map(classes.value.map((c) => [c.cno, c.name])),
  )
  const subjectMap = computed(
    () => new Map(subjects.value.map((s) => [s.sno, s.name])),
  )

  async function openFile() {
    if (!window.showOpenFilePicker) {
      error.value = '請使用 Chrome 瀏覽器（需支援 File System Access API）'
      return
    }
    let handle
    try {
      ;[handle] = await window.showOpenFilePicker({
        types: [{ description: 'SQLite Database', accept: { 'application/octet-stream': ['.sqlite', '.db'] } }],
        multiple: false,
      })
    } catch (e) {
      if (e.name !== 'AbortError') error.value = e.message || String(e)
      return
    }
    loading.value = true
    error.value = ''
    try {
      const file = await handle.getFile()
      db.value = await openDbFromFile(file)
      fileName.value = file.name
      fileHandle.value = handle
      lastSaved.value = ''
      refreshAll()
    } catch (e) {
      error.value = e.message || String(e)
      db.value = null
      fileHandle.value = null
    } finally {
      loading.value = false
    }
  }

  async function saveFile() {
    if (!db.value || !fileHandle.value) return
    try {
      const permission = await fileHandle.value.requestPermission({ mode: 'readwrite' })
      if (permission !== 'granted') {
        error.value = '請在瀏覽器彈窗中允許寫入檔案'
        return
      }
      const data = db.value.export()
      const writable = await fileHandle.value.createWritable()
      await writable.write(data)
      await writable.close()
      const now = new Date()
      lastSaved.value = now.toLocaleTimeString('zh-TW', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
    } catch (e) {
      error.value = '存檔失敗：' + (e.message || String(e))
    }
  }

  function refreshAll() {
    if (!db.value) return
    classes.value = rowsToObjects(
      db.value.exec(
        `SELECT cno, name, order_id FROM class WHERE uno=${JACK_UNO} ORDER BY order_id`,
      ),
    )
    subjects.value = rowsToObjects(
      db.value.exec(
        `SELECT sno, cno, name, order_id FROM subject WHERE uno=${JACK_UNO} ORDER BY cno, order_id`,
      ),
    )
    transactions.value = rowsToObjects(
      db.value.exec(
        `SELECT mno, cno, sno, spend, date, note, mode FROM money WHERE uno=${JACK_UNO} ORDER BY date DESC, mno DESC`,
      ),
    )
    loadBudget(budgetYear.value)
    loadAssets()
  }

  async function addTransaction({ cno, sno, spend, date, note, mode }) {
    if (!db.value) return
    db.value.run(
      `INSERT INTO money (uno, cno, sno, spend, date, note, mode)
       VALUES (?, ?, ?, ?, ?, ?, ?)`,
      [JACK_UNO, cno, sno ?? null, spend, date, note || '', mode],
    )
    refreshAll()
    await saveFile()
  }

  async function updateTransaction({ mno, cno, sno, spend, date, note, mode }) {
    if (!db.value) return
    db.value.run(
      `UPDATE money SET cno=?, sno=?, spend=?, date=?, note=?, mode=?
       WHERE mno=? AND uno=?`,
      [cno, sno ?? null, spend, date, note || '', mode, mno, JACK_UNO],
    )
    refreshAll()
    await saveFile()
  }

  async function deleteTransaction(mno) {
    if (!db.value) return
    db.value.run(`DELETE FROM money WHERE mno=? AND uno=?`, [mno, JACK_UNO])
    refreshAll()
    await saveFile()
  }

  // ── 類別 CRUD ─────────────────────────────────────────
  async function addClass(name) {
    if (!db.value) return
    const maxOrder = classes.value.length > 0 ? Math.max(...classes.value.map(c => c.order_id ?? 0)) : 0
    db.value.run(`INSERT INTO class (uno, name, order_id) VALUES (?, ?, ?)`, [JACK_UNO, name, maxOrder + 1])
    refreshAll()
    await saveFile()
  }

  async function renameClass(cno, name) {
    if (!db.value) return
    db.value.run(`UPDATE class SET name=? WHERE cno=? AND uno=?`, [name, cno, JACK_UNO])
    refreshAll()
    await saveFile()
  }

  async function deleteClass(cno) {
    if (!db.value) return
    db.value.run(`DELETE FROM subject WHERE cno=? AND uno=?`, [cno, JACK_UNO])
    db.value.run(`DELETE FROM class WHERE cno=? AND uno=?`, [cno, JACK_UNO])
    refreshAll()
    await saveFile()
  }

  async function saveClassOrder(orderedCnos) {
    if (!db.value) return
    orderedCnos.forEach((cno, i) => {
      db.value.run(`UPDATE class SET order_id=? WHERE cno=? AND uno=?`, [i + 1, cno, JACK_UNO])
    })
    refreshAll()
    await saveFile()
  }

  // ── 子項目 CRUD ───────────────────────────────────────
  async function addSubject(cno, name) {
    if (!db.value) return
    const subs = subjects.value.filter(s => s.cno === cno)
    const maxOrder = subs.length > 0 ? Math.max(...subs.map(s => s.order_id ?? 0)) : 0
    db.value.run(`INSERT INTO subject (uno, cno, name, order_id) VALUES (?, ?, ?, ?)`, [JACK_UNO, cno, name, maxOrder + 1])
    refreshAll()
    await saveFile()
  }

  async function renameSubject(sno, name) {
    if (!db.value) return
    db.value.run(`UPDATE subject SET name=? WHERE sno=? AND uno=?`, [name, sno, JACK_UNO])
    refreshAll()
    await saveFile()
  }

  async function deleteSubject(sno) {
    if (!db.value) return
    db.value.run(`UPDATE money SET sno=NULL WHERE sno=? AND uno=?`, [sno, JACK_UNO])
    db.value.run(`DELETE FROM subject WHERE sno=? AND uno=?`, [sno, JACK_UNO])
    refreshAll()
    await saveFile()
  }

  async function saveSubjectOrder(orderedSnos) {
    if (!db.value) return
    orderedSnos.forEach((sno, i) => {
      db.value.run(`UPDATE subject SET order_id=? WHERE sno=? AND uno=?`, [i + 1, sno, JACK_UNO])
    })
    refreshAll()
    await saveFile()
  }

  // ── 設定檔匯入（完全取代）────────────────────────────
  async function importCategories(jsonData) {
    if (!db.value) return
    db.value.run(`DELETE FROM subject WHERE uno=?`, [JACK_UNO])
    db.value.run(`DELETE FROM class   WHERE uno=?`, [JACK_UNO])
    const nameToId = new Map()
    ;(jsonData.classes ?? []).forEach(cls => {
      db.value.run(
        `INSERT INTO class (uno, name, order_id) VALUES (?, ?, ?)`,
        [JACK_UNO, cls.name, cls.order_id ?? 1],
      )
      const r = db.value.exec(`SELECT last_insert_rowid()`)
      nameToId.set(cls.name, r[0]?.values[0][0])
    })
    ;(jsonData.subjects ?? []).forEach(sub => {
      const cno = nameToId.get(sub.className)
      if (!cno) return
      db.value.run(
        `INSERT INTO subject (uno, cno, name, order_id) VALUES (?, ?, ?, ?)`,
        [JACK_UNO, cno, sub.name, sub.order_id ?? 1],
      )
    })
    refreshAll()
    await saveFile()
  }

  // ── 預算 CRUD ───────────────────────────────────────
  function loadAllBudgets() {
    if (!db.value) return
    ensureBudgetSchema(db.value)
    allBudgetYearMetas.value = rowsToObjects(
      db.value.exec(`SELECT year, total FROM budget_year ORDER BY year`)
    )
    allBudgetItems.value = rowsToObjects(
      db.value.exec(`SELECT year, cno, sno, amount FROM budget_item WHERE month=0 ORDER BY year, cno, sno`)
    )
  }

  function loadBudget(year) {
    if (!db.value) return
    ensureBudgetSchema(db.value)
    budgetYear.value = year
    const yr = rowsToObjects(
      db.value.exec(`SELECT year, total, note, ratio_life, ratio_fixed, ratio_want, ratio_save FROM budget_year WHERE year=${year}`),
    )
    budgetYearMeta.value = yr[0] ?? null
    budgetItems.value = rowsToObjects(
      db.value.exec(
        `SELECT year, cno, sno, month, amount, formula, note FROM budget_item WHERE year=${year}`,
      ),
    )
    loadClassBuckets()
  }

  function loadClassBuckets() {
    if (!db.value) return
    const rows = rowsToObjects(db.value.exec(`SELECT cno, bucket FROM budget_class_bucket`))
    const map = {}
    rows.forEach((r) => { map[r.cno] = r.bucket })
    // 若某個 class 尚未設定桶位，套預設值
    let needSave = false
    for (const c of classes.value) {
      if (!map[c.cno]) {
        const def = DEFAULT_BUCKET_BY_NAME[c.name]
        if (def) {
          map[c.cno] = def
          db.value.run(
            `INSERT OR IGNORE INTO budget_class_bucket (cno, bucket) VALUES (?, ?)`,
            [c.cno, def],
          )
          needSave = true
        }
      }
    }
    if (needSave) saveFile()
    classBuckets.value = map
  }

  async function setClassBucket(cno, bucket) {
    if (!db.value) return
    db.value.run(
      `INSERT INTO budget_class_bucket (cno, bucket) VALUES (?, ?)
       ON CONFLICT(cno) DO UPDATE SET bucket=excluded.bucket`,
      [cno, bucket],
    )
    classBuckets.value = { ...classBuckets.value, [cno]: bucket }
    await saveFile()
  }

  async function upsertBudgetYear({ year, total, note, ratio_life, ratio_fixed, ratio_want, ratio_save }) {
    if (!db.value) return
    db.value.run(
      `INSERT INTO budget_year (year, total, note, ratio_life, ratio_fixed, ratio_want, ratio_save)
       VALUES (?, ?, ?, ?, ?, ?, ?)
       ON CONFLICT(year) DO UPDATE SET
         total=excluded.total, note=excluded.note,
         ratio_life=excluded.ratio_life, ratio_fixed=excluded.ratio_fixed,
         ratio_want=excluded.ratio_want, ratio_save=excluded.ratio_save`,
      [year, total ?? null, note ?? '',
       ratio_life ?? 0.30, ratio_fixed ?? 0.20, ratio_want ?? 0.10, ratio_save ?? 0.40],
    )
    loadBudget(budgetYear.value)
    await saveFile()
  }

  async function upsertBudgetItemNote({ year, cno, sno = 0, month = 0, note }) {
    if (!db.value) return
    // 確保 row 存在（沒 amount 也建 row 來存 note）
    db.value.run(
      `INSERT INTO budget_item (year, cno, sno, month, amount, formula, note) VALUES (?, ?, ?, ?, NULL, NULL, ?)
       ON CONFLICT(year, cno, sno, month) DO UPDATE SET note=excluded.note`,
      [year, cno, sno, month, note ?? null],
    )
    loadBudget(budgetYear.value)
    await saveFile()
  }

  async function upsertBudgetItem({ year, cno, sno = 0, month = 0, amount, formula }) {
    if (!db.value) return
    if (amount == null || amount === '' || Number.isNaN(Number(amount))) {
      // 空值 = 刪除該格
      db.value.run(
        `DELETE FROM budget_item WHERE year=? AND cno=? AND sno=? AND month=?`,
        [year, cno, sno, month],
      )
    } else {
      db.value.run(
        `INSERT INTO budget_item (year, cno, sno, month, amount, formula) VALUES (?, ?, ?, ?, ?, ?)
         ON CONFLICT(year, cno, sno, month) DO UPDATE SET amount=excluded.amount, formula=excluded.formula`,
        [year, cno, sno, month, Math.round(Number(amount)), formula ?? null],
      )
    }
    loadBudget(budgetYear.value)
    await saveFile()
  }

  // 批次寫入（給「一鍵填入」之類用，避免每格都觸發 saveFile）
  async function bulkUpsertBudgetItems(items) {
    if (!db.value || !items?.length) return
    for (const it of items) {
      const { year, cno, sno = 0, month = 0, amount, formula } = it
      if (amount == null || amount === '' || Number.isNaN(Number(amount))) continue
      db.value.run(
        `INSERT INTO budget_item (year, cno, sno, month, amount, formula) VALUES (?, ?, ?, ?, ?, ?)
         ON CONFLICT(year, cno, sno, month) DO UPDATE SET amount=excluded.amount, formula=excluded.formula`,
        [year, cno, sno, month, Math.round(Number(amount)), formula ?? null],
      )
    }
    loadBudget(budgetYear.value)
    await saveFile()
  }

  // 匯出某一年度預算為 JSON（含 budget_year / budget_item / budget_class_bucket + class/subject 名稱）
  function exportBudgetYearJson(year) {
    if (!db.value) return null
    const yearMeta = rowsToObjects(db.value.exec(
      `SELECT * FROM budget_year WHERE year=${year}`
    ))[0] ?? null
    const items = rowsToObjects(db.value.exec(
      `SELECT b.year, b.cno, b.sno, b.month, b.amount, b.formula, b.note,
              c.name AS class_name, s.name AS subject_name
       FROM budget_item b
       LEFT JOIN class   c ON c.cno = b.cno
       LEFT JOIN subject s ON s.cno = b.cno AND s.sno = b.sno
       WHERE b.year=${year}
       ORDER BY b.cno, b.sno, b.month`
    ))
    const buckets = rowsToObjects(db.value.exec(
      `SELECT b.cno, c.name AS class_name, b.bucket
       FROM budget_class_bucket b
       LEFT JOIN class c ON c.cno = b.cno
       ORDER BY b.cno`
    ))
    return {
      exported_at: new Date().toISOString(),
      year,
      budget_year: yearMeta,
      budget_class_bucket: buckets,
      budget_item: items,
    }
  }

  async function copyBudgetFromYear(srcYear, dstYear, { multiplier = 1.0 } = {}) {
    if (!db.value) return
    const src = rowsToObjects(
      db.value.exec(
        `SELECT cno, sno, month, amount, formula FROM budget_item WHERE year=${srcYear}`,
      ),
    )
    db.value.run(`DELETE FROM budget_item WHERE year=?`, [dstYear])
    for (const r of src) {
      const newAmt = r.amount != null ? Math.round(r.amount * multiplier) : null
      db.value.run(
        `INSERT INTO budget_item (year, cno, sno, month, amount, formula) VALUES (?, ?, ?, ?, ?, ?)`,
        [dstYear, r.cno, r.sno, r.month, newAmt, r.formula],
      )
    }
    // 同時複製年度總覽
    const srcMeta = rowsToObjects(
      db.value.exec(`SELECT total, note, ratio_life, ratio_fixed, ratio_want, ratio_save FROM budget_year WHERE year=${srcYear}`),
    )[0]
    if (srcMeta) {
      db.value.run(
        `INSERT INTO budget_year (year, total, note, ratio_life, ratio_fixed, ratio_want, ratio_save)
         VALUES (?, ?, ?, ?, ?, ?, ?)
         ON CONFLICT(year) DO UPDATE SET
           total=excluded.total, note=excluded.note,
           ratio_life=excluded.ratio_life, ratio_fixed=excluded.ratio_fixed,
           ratio_want=excluded.ratio_want, ratio_save=excluded.ratio_save`,
        [
          dstYear,
          srcMeta.total != null ? Math.round(srcMeta.total * multiplier) : null,
          srcMeta.note ?? '',
          srcMeta.ratio_life ?? 0.30,
          srcMeta.ratio_fixed ?? 0.20,
          srcMeta.ratio_want ?? 0.10,
          srcMeta.ratio_save ?? 0.40,
        ],
      )
    }
    loadBudget(dstYear)
    await saveFile()
  }

  // ── 歷史支出統計 ───────────────────────────────────────
  // 取得指定 (cno, sno) 各年度的實際支出統計
  // sno=0 代表整個類別合計
  // 回傳 { byYear: {2023: total, 2024: total, ...}, median, mean, last }
  function historicalSpend(cno, sno = 0, years = 3) {
    if (!db.value) return { byYear: {}, median: 0, mean: 0, last: 0 }
    const thisYear = budgetYear.value
    const yMin = thisYear - years
    const yMax = thisYear - 1
    const whereSno = sno > 0 ? `AND sno=${sno}` : ''
    const rows = rowsToObjects(
      db.value.exec(
        `SELECT strftime('%Y', date) AS yr, SUM(spend) AS total
         FROM money
         WHERE uno=${JACK_UNO} AND cno=${cno} ${whereSno}
           AND CAST(strftime('%Y', date) AS INTEGER) BETWEEN ${yMin} AND ${yMax}
         GROUP BY yr
         ORDER BY yr`,
      ),
    )
    const byYear = {}
    rows.forEach((r) => {
      byYear[r.yr] = Number(r.total ?? 0)
    })
    const values = Object.values(byYear).filter((v) => v > 0)
    const sorted = [...values].sort((a, b) => a - b)
    const median = sorted.length
      ? sorted.length % 2
        ? sorted[(sorted.length - 1) / 2]
        : Math.round((sorted[sorted.length / 2 - 1] + sorted[sorted.length / 2]) / 2)
      : 0
    const mean = values.length ? Math.round(values.reduce((a, b) => a + b, 0) / values.length) : 0
    const last = byYear[String(yMax)] ?? 0
    return { byYear, median, mean, last }
  }

  // 取指定年度某類別/子項目的實際支出（用於與預算比對）
  function actualSpend(year, cno, sno = 0) {
    if (!db.value) return 0
    const whereSno = sno > 0 ? `AND sno=${sno}` : ''
    const r = db.value.exec(
      `SELECT SUM(spend) FROM money
       WHERE uno=${JACK_UNO} AND cno=${cno} ${whereSno}
         AND strftime('%Y', date)='${year}'`,
    )
    return Number(r?.[0]?.values?.[0]?.[0] ?? 0)
  }

  // 取指定年度的實際總收入（收入 class 的合計）
  function actualIncome(year) {
    if (!db.value) return 0
    // 找桶位為 'income' 的所有類別
    const incomeCnos = Object.entries(classBuckets.value)
      .filter(([, b]) => b === 'income')
      .map(([cno]) => Number(cno))
    if (!incomeCnos.length) {
      // fallback：用類別名稱 '收入' 查
      const cls = classes.value.find((c) => c.name === '收入')
      if (!cls) return 0
      incomeCnos.push(cls.cno)
    }
    let total = 0
    for (const cno of incomeCnos) {
      const r = db.value.exec(
        `SELECT SUM(spend) FROM money
         WHERE uno=${JACK_UNO} AND cno=${cno}
           AND strftime('%Y', date)='${year}'`,
      )
      total += Number(r?.[0]?.values?.[0]?.[0] ?? 0)
    }
    return total
  }

  return {
    db,
    fileName,
    fileHandle,
    loading,
    error,
    lastSaved,
    classes,
    subjects,
    transactions,
    classMap,
    subjectMap,
    pendingEditMno,
    requestTabSwitch,
    requestEditInEntry,
    clearPendingEdit,
    clearTabSwitch,
    // 預算
    budgetYear,
    budgetYearMeta,
    budgetItems,
    classBuckets,
    BUCKETS,
    openFile,
    saveFile,
    refreshAll,
    addTransaction,
    updateTransaction,
    deleteTransaction,
    addClass,
    renameClass,
    deleteClass,
    saveClassOrder,
    addSubject,
    renameSubject,
    deleteSubject,
    saveSubjectOrder,
    importCategories,
    // 預算方法
    allBudgetYearMetas,
    allBudgetItems,
    loadAllBudgets,
    loadBudget,
    upsertBudgetYear,
    upsertBudgetItem,
    upsertBudgetItemNote,
    exportBudgetYearJson,
    bulkUpsertBudgetItems,
    copyBudgetFromYear,
    historicalSpend,
    actualSpend,
    actualIncome,
    loadClassBuckets,
    setClassBucket,
    // 資產
    assetAccounts,
    assetSnapshots,
    loadAssets,
    upsertAssetAccount,
    deleteAssetAccount,
    upsertAssetSnapshot,
    bulkUpsertAssetSnapshots,
    deleteAssetSnapshotDate,
  }
})
