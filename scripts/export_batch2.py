#!/usr/bin/env python3
# 增量导出：已有 CSV + 新批次（列表 + 详情）合并去重后写回
import csv, json, os

BASE = os.environ.get('BOSS_WORKDIR', os.getcwd())
OUT  = os.path.join(BASE, 'boss_AI产品经理_北京.csv')
NEW_LIST = '/tmp/list_b2.json'
DET_DIR  = '/tmp/db2'

FIELDS = ['#','职位名称','薪资','公司','行业','融资阶段','公司规模',
          '城市·区域','经验要求','学历要求','技能标签','招聘者','发布时间','岗位JD','岗位链接']

EDU_SET = ('初中及以下','中专/中技','高中','大专','本科','硕士','博士','学历不限')

def jload(path):
    if not os.path.exists(path): return None
    s = open(path, encoding='utf-8').read().strip()
    if not s: return None
    try:
        v = json.loads(s)
    except Exception:
        return None
    if isinstance(v, str):          # 浏览器 eval 的输出是双重编码
        try: v = json.loads(v)
        except Exception: return None
    return v

def jid(u):
    return (u or '').rsplit('/', 1)[-1].replace('.html', '')

def build(det, item):
    tags = (item or {}).get('tags') or []
    exp = det.get('exp') or ''
    edu = det.get('edu') or ''
    if not exp:
        for t in tags:
            if t in ('应届生','经验不限') or ('年' in t and ('-' in t or '以内' in t or '以上' in t)):
                exp = t; break
    if not edu:
        for t in tags:
            if t in EDU_SET:
                edu = t; break
    recruiter = det.get('recruiter','') or ''
    attr = det.get('recruiterAttr','') or ''
    recruiter_full = f"{recruiter}·{attr.split('·')[-1]}" if (recruiter and attr and '·' in attr) else recruiter
    return {
        '职位名称': det.get('name') or (item or {}).get('name',''),
        '薪资':     det.get('salary') or (item or {}).get('salary',''),
        '公司':     det.get('companyName') or (item or {}).get('company',''),
        '行业':     det.get('industry','') or '',
        '融资阶段': det.get('financing','') or '',
        '公司规模': det.get('scale','') or '',
        '城市·区域': (item or {}).get('area','') or det.get('city','') or '',
        '经验要求': exp,
        '学历要求': edu,
        '技能标签': '；'.join(det.get('skills') or []),
        '招聘者':   recruiter_full,
        '发布时间': det.get('recruiterActive','') or '',
        '岗位JD':   (det.get('jd') or '').strip(),
        '岗位链接': det.get('url') or ('https://www.zhipin.com' + (item or {}).get('href','')),
    }

# 1) 已有 CSV
existing = {}
base_rows = []
if os.path.exists(OUT):
    for r in csv.DictReader(open(OUT, encoding='utf-8-sig')):
        k = jid(r.get('岗位链接',''))
        existing[k] = r
        base_rows.append(k)
print('已有 CSV 条数:', len(base_rows))

# 2) 新批次
new_list = jload(NEW_LIST) or []
item_by_id = {jid(x.get('href','')): x for x in new_list}
# 新批次会被重建，先从基础顺序里剔除，避免重复
new_ids = set()
for i in range(1, 200):
    det = jload(os.path.join(DET_DIR, f'{i}.json'))
    if det is None: break
    k = jid(det.get('url',''))
    if k: new_ids.add(k)
base_rows = [k for k in base_rows if k not in new_ids]

added = []
for i in range(1, 200):
    det = jload(os.path.join(DET_DIR, f'{i}.json'))
    if det is None: break
    k = jid(det.get('url',''))
    if not k:
        print(f'  [跳过] 第{i}条：无链接')
        continue
    row = build(det, item_by_id.get(k))
    if not row['职位名称']:
        print(f'  [跳过] 第{i}条：无职位名')
        continue
    if k in existing:
        print(f'  [覆盖] 第{i}条：{row["职位名称"][:20]}')
    existing[k] = row
    added.append(row)
print('新写入:', len(added))

# 3) 输出（原有顺序 + 新条目）
allkeys = base_rows + [jid(r['岗位链接']) for r in added]
rows = []
for idx, k in enumerate(allkeys, 1):
    r = dict(existing[k]); r['#'] = idx; rows.append(r)

with open(OUT, 'w', newline='', encoding='utf-8-sig') as f:
    w = csv.DictWriter(f, fieldnames=FIELDS)
    w.writeheader()
    for r in rows: w.writerow(r)

print('总条数:', len(rows), '->', OUT)
for r in added:
    print('  +', r['职位名称'][:24], '|', r['薪资'], '|', r['公司'][:16], '| JD', len(r['岗位JD']))
