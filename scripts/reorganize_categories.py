"""
階段 1+2+3 整合：按 pigmoney-categories.json 簡化分類與子分類

執行內容：
  階段 1 - 14 筆未分類項目 + 修車跨類別
  階段 2 - 類別合併（基金/買賣/導師費）+ 還原「專案項目-」
  階段 3 - 子項目大規模簡化

預設 dry-run，加 --apply 才寫入
"""
import sqlite3
import sys
from collections import defaultdict

DB = r'D:\Projects\pigmoney-web\data\money_merged.sqlite'


# ── 對應規則 ──────────────────────────────────────────
# 按 (舊類別, 舊子項目) → (新類別, 新子項目)，所有交易記錄按這個批次 UPDATE

MAPPING = {
    # ─ 階段 2：類別整併 ─
    # 基金 → 投資/基金（新增子項目）
    ('基金', '手續費'): ('投資', '基金'),
    ('基金', '購入'):   ('投資', '基金'),
    # 買賣 → 投資/股票
    ('買賣', '賣出'): ('投資', '股票'),
    ('買賣', '購入'): ('投資', '股票'),
    # 導師費 → 收入/其他
    ('導師費', '請吃飯'): ('收入', '其他'),
    ('導師費', '飲料'):   ('收入', '其他'),
    ('導師費', '其他'):   ('收入', '其他'),

    # ─ 還原「專案項目-」（硬體設備類）─
    # 從專案項目把設備類搬出
    ('專案項目', '家俱設備'):  ('專案項目-', '家俱設備'),
    ('專案項目', '家俱'):      ('專案項目-', '家俱設備'),
    ('專案項目', '廚房設備'):  ('專案項目-', '廚房設備'),
    ('專案項目', '衛生設備'):  ('專案項目-', '衛生設備'),
    ('專案項目', '網通設備'):  ('專案項目-', '網通設備'),
    ('專案項目', '辦公設備'):  ('專案項目-', '辦公設備'),
    ('專案項目', '寢室用品'):  ('專案項目-', '寢俱用聘'),

    # ─ 階段 3：子項目簡化 ─
    # [食]
    ('食', '水果'):  ('食', '零食/飲料'),
    ('食', '點心'):  ('食', '零食/飲料'),
    ('食', '飲料'):  ('食', '零食/飲料'),
    ('食', '醬料'):  ('食', '食材'),

    # [衣]
    ('衣', '內褲內衣'): ('衣', '內衣'),
    ('衣', '褲裙'):     ('衣', '褲子'),
    ('衣', '飾品'):     ('衣', '髮飾'),

    # [生活]
    ('生活', '美髮'):     ('生活', '剪髮'),
    ('生活', '洗衣烘衣'): ('生活', '洗衣清潔'),
    ('生活', '生活用品'): ('生活', '日常用品'),
    ('生活', '其他'):     ('生活', '日常用品'),
    ('生活', '寢具用品'): ('生活', '日常用品'),
    ('生活', 'Skype'):    ('生活', '電子用品'),
    ('生活', '手機'):     ('生活', '電子用品'),
    ('生活', '電子商品'): ('生活', '電子用品'),
    ('生活', '書'):       ('生活', '書文具'),
    ('生活', '文具'):     ('生活', '書文具'),
    ('生活', '保健藥品'): ('生活', '保健用品'),
    ('生活', '藥品'):     ('生活', '保健用品'),
    ('生活', '醫藥'):     ('生活', '保健用品'),
    ('生活', '保養彩妝'): ('生活', '衛浴清潔'),
    # 跨類別
    ('生活', '衣服'):     ('衣', '上衣'),
    ('生活', '住宿'):     ('房屋', '管理費'),
    ('生活', '宿舍費用'): ('房屋', '管理費'),

    # [交通]
    ('交通', 'etag'):       ('交通', 'ETAG高速公路'),
    ('交通', '加油'):       ('交通', '加油充電'),
    ('交通', '悠遊卡'):     ('交通', '腳踏車公車計程車'),
    ('交通', '腳踏車公車'): ('交通', '腳踏車公車計程車'),
    ('交通', '計程車'):     ('交通', '腳踏車公車計程車'),
    ('交通', '車票'):       ('交通', '腳踏車公車計程車'),
    ('交通', '交通費用'):   ('交通', '腳踏車公車計程車'),
    ('交通', '亞聯費用'):   ('交通', '腳踏車公車計程車'),
    ('交通', '腳踏車'):     ('交通', '腳踏車公車計程車'),
    # 跨類別
    ('交通', '證件'):       ('車', '其他'),  # 國際駕照

    # [教育]
    ('教育', '學費'): ('教育', '學雜費'),

    # [娛樂]
    ('娛樂', '紀念品'): ('娛樂', '郊遊'),
    ('娛樂', '出遊'):   ('娛樂', '郊遊'),
    ('娛樂', '撲克牌'): ('娛樂', '郊遊'),
    ('娛樂', '小費'):   ('娛樂', '郊遊'),
    ('娛樂', '年費'):   ('娛樂', '門票(年費)'),
    ('娛樂', '門票'):   ('娛樂', '門票(年費)'),
    ('娛樂', 'CD'):     ('娛樂', '遊戲片'),
    ('娛樂', '彩眷'):   ('娛樂', '彩卷'),
    # 跨類別
    ('娛樂', '捐獻'):   ('特殊', '其他'),
    # 娛樂/禮物 343 筆要按 note 分流（在程式裡處理）

    # [特殊]
    ('特殊', '家人'):       ('特殊', '禮金'),   # 全部都是紅包/禮金
    ('特殊', '假牙'):       ('特殊', '醫療費用'),
    ('特殊', '生產費用'):   ('特殊', '生產'),
    ('特殊', '請客'):       ('特殊', '聚餐費'),
    # 跨類別
    ('特殊', '出國'):       ('專案項目', '出國'),
    ('特殊', '旅遊準備金'): ('專案項目', '旅遊準備金'),
    ('特殊', '研討會'):     ('專案項目', '研討會'),
    ('特殊', '學費'):       ('教育', '學雜費'),
    ('特殊', '飲料'):       ('食', '零食/飲料'),
    # 特殊/3C家電 6 筆按 mno 分流（在程式裡處理）
    # 特殊/勞健保費 2 筆按 note 分流（在程式裡處理）

    # [房屋]
    ('房屋', '家具'):     ('專案項目-', '家俱設備'),
    ('房屋', '房屋火險'): ('房屋', '保險'),

    # [稅金]
    ('稅金', '地價稅'): ('稅金', '地價稅(12/1)'),
    ('稅金', '房屋稅'): ('稅金', '房屋稅(6/1)'),

    # [車]
    ('車', '保險'): ('保險', '車險'),

    # [收入]
    ('收入', '兼差'):     ('收入', '政德薪水'),
    ('收入', '投資利潤'): ('收入', '投資利得'),
    ('收入', '政德薪資'): ('收入', '政德薪水'),
    ('收入', '薪水'):     ('收入', '政德薪水'),
}


