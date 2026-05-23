"""
合併歷年 .sqlite 記帳檔 → 單一 money_merged.sqlite

策略：
  1. 用 money2026.sqlite 的 class 排序當主架構，其他檔案出現過但 2026 沒有
     的 class 名稱補在最後
  2. 子項目按 (class_name, subject_name) 合併，順序以 2026 為主
  3. 所有 uno 都映射到合併檔的 uno=1
  4. money 記錄做指紋 (date, class_name, subject_name, spend, note, mode) 去重
"""
import os
import sqlite3
import sys
from collections import OrderedDict

# ── 來源檔案清單 ──────────────────────────────────────────
DATA_DIR_LOCAL = r'D:\Projects\pigmoney-web\data'
DATA_DIR_DROPBOX = r'F:\Dropbox\(0)money'

# 主架構參考：類別與子項目順序以這個檔為主
MASTER_FILE = os.path.join(DATA_DIR_DROPBOX, 'money2026.sqlite')

SOURCES = [
    # Jack 主帳（每年取最完整版）
    os.path.join(DATA_DIR_LOCAL,   'money.sqlite'),                    # 2009-2017
    os.path.join(DATA_DIR_DROPBOX, '年度收支', 'money2019.sqlite'),
    os.path.join(DATA_DIR_DROPBOX, '年度收支', 'money2020.sqlite'),
    os.path.join(DATA_DIR_DROPBOX, '年度收支', 'money2021.sqlite'),
    os.path.join(DATA_DIR_DROPBOX, '年度收支', 'money2022.sqlite'),
    os.path.join(DATA_DIR_LOCAL,   'money2023.sqlite'),
    os.path.join(DATA_DIR_LOCAL,   'money2024.sqlite'),
    os.path.join(DATA_DIR_LOCAL,   'money2025.sqlite'),
    MASTER_FILE,                                                       # 2026
    # Cassie 相關（uno 都映射到 1）
    os.path.join(DATA_DIR_DROPBOX, 'Cassie', 'cassie.sqlite'),
    os.path.join(DATA_DIR_DROPBOX, '2010cassie_money.sqlite'),
    os.path.join(DATA_DIR_DROPBOX, '2011cassie_money.sqlite'),
    os.path.join(DATA_DIR_DROPBOX, '2012cassie_money.sqlite'),
    os.path.join(DATA_DIR_DROPBOX, 'cassie_money.sqlite'),
]

OUTPUT_FILE = os.path.join(DATA_DIR_LOCAL, 'money_merged.sqlite')

# ── 類別重映射：來源類別名稱 → 合併後類別名稱 ─────────────
# Cassie 的「住」實際是 2011 新加坡旅行的飯店小費，併入「娛樂」
CLASS_REMAP = {
    '住': '娛樂',
}


def open_src(path):
    con = sqlite3.connect(path)
    con.text_factory = lambda b: b.decode('utf-8', errors='replace') if isinstance(b, bytes) else b
    return con


def read_classes(con):
    """讀 uno=1 所有類別  → [(name, order_id), ...]"""
    cur = con.cursor()
    cur.execute('SELECT cno, name, order_id FROM class WHERE uno=1 ORDER BY order_id, cno')
    return cur.fetchall()  # list of (cno, name, order_id)


def read_subjects(con):
    """讀 uno=1 所有子項目  → [(cno, sno, name, order_id), ...]"""
    cur = con.cursor()
    cur.execute('SELECT cno, sno, name, order_id FROM subject WHERE uno=1 ORDER BY cno, order_id, sno')
    return cur.fetchall()


def read_money(con):
    """讀所有 money 記錄（不限 uno）→ [(uno, cno, sno, spend, date, note, mode), ...]"""
    cur = con.cursor()
    cur.execute('SELECT uno, cno, sno, spend, date, note, mode FROM money')
    return cur.fetchall()


