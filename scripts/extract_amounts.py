"""
從 spend=0 記錄的 note 抽取金額更新到 spend 欄位。
只處理 2019 年以前（含）的記錄。

支援格式（按優先序）：
  1. 多個括弧加總:  '蔥油餅(50)+秋葵(30)'   → 80
     括弧內可含乘法: '(50*3)+(60)'         → 210
  2. 單一括弧:      '蘋果麵包(24)'           → 24
  3. N*M 乘法:      '酪梨慕斯5.5*2'         → 11
     (含「換錢/換匯」的跳過)
  4. 結尾中文+數字: '披薩16.9' / '請客850'  → 16.9 / 850
     (含「代墊」的跳過)

* 已移除單純 *N 結尾模式（多為「份數」標記非金額）

預設 dry-run；加 --apply 才會寫入。
"""
import sqlite3
import re
import sys
from collections import Counter

DB = r'D:\Projects\pigmoney-web\.data\money_merged.sqlite'
YEAR_CUTOFF = '2019'  # <= 2019 才處理

# 括弧內：純數字 或 N*M（甚至 N*M*K）
RE_PAREN_INNER = re.compile(r'\(([\d.*\s]+)\)')
RE_MULTIPLY    = re.compile(r'(\d+(?:\.\d+)?)\s*\*\s*(\d+(?:\.\d+)?)')   # 5.5*2
RE_TRAILING    = re.compile(r'[一-鿿)]\s*([\d.]+)\s*$')                  # 中文/)+數字結尾

# 整筆跳過的關鍵字（金融行為或不確定是否為花費）
SKIP_ALL = (
    '領錢', '領現', '提款', '存款', '匯款',
    '換錢', '換匯', '換美金', '換日幣', '換韓元', '換新幣', '匯率',
    '代墊',
    '給胡', '給媽', '給爸',  # 給人錢，可能是借/還/贈
)


def _eval_paren_content(s):
    """括弧內字串求值: '50' → 50, '50*3' → 150, '50*3*2' → 300"""
    s = s.strip()
    if not s:
        return None
    if '*' in s:
        try:
            parts = [float(p.strip()) for p in s.split('*')]
            r = 1.0
            for p in parts:
                r *= p
            return r
        except ValueError:
            return None
    try:
        return float(s)
    except ValueError:
        return None


def extract(note):
    """returns (amount, pattern_name) or (None, None)"""
    if not note:
        return None, None

    # 含金融關鍵字一律跳過
    if any(k in note for k in SKIP_ALL):
        return None, None

    # 抓所有括弧內可解析金額
    paren_vals = []
    for inner in RE_PAREN_INNER.findall(note):
        v = _eval_paren_content(inner)
        if v is not None:
            paren_vals.append(v)

    # 1. 多括弧加總
    if len(paren_vals) > 1:
        return sum(paren_vals), 'multi_paren'

    # 2. 單一括弧
    if len(paren_vals) == 1:
        return paren_vals[0], 'single_paren'

    # 3. N*M 乘法
    m = RE_MULTIPLY.search(note)
    if m:
        try:
            return float(m.group(1)) * float(m.group(2)), 'multiply'
        except ValueError:
            pass

    # 4. 結尾中文+數字
    m = RE_TRAILING.search(note)
    if m:
        try:
            return float(m.group(1)), 'trailing'
        except ValueError:
            pass

    return None, None


def main():
    apply_changes = '--apply' in sys.argv

    con = sqlite3.connect(DB)
    cur = con.cursor()

    cur.execute(
        f"""SELECT mno, date, note FROM money
            WHERE spend=0 AND strftime('%Y', date) <= '{YEAR_CUTOFF}'"""
    )
    rows = cur.fetchall()

    updates, skipped = [], []
    for mno, date, note in rows:
        amt, pat = extract(note)
        if amt is not None and amt > 0:
            updates.append((mno, date, amt, pat, note))
        else:
            skipped.append((mno, date, note))

    pat_counts = Counter(p for _, _, _, p, _ in updates)

    out = sys.stdout.buffer
    out.write(f'共 {len(rows)} 筆 spend=0 (<=2019)\n'.encode())
    out.write(f'  可抽取: {len(updates)}\n'.encode())
    out.write(f'  跳過:   {len(skipped)} (note 內無可解析金額)\n'.encode())
    out.write('\n模式分布:\n'.encode())
    for p, c in pat_counts.most_common():
        out.write(f'  {p:15s} {c}\n'.encode())

    # 每個模式列出 8 個樣本
    by_pat = {}
    for mno, date, amt, pat, note in updates:
        by_pat.setdefault(pat, []).append((mno, date, amt, note))

    out.write('\n=== 每種模式樣本 (前 8) ===\n'.encode())
    for pat, items in by_pat.items():
        out.write(f'\n[{pat}] {len(items)} 筆\n'.encode())
        for mno, date, amt, note in items[:8]:
            out.write(f'  {date}  {note!r:50s} 0 → {amt}\n'.encode())

    # 金額分布
    out.write('\n=== 抽取金額分布 ===\n'.encode())
    amounts = [u[2] for u in updates]
    if amounts:
        out.write(f'  最小: {min(amounts):.2f}\n'.encode())
        out.write(f'  最大: {max(amounts):.2f}\n'.encode())
        out.write(f'  總和: {sum(amounts):,.2f}\n'.encode())

    # 寫入
    if apply_changes:
        for mno, _, amt, _, _ in updates:
            cur.execute('UPDATE money SET spend=? WHERE mno=?', (amt, mno))
        con.commit()
        out.write(f'\n✓ 已更新 {len(updates)} 筆\n'.encode())
    else:
        out.write('\n*** DRY RUN (預覽模式) — 加 --apply 才會實際寫入 ***\n'.encode())

    con.close()


if __name__ == '__main__':
    main()