# 階段 1：14 筆未分類項目 + 修車（按 mno）
STAGE1_FIXES = [
    # (mno, new_class, new_subject)
    (1341,  '收入', '其他'),  # 演講費代墊29760
    (694,   '收入', '其他'),  # 全家禮卷
    (1342,  '收入', '其他'),  # 演講費代墊3200
    (1198,  '收入', '其他'),  # 紅包(爸爸+媽媽)
    (1199,  '收入', '其他'),  # 紅包(爺爺奶奶)
    (1200,  '收入', '其他'),  # 紅包(吳怡亭爸爸)
    (763,   '收入', '其他'),  # 自強活動補助費
    (25091, '收入', '其他'),  # 媽媽給褲子錢多給
    (25092, '收入', '其他'),  # 爸爸給我出遊錢
    (7161,  '交通', '加油充電'),  # 加油
    (6416,  '娛樂', '門票(年費)'),  # 音樂票*2
    (4396,  '稅金', '所得稅'),  # 2012所得稅
    (20354, '娛樂', '旅館'),  # 押金*100
    (25110, '車',   '保養'),  # 修車(2200) — 跨類別到車
]

# 特殊/3C家電 6 筆按 mno 分流
STAGE3_3C_FIXES = [
    # (mno_pattern_or_note, new_class, new_subject)
    # 因為要按 note 內容判斷，這裡用 SQL LIKE
    ('sony相機',    '專案項目-', '視聽設備'),
    ('ipad2',       '專案項目-', '視聽設備'),
    ('Mac book',    '專案項目-', '視聽設備'),
    ('skype話費',   '生活',     '電話網路費'),
    ('掃地機器人',  '專案項目-', '健康家電'),
    ('高壓水柱',    '專案項目-', '工具設備'),
]


