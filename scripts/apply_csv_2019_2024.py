"""
用 2019-2024年度收支.csv 取代合併 DB 中 2019–2024 區段。

流程：
  1. 讀 CSV 與 DB 2019-2024
  2. 列出差異 (CSV 獨有 / DB 獨有)
  3. 確認後執行（加 --apply）：
     - 移除 DB 中 2019–2024 全部 money 記錄
     - 補上 CSV 用到、DB 沒有的子項目
     - 從 CSV 重新插入記錄
     - 清理變孤兒的類別/子項目
"""
import csv
import sqlite3
import sys
from collections import Counter, defaultdict

CSV_FILE = r'F:\Dropbox\(0)money\年度收支\2019-2024年度收支.csv'
DB_FILE  = r'D:\Projects\pigmoney-web\data\money_merged.sqlite'

YEAR_START = '2019'
YEAR_END   = '2024'


def read_csv():
    rows = []
    with open(CSV_FILE, encoding='utf-8-sig') as f:
        next(f)  # header
        for r in csv.reader(f):
            date, cls, sub, mode, amt, note = r
            try:
                spend = float(amt.strip()) if amt.strip() else 0
            except ValueError:
                spend = 0
            # 整數金額轉 int
            if spend == int(spend):
                spend = int(spend)
            rows.append((date, cls.strip(), sub.strip(), mode.strip(),
                         spend, note.strip()))
    return rows


def read_db_range():
    con = sqlite3.connect(DB_FILE)
    cur = con.cursor()
    cur.execute(f'''
        SELECT m.mno, m.date, c.name, COALESCE(s.name,''), m.mode,
               m.spend, COALESCE(m.note,'')
        FROM money m
        JOIN class c ON m.cno=c.cno
        LEFT JOIN subject s ON m.sno=s.sno
        WHERE strftime('%Y', m.date) BETWEEN '{YEAR_START}' AND '{YEAR_END}'
        ORDER BY m.date, m.mno
    ''')
    rows = [(mno, d, c, s, m, sp, n.strip()) for mno, d, c, s, m, sp, n in cur.fetchall()]
    con.close()
    return rows


def fp(r_csv_or_db):
    """fingerprint: (date, class, subject, mode, spend, note)"""
    # CSV: (date, cls, sub, mode, spend, note)
    # DB:  (mno, date, cls, sub, mode, spend, note)
    if len(r_csv_or_db) == 7:
        _, d, c, s, m, sp, n = r_csv_or_db
    else:
        d, c, s, m, sp, n = r_csv_or_db
    return (d, c, s, m, float(sp), n)


def fp_loose(r):
    """無 note 的 fingerprint，用於 note 略不同但其他都相同的判斷"""
    if len(r) == 7:
        _, d, c, s, m, sp, _ = r
    else:
        d, c, s, m, sp, _ = r
    return (d, c, s, m, float(sp))