def main():
    # ── 1. 收集所有類別、子項目（按名稱合併） ──────────────
    # 先讀主架構檔
    master_con = open_src(MASTER_FILE)
    master_classes = read_classes(master_con)        # [(cno, name, order_id), ...]
    master_subjects = read_subjects(master_con)
    master_class_name_by_cno = {cno: name for cno, name, _ in master_classes}
    master_con.close()

    # 統一 class 順序：master 在前
    class_order = OrderedDict()  # name → new_cno (起始 1)
    for cno, name, _ in master_classes:
        class_order[name] = None  # 先佔位

    # 統一 subject 順序：master 在前，key = (class_name, subject_name)
    subject_order = OrderedDict()
    for cno, sno, name, _ in master_subjects:
        cname = master_class_name_by_cno.get(cno)
        if cname:
            subject_order[(cname, name)] = None

    # ── 2. 掃描所有來源，補上 master 沒有的類別/子項目 ──────
    all_money_rows = []  # list of (src_label, uno, cno_name, sno_name_or_none, spend, date, note, mode)

    for src in SOURCES:
        if not os.path.exists(src):
            print(f'  [SKIP] not found: {src}')
            continue
        label = os.path.basename(src)
        con = open_src(src)
        cur = con.cursor()

        # 該檔的 cno → name, sno → (cno, sname)
        cur.execute('SELECT cno, name FROM class')
        cno_to_name = {cno: name for cno, name in cur.fetchall()}

        cur.execute('SELECT sno, cno, name FROM subject')
        sno_to_cname_sname = {sno: (cno_to_name.get(cno), name) for sno, cno, name in cur.fetchall()}

        # 補上新類別（套用重映射）
        for nm in cno_to_name.values():
            if nm:
                nm = CLASS_REMAP.get(nm, nm)
                if nm not in class_order:
                    class_order[nm] = None

        # 補上新子項目（類別經過重映射）
        for sno, (cname, sname) in sno_to_cname_sname.items():
            if cname and sname:
                cname = CLASS_REMAP.get(cname, cname)
                key = (cname, sname)
                if key not in subject_order:
                    subject_order[key] = None

        # 讀 money（類別經過重映射）
        rows = read_money(con)
        for uno, cno, sno, spend, date, note, mode in rows:
            cname = cno_to_name.get(cno)
            if not cname:
                continue
            cname = CLASS_REMAP.get(cname, cname)
            sname = None
            if sno:
                pair = sno_to_cname_sname.get(sno)
                if pair:
                    sname = pair[1]
            all_money_rows.append((label, uno, cname, sname, spend, date, note, mode))

        con.close()

    # ── 3. 指派新 cno / sno ──────────────────────────────
    for i, name in enumerate(class_order.keys(), start=1):
        class_order[name] = i
    for i, key in enumerate(subject_order.keys(), start=1):
        subject_order[key] = i

    print(f'Unified classes: {len(class_order)}')
    print(f'Unified subjects: {len(subject_order)}')

    # ── 4. 去重 money ───────────────────────────────────
    seen = set()
    dedup_rows = []
    dup_count = 0
    skip_no_class = 0
    for label, uno, cname, sname, spend, date, note, mode in all_money_rows:
        if cname not in class_order:
            skip_no_class += 1
            continue
        # fingerprint: 全部對齊到合併後的名稱與值
        sname_key = sname or ''
        note_key = note or ''
        fp = (date, cname, sname_key, spend, note_key, mode)
        if fp in seen:
            dup_count += 1
            continue
        seen.add(fp)
        new_cno = class_order[cname]
        new_sno = subject_order.get((cname, sname)) if sname else None
        dedup_rows.append((1, new_cno, new_sno, spend, date, note or '', mode))

    print(f'Total raw money rows:   {len(all_money_rows)}')
    print(f'After dedup:            {len(dedup_rows)}')
    print(f'Duplicates removed:     {dup_count}')
    print(f'Skipped (no class):     {skip_no_class}')

    # ── 5. 寫入新檔 ─────────────────────────────────────
    if os.path.exists(OUTPUT_FILE):
        os.remove(OUTPUT_FILE)
    out = sqlite3.connect(OUTPUT_FILE)
    out_cur = out.cursor()

    # 用 master 的 schema 完整建表
    schema = [
        '''CREATE TABLE `class` (`cno` INTEGER PRIMARY KEY DEFAULT '', `uno` INTEGER NOT NULL DEFAULT '',
            `name` VARCHAR NOT NULL DEFAULT '', `order_id` INTEGER NOT NULL DEFAULT '-1')''',
        '''CREATE TABLE `subject` (`sno` INTEGER PRIMARY KEY NOT NULL DEFAULT '', `cno` INTEGER NOT NULL DEFAULT '',
            `uno` INTEGER NOT NULL DEFAULT '', `name` VARCHAR NOT NULL DEFAULT '',
            `order_id` INTEGER NOT NULL DEFAULT '-1')''',
        '''CREATE TABLE `money` (`mno` INTEGER PRIMARY KEY NOT NULL DEFAULT '', `uno` INTEGER NOT NULL DEFAULT '',
            `cno` INTEGER NOT NULL DEFAULT '', `sno` INTEGER NOT NULL DEFAULT '', `spend` INTEGER NOT NULL DEFAULT '',
            `date` DATETIME NOT NULL DEFAULT '', `note` TEXT DEFAULT '', `mode` TEXT NOT NULL DEFAULT '現金支出')''',
        '''CREATE TABLE `user` (`uno` INTEGER PRIMARY KEY DEFAULT '', `uid` VARCHAR NOT NULL DEFAULT '',
            `passwd` VARCHAR DEFAULT '', `needPwd` INTEGER NOT NULL DEFAULT '0')''',
        '''CREATE TABLE `info` (`app_version` VARCHAR, `db_version` VARCHAR)''',
        '''CREATE TABLE `clock` (`cno` INTEGER PRIMARY KEY NOT NULL, `uno` INTEGER NOT NULL,
            `isOn` INTEGER NOT NULL DEFAULT 1, `name` VARCHAR, `remind_before` INTEGER NOT NULL DEFAULT 0,
            `last_remind` DATETIME, `pause` INTEGER NOT NULL DEFAULT 0, `note` TEXT,
            `cycle_mode` INTEGER NOT NULL DEFAULT 0, `week` INTEGER, `day` INTEGER, `date` DATETIME)''',
    ]
    for sql in schema:
        out_cur.execute(sql)

    # 寫 user
    out_cur.execute("INSERT INTO user (uno, uid, passwd, needPwd) VALUES (1, 'jack', '', 0)")

    # 寫 info
    out_cur.execute("INSERT INTO info (app_version, db_version) VALUES ('merged', 'Beta 5.0')")

    # 寫 class
    for name, new_cno in class_order.items():
        out_cur.execute(
            'INSERT INTO class (cno, uno, name, order_id) VALUES (?, 1, ?, ?)',
            (new_cno, name, new_cno),
        )

    # 寫 subject
    for (cname, sname), new_sno in subject_order.items():
        new_cno = class_order[cname]
        out_cur.execute(
            'INSERT INTO subject (sno, cno, uno, name, order_id) VALUES (?, ?, 1, ?, ?)',
            (new_sno, new_cno, sname, new_sno),
        )

    # 寫 money
    for i, (uno, cno, sno, spend, date, note, mode) in enumerate(dedup_rows, start=1):
        out_cur.execute(
            'INSERT INTO money (mno, uno, cno, sno, spend, date, note, mode) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
            (i, uno, cno, sno if sno is not None else 0, spend, date, note, mode),
        )

    out.commit()
    out.close()

    # ── 6. 驗證輸出 ─────────────────────────────────────
    print(f'\nOutput: {OUTPUT_FILE}')
    con = sqlite3.connect(OUTPUT_FILE)
    cur = con.cursor()
    cur.execute('SELECT COUNT(*) FROM money')
    print(f'  money rows:    {cur.fetchone()[0]}')
    cur.execute('SELECT COUNT(*) FROM class')
    print(f'  class rows:    {cur.fetchone()[0]}')
    cur.execute('SELECT COUNT(*) FROM subject')
    print(f'  subject rows:  {cur.fetchone()[0]}')
    cur.execute("SELECT strftime('%Y',date), COUNT(*) FROM money GROUP BY 1 ORDER BY 1")
    print('  rows by year:')
    for yr, cnt in cur.fetchall():
        print(f'    {yr}: {cnt}')
    con.close()


if __name__ == '__main__':
    main()
