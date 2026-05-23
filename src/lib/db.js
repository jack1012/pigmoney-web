import initSqlJs from 'sql.js'
import wasmUrl from 'sql.js/dist/sql-wasm.wasm?url'

let SQL = null

export async function getSQL() {
  if (!SQL) {
    SQL = await initSqlJs({ locateFile: () => wasmUrl })
  }
  return SQL
}

export async function openDbFromFile(file) {
  const sql = await getSQL()
  const buf = await file.arrayBuffer()
  const db = new sql.Database(new Uint8Array(buf))
  ensureBudgetSchema(db)
  return db
}

export function rowsToObjects(result) {
  if (!result || result.length === 0) return []
  const { columns, values } = result[0]
  return values.map((row) =>
    Object.fromEntries(columns.map((col, i) => [col, row[i]])),
  )
}

// ── Budget schema migration ─────────────────────────────
// 確保預算相關表存在；舊檔開啟時也會自動補表。
export function ensureBudgetSchema(db) {
  db.run(`
    CREATE TABLE IF NOT EXISTS budget_year (
      year        INTEGER PRIMARY KEY,
      total       INTEGER,
      note        TEXT,
      ratio_life  REAL DEFAULT 0.30,
      ratio_fixed REAL DEFAULT 0.20,
      ratio_want  REAL DEFAULT 0.10,
      ratio_save  REAL DEFAULT 0.40
    );
  `)
  // 向後相容：舊檔若已有 budget_year 但缺少新欄位則補上
  const alterCols = [
    ['ratio_life',  'REAL DEFAULT 0.30'],
    ['ratio_fixed', 'REAL DEFAULT 0.20'],
    ['ratio_want',  'REAL DEFAULT 0.10'],
    ['ratio_save',  'REAL DEFAULT 0.40'],
  ]
  for (const [col, def] of alterCols) {
    try { db.run(`ALTER TABLE budget_year ADD COLUMN ${col} ${def}`) } catch (_) { /* 已存在 */ }
  }
  // 移除舊欄位 income（合併為 total），SQLite 不支援 DROP COLUMN，保留舊資料無妨

  db.run(`
    CREATE TABLE IF NOT EXISTS budget_item (
      year    INTEGER NOT NULL,
      cno     INTEGER NOT NULL,
      sno     INTEGER NOT NULL DEFAULT 0,
      month   INTEGER NOT NULL DEFAULT 0,
      amount  INTEGER,
      formula TEXT,
      note    TEXT,
      PRIMARY KEY (year, cno, sno, month)
    );
  `)
  // 舊檔補欄位
  try { db.run(`ALTER TABLE budget_item ADD COLUMN note TEXT`) } catch (_) { /* 已存在 */ }
  db.run(`
    CREATE TABLE IF NOT EXISTS budget_project (
      pno            INTEGER PRIMARY KEY AUTOINCREMENT,
      year           INTEGER NOT NULL,
      cno            INTEGER,
      sno            INTEGER,
      name           TEXT,
      amount         INTEGER,
      planned_month  INTEGER,
      status         TEXT DEFAULT 'planned',
      note           TEXT
    );
  `)
  // 類別→桶位對應表（全局，不分年）
  db.run(`
    CREATE TABLE IF NOT EXISTS budget_class_bucket (
      cno    INTEGER PRIMARY KEY,
      bucket TEXT  -- 'life' | 'fixed' | 'save'
    );
  `)
}