def main():
    apply_changes = '--apply' in sys.argv

    out = sys.stdout.buffer
    csv_rows = read_csv()
    db_rows  = read_db_range()

    out.write(f'CSV: {len(csv_rows)} 筆\nDB:  {len(db_rows)} 筆\n\n'.encode())

    # 嚴格 fingerprint 比對
    csv_fps = Counter(fp(r) for r in csv_rows)
    db_fps  = Counter(fp(r) for r in db_rows)

    csv_only = csv_fps - db_fps  # 嚴格只 CSV 有（含次數差）
    db_only  = db_fps - csv_fps

    # 進一步區分：note 略不同 vs 完全不同
    csv_loose = Counter(fp_loose(r) for r in csv_rows)
    db_loose  = Counter(fp_loose(r) for r in db_rows)

    note_diff = []        # 其他都同，只差 note
    csv_truly_unique = []
    db_truly_unique = []

    # 用 loose 比對找「note 略不同」的記錄
    common_loose = csv_loose & db_loose
    csv_only_loose = csv_loose - db_loose
    db_only_loose  = db_loose - csv_loose

    # CSV 獨有（連 loose 都不一致）
    csv_unique_keys = set(csv_only_loose)
    db_unique_keys  = set(db_only_loose)

    for r in csv_rows:
        if fp_loose(r) in csv_unique_keys:
            csv_truly_unique.append(r)
    for r in db_rows:
        if fp_loose(r) in db_unique_keys:
            db_truly_unique.append(r)

    # note 略不同：兩邊 loose 都有，但嚴格 fp 不同
    # 收集兩邊資料按 loose key 分組
    csv_by_loose = defaultdict(list)
    db_by_loose  = defaultdict(list)
    for r in csv_rows: csv_by_loose[fp_loose(r)].append(r)
    for r in db_rows:  db_by_loose[fp_loose(r)].append(r)

    for k in common_loose.keys():
        cs = csv_by_loose[k]
        ds = db_by_loose[k]
        if len(cs) != len(ds):
            # 筆數不同也算差異
            continue
        for c_r, d_r in zip(cs, ds):
            if c_r[5] != d_r[6]:  # note 不同
                note_diff.append((c_r, d_r))

    out.write('=== 差異統計 ===\n'.encode())
    out.write(f'  CSV 獨有: {len(csv_truly_unique)} 筆\n'.encode())
    out.write(f'  DB  獨有: {len(db_truly_unique)} 筆\n'.encode())
    out.write(f'  其他都同、僅 note 略不同: {len(note_diff)} 筆 (不重要，本次會用 CSV 的 note)\n'.encode())

    # ── 列出 CSV 獨有 ──
    out.write('\n=== CSV 獨有 (將會新增到 DB) ===\n'.encode())
    csv_truly_unique.sort()
    for d, c, s, m, sp, n in csv_truly_unique:
        note = n[:40] + '...' if len(n) > 40 else n
        out.write(f'  + {d} [{c}/{s}] {m} {sp:>8}  {note}\n'.encode())

    # ── 列出 DB 獨有 ──
    out.write('\n=== DB 獨有 (將會從 DB 移除) ===\n'.encode())
    db_truly_unique.sort(key=lambda r: (r[1], r[0]))
    for mno, d, c, s, m, sp, n in db_truly_unique:
        note = n[:40] + '...' if len(n) > 40 else n
        out.write(f'  - {d} [{c}/{s}] {m} {sp:>8}  {note}\n'.encode())

    if not apply_changes:
        out.write('\n*** DRY RUN：加 --apply 才會實際寫入 ***\n'.encode())
        return

    # ── 執行替換 ──────────────────────────────
    out.write('\n=== 開始替換 ===\n'.encode())
    con = sqlite3.connect(DB_FILE)
    cur = con.cursor()

    # 取得目前的 class / subject 對應 name → cno / (cname, sname) → sno
    cur.execute('SELECT cno, name, order_id FROM class ORDER BY order_id')
    class_rows = cur.fetchall()
    class_to_cno = {nm: cno for cno, nm, _ in class_rows}
    max_cno = max(c for c, _, _ in class_rows)
    max_order = max(o for _, _, o in class_rows)

    cur.execute('''SELECT s.sno, c.name, s.name, s.order_id
                   FROM subject s JOIN class c ON s.cno=c.cno''')
    sub_rows = cur.fetchall()
    pair_to_sno = {(cn, sn): sno for sno, cn, sn, _ in sub_rows}
    max_sno = max(s for s, _, _, _ in sub_rows)
    max_sorder = max(o for _, _, _, o in sub_rows)

    # 補上 CSV 用到但 DB 沒有的 class / subject
    new_classes = 0
    new_subjects = 0
    for d, c, s, m, sp, n in csv_rows:
        if c not in class_to_cno:
            max_cno += 1
            max_order += 1
            cur.execute(
                'INSERT INTO class (cno, uno, name, order_id) VALUES (?, 1, ?, ?)',
                (max_cno, c, max_order),
            )
            class_to_cno[c] = max_cno
            new_classes += 1
        if s and (c, s) not in pair_to_sno:
            max_sno += 1
            max_sorder += 1
            cur.execute(
                'INSERT INTO subject (sno, cno, uno, name, order_id) VALUES (?, ?, 1, ?, ?)',
                (max_sno, class_to_cno[c], s, max_sorder),
            )
            pair_to_sno[(c, s)] = max_sno
            new_subjects += 1

    out.write(f'  新增類別: {new_classes}\n'.encode())
    out.write(f'  新增子項目: {new_subjects}\n'.encode())

    # 移除 DB 中 2019-2024 的 money 記錄
    cur.execute(f'''DELETE FROM money
                    WHERE strftime('%Y', date) BETWEEN '{YEAR_START}' AND '{YEAR_END}'
                 ''')
    out.write(f'  移除 {cur.rowcount} 筆舊記錄\n'.encode())

    # 取下一個 mno
    cur.execute('SELECT MAX(mno) FROM money')
    next_mno = (cur.fetchone()[0] or 0) + 1

    # 從 CSV 插入
    inserted = 0
    for d, c, s, mode, sp, n in csv_rows:
        cno = class_to_cno[c]
        sno = pair_to_sno.get((c, s), 0)
        cur.execute(
            'INSERT INTO money (mno, uno, cno, sno, spend, date, note, mode) '
            'VALUES (?, 1, ?, ?, ?, ?, ?, ?)',
            (next_mno, cno, sno, sp, d, n, mode),
        )
        next_mno += 1
        inserted += 1
    out.write(f'  插入 {inserted} 筆新記錄\n'.encode())

    # 清理變孤兒的 class / subject
    cur.execute('''DELETE FROM subject WHERE sno NOT IN
                   (SELECT DISTINCT sno FROM money WHERE sno > 0)''')
    orphan_sub = cur.rowcount
    cur.execute('''DELETE FROM class WHERE cno NOT IN
                   (SELECT DISTINCT cno FROM money)''')
    orphan_cls = cur.rowcount
    out.write(f'  清理孤兒類別: {orphan_cls}  孤兒子項目: {orphan_sub}\n'.encode())

    con.commit()

    # 驗證
    cur.execute('SELECT COUNT(*) FROM money')
    n_total = cur.fetchone()[0]
    cur.execute('SELECT COUNT(*) FROM class')
    n_class = cur.fetchone()[0]
    cur.execute('SELECT COUNT(*) FROM subject')
    n_sub = cur.fetchone()[0]
    out.write(f'\n=== 完成 ===\n'.encode())
    out.write(f'  money: {n_total} 筆  /  class: {n_class}  /  subject: {n_sub}\n'.encode())

    cur.execute(f'''SELECT strftime('%Y',date), COUNT(*) FROM money
                    GROUP BY 1 ORDER BY 1''')
    out.write('  逐年:\n'.encode())
    for yr, cnt in cur.fetchall():
        mark = ' ← 已替換' if YEAR_START <= yr <= YEAR_END else ''
        out.write(f'    {yr}: {cnt}{mark}\n'.encode())
    con.close()


if __name__ == '__main__':
    main()