# 需要事先建立的類別 (按 JSON)
NEW_CLASSES = [
    # name, order_id (相對位置會調整)
    ('專案項目-', 14),
]

# 需要事先建立的子項目 (按 JSON 結構)
NEW_SUBJECTS = [
    # (class_name, subject_name)
    ('投資',     '基金'),
    ('專案項目', '出國'),
    ('專案項目', '旅遊準備金'),
    ('專案項目', '研討會'),
    ('專案項目-', '家俱設備'),
    ('專案項目-', '寢俱用聘'),
    ('專案項目-', '視聽設備'),
    ('專案項目-', '衛生設備'),
    ('專案項目-', '空調設備'),
    ('專案項目-', '廚房設備'),
    ('專案項目-', '網通設備'),
    ('專案項目-', '其他'),
    ('專案項目-', '辦公設備'),
    ('專案項目-', '健康家電'),
    ('專案項目-', '工具設備'),
    # 防呆：確保某些 mapping 目標存在
    ('車',   '其他'),
    ('保險', '其他'),
    ('保險', '健保費'),
    ('特殊', '生產'),
]


def main():
    apply_changes = '--apply' in sys.argv
    out = sys.stdout.buffer

    con = sqlite3.connect(DB)
    cur = con.cursor()

    # ── 0. 確保所有需要的類別/子項目存在 ─────────────────
    cur.execute('SELECT name, cno, order_id FROM class')
    class_map = {n: (c, o) for n, c, o in cur.fetchall()}

    cur.execute('SELECT MAX(cno), MAX(order_id) FROM class')
    max_cno, max_order = cur.fetchone()

    to_create_classes = []
    for nm, oid in NEW_CLASSES:
        if nm not in class_map:
            max_cno += 1
            max_order += 1
            to_create_classes.append((max_cno, nm, max_order))
            class_map[nm] = (max_cno, max_order)

    cur.execute('''SELECT c.name, s.name, s.sno, s.order_id
                   FROM subject s JOIN class c ON s.cno=c.cno''')
    sub_map = {(cn, sn): sno for cn, sn, sno, _ in cur.fetchall()}

    cur.execute('SELECT MAX(sno), MAX(order_id) FROM subject')
    max_sno, max_sorder = cur.fetchone()

    to_create_subs = []
    for cls_name, sub_name in NEW_SUBJECTS:
        if (cls_name, sub_name) not in sub_map:
            if cls_name not in class_map:
                out.write(f'  ! 找不到類別 {cls_name}\n'.encode())
                continue
            max_sno += 1
            max_sorder += 1
            cno = class_map[cls_name][0]
            to_create_subs.append((max_sno, cno, sub_name, max_sorder))
            sub_map[(cls_name, sub_name)] = max_sno

    out.write(f'[init] 待建類別: {len(to_create_classes)}\n'.encode())
    for cno, nm, oid in to_create_classes:
        out.write(f'  + cno={cno}  {nm}\n'.encode())
    out.write(f'[init] 待建子項目: {len(to_create_subs)}\n'.encode())
    for sno, cno, nm, oid in to_create_subs:
        out.write(f'  + sno={sno} cno={cno}  {nm}\n'.encode())

    # ── 1. 階段 1：14 筆未分類 + 修車 ─────────────────
    out.write('\n[stage 1] 14 筆未分類 + 修車（按 mno）:\n'.encode())
    stage1_updates = []
    for mno, new_cls, new_sub in STAGE1_FIXES:
        cno = class_map.get(new_cls, (None,))[0]
        sno = sub_map.get((new_cls, new_sub))
        if cno is None or sno is None:
            out.write(f'  ! mno={mno} 找不到 [{new_cls}/{new_sub}]\n'.encode())
            continue
        stage1_updates.append((mno, cno, sno, new_cls, new_sub))
    out.write(f'  共 {len(stage1_updates)} 筆要 UPDATE\n'.encode())

    # ── 2. 階段 2+3：按 (舊類別, 舊子項目) 批次 UPDATE ─────
    out.write('\n[stage 2+3] 按對應規則批次更新:\n'.encode())
    stage23_updates = []  # (old_cno, old_sno, new_cno, new_sno, label)
    for (old_cls, old_sub), (new_cls, new_sub) in MAPPING.items():
        # 找舊對應
        old_cno = class_map.get(old_cls, (None,))[0]
        old_sno = sub_map.get((old_cls, old_sub))
        if old_cno is None or old_sno is None:
            continue  # 不存在的對應，跳過
        new_cno = class_map.get(new_cls, (None,))[0]
        new_sno = sub_map.get((new_cls, new_sub))
        if new_cno is None or new_sno is None:
            out.write(f'  ! 缺新對應 [{new_cls}/{new_sub}]\n'.encode())
            continue
        # 算受影響筆數
        cur.execute('SELECT COUNT(*) FROM money WHERE cno=? AND sno=?', (old_cno, old_sno))
        n = cur.fetchone()[0]
        stage23_updates.append((old_cno, old_sno, new_cno, new_sno, n, f'{old_cls}/{old_sub} → {new_cls}/{new_sub}'))

    stage23_updates.sort(key=lambda x: -x[4])
    total23 = sum(u[4] for u in stage23_updates)
    for old_cno, old_sno, new_cno, new_sno, n, label in stage23_updates:
        out.write(f'  [{n:>4}] {label}\n'.encode())
    out.write(f'  共 {total23} 筆要 UPDATE\n'.encode())

    # ── 3. 娛樂/禮物 343 筆按 note 關鍵字分流 ─────────────
    out.write('\n[stage 3 特殊] 娛樂/禮物 按關鍵字分流:\n'.encode())
    cur.execute('''SELECT m.mno, COALESCE(m.note,'') FROM money m
                   JOIN class c ON m.cno=c.cno JOIN subject s ON m.sno=s.sno
                   WHERE c.name='娛樂' AND s.name='禮物' ''')
    gift_rows = cur.fetchall()

    def is_hongbao(note):
        return any(k in note for k in ['紅包', '禮金', '母親節', '父親節', '節禮'])

    hongbao_mnos = [mno for mno, n in gift_rows if is_hongbao(n)]
    other_mnos   = [mno for mno, n in gift_rows if not is_hongbao(n)]
    out.write(f'  9 筆紅包字眼 → 特殊/禮金: {len(hongbao_mnos)}\n'.encode())
    out.write(f'  其他 → 特殊/禮物: {len(other_mnos)}\n'.encode())

    # ── 4. 特殊/3C家電 6 筆按 note 分流 ───────────────────
    out.write('\n[stage 3 特殊] 特殊/3C家電 按 note 分流:\n'.encode())
    cur.execute('''SELECT m.mno, COALESCE(m.note,'') FROM money m
                   JOIN class c ON m.cno=c.cno JOIN subject s ON m.sno=s.sno
                   WHERE c.name='特殊' AND s.name='3C家電' ''')
    c3_rows = cur.fetchall()
    c3_fixes = []  # (mno, new_class, new_subject)
    for mno, note in c3_rows:
        for kw, ncls, nsub in STAGE3_3C_FIXES:
            if kw in note:
                c3_fixes.append((mno, ncls, nsub))
                out.write(f'  mno={mno}  {note[:30]:30s} → {ncls}/{nsub}\n'.encode())
                break

    # ── 5. 特殊/勞健保費 2 筆按 note 分流 ──────────────────
    out.write('\n[stage 3 特殊] 特殊/勞健保費 按 note 分流:\n'.encode())
    cur.execute('''SELECT m.mno, COALESCE(m.note,'') FROM money m
                   JOIN class c ON m.cno=c.cno JOIN subject s ON m.sno=s.sno
                   WHERE c.name='特殊' AND s.name='勞健保費' ''')
    laoba_rows = cur.fetchall()
    laoba_fixes = []
    for mno, note in laoba_rows:
        # 含「勞」→ 勞保費，否則 → 健保費（涵蓋「建保費」typo）
        target = ('保險', '勞保費') if '勞' in note else ('保險', '健保費')
        laoba_fixes.append((mno, *target))
        out.write(f'  mno={mno}  {note[:30]:30s} → {target[0]}/{target[1]}\n'.encode())

    if not apply_changes:
        out.write('\n*** DRY RUN：加 --apply 才會實際寫入 ***\n'.encode())
        return

    # ── 套用 ────────────────────────────────────────────
    out.write('\n=== 套用 ===\n'.encode())

    # 0. 建立 class/subject
    for cno, nm, oid in to_create_classes:
        cur.execute('INSERT INTO class (cno, uno, name, order_id) VALUES (?, 1, ?, ?)',
                    (cno, nm, oid))
    for sno, cno, nm, oid in to_create_subs:
        cur.execute('INSERT INTO subject (sno, cno, uno, name, order_id) VALUES (?, ?, 1, ?, ?)',
                    (sno, cno, nm, oid))
    out.write(f'  建立 {len(to_create_classes)} 類別 / {len(to_create_subs)} 子項目\n'.encode())

    # 1. 階段 1
    n1 = 0
    for mno, cno, sno, _, _ in stage1_updates:
        cur.execute('UPDATE money SET cno=?, sno=? WHERE mno=?', (cno, sno, mno))
        n1 += cur.rowcount
    out.write(f'  階段 1: {n1} 筆\n'.encode())

    # 2. 階段 2+3 批次
    n23 = 0
    for old_cno, old_sno, new_cno, new_sno, _, _ in stage23_updates:
        cur.execute('UPDATE money SET cno=?, sno=? WHERE cno=? AND sno=?',
                    (new_cno, new_sno, old_cno, old_sno))
        n23 += cur.rowcount
    out.write(f'  階段 2+3 批次: {n23} 筆\n'.encode())

    # 3. 娛樂/禮物 分流
    hongbao_target = sub_map.get(('特殊', '禮金'))
    other_target   = sub_map.get(('特殊', '禮物'))
    special_cno    = class_map['特殊'][0]
    if hongbao_target and other_target:
        for mno in hongbao_mnos:
            cur.execute('UPDATE money SET cno=?, sno=? WHERE mno=?',
                        (special_cno, hongbao_target, mno))
        for mno in other_mnos:
            cur.execute('UPDATE money SET cno=?, sno=? WHERE mno=?',
                        (special_cno, other_target, mno))
        out.write(f'  娛樂/禮物 → 特殊/禮金 {len(hongbao_mnos)} + 特殊/禮物 {len(other_mnos)}\n'.encode())

    # 4. 3C家電
    for mno, ncls, nsub in c3_fixes:
        cno = class_map[ncls][0]
        sno = sub_map[(ncls, nsub)]
        cur.execute('UPDATE money SET cno=?, sno=? WHERE mno=?', (cno, sno, mno))
    out.write(f'  3C家電: {len(c3_fixes)} 筆\n'.encode())

    # 5. 勞健保費
    for mno, ncls, nsub in laoba_fixes:
        cno = class_map[ncls][0]
        sno = sub_map[(ncls, nsub)]
        cur.execute('UPDATE money SET cno=?, sno=? WHERE mno=?', (cno, sno, mno))
    out.write(f'  勞健保費: {len(laoba_fixes)} 筆\n'.encode())

    # 6. 清孤兒
    cur.execute('''DELETE FROM subject WHERE sno NOT IN
                   (SELECT DISTINCT sno FROM money WHERE sno > 0)
                   AND (cno, name) NOT IN (
                     SELECT c.cno, ? FROM class c WHERE 1=0
                   )''', ('',))
    # 重做：保留 JSON 定義的空子項目，刪除真孤兒
    cur.execute('''DELETE FROM subject WHERE sno NOT IN
                   (SELECT DISTINCT sno FROM money WHERE sno > 0)''')
    out.write(f'  清孤兒子項目: {cur.rowcount}\n'.encode())
    cur.execute('''DELETE FROM class WHERE cno NOT IN
                   (SELECT DISTINCT cno FROM money)''')
    out.write(f'  清孤兒類別: {cur.rowcount}\n'.encode())

    con.commit()

    # ── 驗證 ────────────────────────────────────────
    cur.execute("SELECT COUNT(*) FROM money WHERE sno IS NULL OR sno=0")
    out.write(f'\n=== 驗證 ===\n  未分類筆數: {cur.fetchone()[0]}\n'.encode())

    cur.execute('SELECT COUNT(*) FROM class')
    n_class = cur.fetchone()[0]
    cur.execute('SELECT COUNT(*) FROM subject')
    n_sub = cur.fetchone()[0]
    cur.execute('SELECT COUNT(*) FROM money')
    n_money = cur.fetchone()[0]
    out.write(f'  類別: {n_class} / 子項目: {n_sub} / money: {n_money}\n'.encode())

    cur.execute('SELECT name FROM class ORDER BY order_id')
    out.write(f'  類別: {[r[0] for r in cur.fetchall()]}\n'.encode())

    con.close()


if __name__ == '__main__':
    main()
