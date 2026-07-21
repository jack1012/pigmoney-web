import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parents[1] / '.data' / 'money_merged.sqlite'

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

MOVES = [
    ('2025-10-31', '2025-09-30'),  # 10月 → 9月
    ('2025-11-30', '2025-10-31'),  # 11月 → 10月
    ('2026-05-31', '2026-04-30'),  # 5月  → 4月
]
DELETE = ['2026-01-31']

# 確認操作前各日期筆數
all_dates = [src for src, _ in MOVES] + [tgt for _, tgt in MOVES] + DELETE
print('=== 操作前 ===')
for d in sorted(set(all_dates)):
    n = cur.execute('SELECT COUNT(*) FROM asset_snapshot WHERE date=?', (d,)).fetchone()[0]
    if n: print(f'  {d}: {n} 筆')

# 執行移動（順序很重要：先移 10月→9月，再移 11月→10月）
for src, tgt in MOVES:
    moved = cur.execute(
        'INSERT OR REPLACE INTO asset_snapshot (date, ano, amount) '
        'SELECT ?, ano, amount FROM asset_snapshot WHERE date=?',
        (tgt, src)
    ).rowcount
    cur.execute('DELETE FROM asset_snapshot WHERE date=?', (src,))
    print(f'移動 {src} → {tgt}：{moved} 筆')

# 刪除
for d in DELETE:
    n = cur.execute('DELETE FROM asset_snapshot WHERE date=?', (d,)).rowcount
    print(f'刪除 {d}：{n} 筆')

conn.commit()

print('\n=== 操作後（相關日期）===')
for d in sorted(set(tgt for _, tgt in MOVES)):
    n = cur.execute('SELECT COUNT(*) FROM asset_snapshot WHERE date=?', (d,)).fetchone()[0]
    print(f'  {d}: {n} 筆')

conn.close()
print('\n完成')
