import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parents[1] / '.data' / 'money_merged.sqlite'

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

print('=== 2026-04-30 快照 ===')
for r in cur.execute('''
    SELECT s.date, s.ano, a.category, a.name, s.amount
    FROM asset_snapshot s JOIN asset_account a ON s.ano=a.ano
    WHERE s.date=? ORDER BY a.category, s.ano
''', ('2026-04-30',)):
    print(f'  [{r[2]}] {r[3]}({r[1]}): {r[4]:,}')

print()
print('=== 2026 年所有快照日期 ===')
for r in cur.execute("SELECT date, COUNT(*), SUM(amount) FROM asset_snapshot WHERE date LIKE '2026%' GROUP BY date"):
    print(f'  {r[0]}: {r[1]} 筆, 合計 {r[2]:,}')

print()
print('=== 現金/投資 帳戶清單 ===')
for r in cur.execute("SELECT ano, category, name FROM asset_account WHERE category IN ('現金','投資') ORDER BY category, ano"):
    print(f'  ano={r[0]} [{r[1]}] {r[2]}')
