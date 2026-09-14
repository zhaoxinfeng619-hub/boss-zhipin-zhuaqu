#!/usr/bin/env python3
"""增量合并导出：已有 CSV + 新一批（列表 JSON + 详情目录）→ 去重 → 重编号写回。

用法：python3 export_batch.py --list /tmp/list_b3.json --det /tmp/db3
"""
import argparse, csv, json, os

BASE = os.environ.get('BOSS_WORKDIR', os.getcwd())
OUT  = os.path.join(BASE, 'boss_AI产品经理_北京.csv')

FIELDS = ['#','职位名称','薪资','公司','行业','融资阶段','公司规模',
          '城市·区域','经验要求','学历要求','技能标签','招聘者','发布时间','岗位JD','岗位链接']

EDU_SET = ('初中及以下','中专/中技','高中','大专','本科','硕士','博士','学历不限')

def jload(path):
    """兼容浏览器 eval 的双重编码与普通 JSON。"""
    if not os.path.exists(path): return None
    s = open(path, encoding='utf-8').read().strip()
    if not s: return None
    try: v = json.loads(s)
    except Exception: return None
    if isinstance(v, str):
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

ap = argparse.ArgumentParser()
ap.add_argument('--list', required=True)
ap.add_argument('--det',  required=True)
a = ap.parse_args()

# 1) 已有 CSV
existing, base_rows = {}, []
if os.path.exists(OUT):
    for r in csv.DictReader(open(OUT, encoding='utf-8-sig')):
        k = jid(r.get('岗位链接',''))
        existing[k] = r
        base_rows.append(k)
print('已有 CSV:', len(base_rows))

# 2) 新批次详情
new_list = jload(a.list) or []
item_by_id = {jid(x.get('href','')): x for x in new_list}

new_ids, dets = set(), []
i = 0
while True:
    i += 1
    p = os.path.join(a.det, f'{i}.json')
    if not os.path.exists(p):
        if i > 200: break
        continue
    det = jload(p)
    if not det:
        print(f'  [跳过] {i}：解析失败'); continue
    k = jid(det.get('url',''))
    if k: new_ids.add(k)
    dets.append((i, k, det))
    if i >= 200: break

base_rows = [k for k in base_rows if k not in new_ids]

added = []
for i, k, det in dets:
    row = build(det, item_by_id.get(k))
    if not row['职位名称']:
        print(f'  [跳过] {i}：无职位名'); continue
    if k in existing and k in new_ids and k in existing:
        pass
    existing[k] = row
    added.append(row)
print('新写入:', len(added))

allkeys = base_rows + [jid(r['岗位链接']) for r in added]
rows = []
for idx, k in enumerate(allkeys, 1):
    r = dict(existing[k]); r['#'] = idx; rows.append(r)

with open(OUT, 'w', newline='', encoding='utf-8-sig') as f:
    w = csv.DictWriter(f, fieldnames=FIELDS)
    w.writeheader()
    for r in rows: w.writerow(r)

print('总条数:', len(rows), '->', OUT)
short = [(r['#'], len(r['岗位JD']), r['职位名称'][:24]) for r in rows if len(r['岗位JD']) < 60]
print('JD 异常短(<60字):', short or '无')
