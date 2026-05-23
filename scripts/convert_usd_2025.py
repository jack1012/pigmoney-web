"""
換算 2025 美國行的美金記錄到台幣。

對象：子項目 = '美國行2025LA(US)' 共 62 筆
匯率：32.7 NTD/USD
動作：
  1. spend × 32.7 → 四捨五入到整數
  2. 子項目從「美國行2025LA(US)」改為「美國行2025LA」
  3. 清掉空的「美國行2025LA(US)」子項目

預設 dry-run；加 --apply 才會寫入。
原始美金金額在 note 文字中已保留，可追溯。
"""
import sqlite3
import sys

DB = r'D:\Projects\pigmoney-web\data\money_merged.sqlite'
RATE = 32.7
SRC_NAME = '美國行2025LA(US)'
DST_NAME = '美國行2025LA'


def main():
    apply_changes = '--apply' in sys.argv
    out = sys.stdout.buffer

    con = sqlite3.connect(DB)
    cur = con.cursor()

    # 取得來源/目標 sno
    cur.execute('SELECT sno, cno FROM subject WHERE name=?', (SRC_NAME,))
    r = cur.fetchone()
    if not r:
        out.write(f'找不到子項目「{SRC_NAME}」\n'.encode())
        return
    src_sno, cno = r

    cur.execute('SELECT sno FROM subject WHERE name=? AND cno=?', (DST_NAME, cno))
    r = cur.fetchone()
    if not r:
        out.write(f'找不到目標子項目「{DST_NAME}」\n'.encode())
        return
    dst_sno = r[0]

    out.write(f'來源 sno={src_sno}  「{SRC_NAME}」\n'.encode())
    out.write(f'目標 sno={dst_sno}  「{DST_NAME}」\n'.encode())
    out.write(f'匯率 {RATE} NTD/USD\n\n'.encode())

    # 取得要換算的記錄
    cur.execute(
        'SELECT mno, date, spend, COALESCE(note, "") FROM money '
        'WHERE sno=? ORDER BY date, mno', (src_sno,))
    rows = cur.fetchall()
    out.write(f'共 {len(rows)} 筆待換算\n'.encode())

    # 預覽 + 統計
    total_usd = 0
    total_ntd = 0
    out.write('\n=== 換算預覽 (前 10) ===\n'.encode())
    for i, (mno, d, sp, n) in enumerate(rows):
        new_ntd = round(sp * RATE)
        total_usd += sp
        total_ntd += new_ntd
        if i < 10:
            out.write(f'  {d}  USD {sp:>7.2f}  →  NTD {new_ntd:>6}   {n[:40]}\n'.encode())

    out.write(f'\n總計: USD {total_usd:,.2f}  →  NTD {total_ntd:,}\n'.encode())

    if not apply_changes:
        out.write('\n*** DRY RUN：加 --apply 才會實際寫入 ***\n'.encode())
        return

    # ── 套用 ────────────────────────────────────────
    for mno, _, sp, _ in rows:
        cur.execute(
            'UPDATE money SET spend=?, sno=? WHERE mno=?',
            (round(sp * RATE), dst_sno, mno),
        )

    # 清掉空的舊子項目
    cur.execute('SELECT COUNT(*) FROM money WHERE sno=?', (src_sno,))
    if cur.fetchone()[0] == 0:
        cur.execute('DELETE FROM subject WHERE sno=?', (src_sno,))
        out.write(f'\n✓ 已刪除空的子項目「{SRC_NAME}」\n'.encode())

    con.commit()

    # 驗證
    cur.execute(
        'SELECT COUNT(*), MIN(spend), MAX(spend), SUM(spend) FROM money '
        'WHERE sno=?', (dst_sno,))
    n, mn, mx, total = cur.fetchone()
    out.write(f'\n=== 完成 ===\n'.encode())
    out.write(f'  「{DST_NAME}」現在 {n} 筆  spend {mn} ~ {mx}  合計 {total:,}\n'.encode())

    con.close()


if __name__ == '__main__':
    main()
