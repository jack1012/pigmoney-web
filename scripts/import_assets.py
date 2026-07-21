import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parents[1] / '.data' / 'money_merged.sqlite'

YEARS = [2019, 2020, 2021, 2022, 2023, 2024, 2025]

# 從 家庭收支儀表板.html 摘取
CASH = {
    '政德-郵局':         [535856, 599405, 541763, 270707, 445436, 711516, 869359],
    '政德-玉山':         [500325, 486426, 427373, 357338, 605837, 1035765, 1586971],
    '政德-中信台幣':     [60862,  59683,  41653,  37942,  45572,  32317,   43047],
    '政德-中信美金':     [46746,  60807,  75755,  105692, 120728, 149807,  69048],
    '政德-王道銀行':     [107830, 41981,  12987,  7607,   5628,   5671,    5719],
    '怡亭-郵局':         [173217, 419274, 256824, 18716,  257786, 257128, 382132],
    '怡亭-中信':         [2203136,467634, 268159, 1166610,1205523,1538691,2855985],
    '怡亭-日盛/富邦':    [104153, 0,      0,      103647, 24736,  58895,  141732],
    '小Q-郵局':          [0, 0, 0, 1000, 1000, 1000, 1000],
    '小K-郵局':          [0, 0, 0, 1000, 1000, 1000, 1000],
    '小A-郵局':          [0, 0, 0, 0,    0,    0,    1000],
    '小Q-玉山':          [0, 0, 1000, 124960, 542796, 225002, 300640],
    '小K-玉山':          [0, 0, 1000, 124960, 703114, 423633, 480525],
    '小A-玉山':          [0, 0, 0,    0,      0,      0,      1000],
}

INVEST = {
    '政德-中信基金':     [323306,  323306,  323306,  323306,  323306,  323306,  323306],
    '政德-玉山股票':     [2653874, 4821629, 7263901, 7781148, 8927077, 9064124, 9624348],
    '怡亭-美金保單':     [1000000, 1000000, 1000000, 1000000, 1000000, 1000000, 1000000],
    '怡亭-凱基股票':     [0,       0,       0,       137820,  346227,  1580378, 1830743],
    '小Q-股票':          [0, 0, 0, 1037476, 1237476, 2189877, 2189877],
    '小K-股票':          [0, 0, 0, 1037476, 1077476, 1614318, 1614318],
    '小A-股票':          [0, 0, 0, 0,       0,       0,       0],
}

# 動產/不動產：存當年折舊後淨值
# 汽車淨值 = 1,680,000 × 0.8^(year-2020+1)，2019 無車
def car_net(year):
    if year < 2020: return 0
    return int(1680000 * (0.8 ** (year - 2020)))  # 2020 = 1,680,000，之後每年乘 0.8

REAL_ESTATE = {
    '房屋':  [8100000] * len(YEARS),           # 購入/市值常數
    '汽車':  [car_net(y) for y in YEARS],      # 折舊後淨值
}

REAL_ESTATE_NOTES = {
    '房屋': '購入 8,100,000（2008年）',
    '汽車': '購入 1,680,000（2020年）；折舊率 20%/年',
}

# 房貸：當年餘額（正數）；2025 = 1,340,000，每年還本 340,000
# 汽車折舊：當年折舊金額（正數）= 當年淨值 × 20%
DEBT = {
    '房貸':    [1090000 + (2025 - y) * 340000 for y in YEARS],
    '汽車折舊': [int(car_net(y) * 0.2) for y in YEARS],
}

DEBT_NOTES = {
    '汽車折舊': '當年折舊 = 當年淨值 x 20%',
}

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

# 建表（以防 db.js 還沒被執行過）
cur.execute('''
    CREATE TABLE IF NOT EXISTS asset_account (
      ano       INTEGER PRIMARY KEY AUTOINCREMENT,
      category  TEXT NOT NULL,
      name      TEXT NOT NULL,
      note      TEXT,
      order_id  INTEGER DEFAULT 0
    )
''')
cur.execute('''
    CREATE TABLE IF NOT EXISTS asset_snapshot (
      date    TEXT NOT NULL,
      ano     INTEGER NOT NULL,
      amount  INTEGER NOT NULL,
      PRIMARY KEY (date, ano)
    )
''')

def create_accounts(category, data, notes=None):
    order = 0
    for name in data.keys():
        order += 1
        note = (notes or {}).get(name)
        existing = cur.execute(
            'SELECT ano FROM asset_account WHERE category=? AND name=?',
            (category, name)
        ).fetchone()
        if not existing:
            cur.execute(
                'INSERT INTO asset_account (category, name, note, order_id) VALUES (?, ?, ?, ?)',
                (category, name, note, order)
            )
        elif note:
            cur.execute(
                'UPDATE asset_account SET note=? WHERE category=? AND name=?',
                (note, category, name)
            )

create_accounts('現金',          CASH)
create_accounts('投資',          INVEST)
create_accounts('動產/不動產',   REAL_ESTATE, REAL_ESTATE_NOTES)
create_accounts('負債',          DEBT, DEBT_NOTES)

ano_map = {}
for r in cur.execute('SELECT ano, category, name FROM asset_account'):
    ano_map[(r[1], r[2])] = r[0]

def insert_snapshots(category, data):
    for name, values in data.items():
        ano = ano_map[(category, name)]
        for i, y in enumerate(YEARS):
            date = f'{y}-12-31'
            cur.execute(
                'INSERT OR REPLACE INTO asset_snapshot (date, ano, amount) VALUES (?, ?, ?)',
                (date, ano, values[i])
            )

insert_snapshots('現金',          CASH)
insert_snapshots('投資',          INVEST)
insert_snapshots('動產/不動產',   REAL_ESTATE)
insert_snapshots('負債',          DEBT)

conn.commit()

# 驗證
print('=== asset_account ===')
for row in cur.execute('SELECT category, name, note FROM asset_account ORDER BY category, order_id'):
    print(f'  [{row[0]}] {row[1]}' + (f'  ({row[2]})' if row[2] else ''))

print()
print('=== 各年度合計（淨資產）===')
for row in cur.execute('''
    SELECT date, COUNT(*), SUM(amount)/10000.0
    FROM asset_snapshot GROUP BY date ORDER BY date
'''):
    print(f'  {row[0]}: {row[1]} 筆, 淨 {row[2]:.1f}W')
