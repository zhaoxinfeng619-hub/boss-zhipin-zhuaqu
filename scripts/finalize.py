#!/usr/bin/env python3
"""最终合成：已有 CSV + 第3/4 批详情 → 剔除猎头/外包/实习 → 取 100 条导出。"""
import csv, json, os, re

BASE = os.environ.get('BOSS_WORKDIR', os.getcwd())
OUT  = os.path.join(BASE, 'boss_AI产品经理_北京.csv')

FIELDS = ['#','职位名称','薪资','公司','行业','融资阶段','公司规模',
          '城市·区域','经验要求','学历要求','技能标签','招聘者','发布时间','岗位JD','岗位链接']
EDU_SET = ('初中及以下','中专/中技','高中','大专','本科','硕士','博士','学历不限')

TARGET = 100

HH_ATTR   = re.compile(r'猎头')
HH_COMPANY= re.compile(r'(人力资源|人力|人才|劳务|锐仕方达|佰钧成|外派|外包)')
HH_TITLE  = re.compile(r'(外派|外包|猎头)')
INTERN    = re.compile(r'实习')

def jload(path):
    if not os.path.exists(path): return None
    s = open(path, encoding='utf-8').read().strip()
    if not s: return None
    try: v = json.loads(s)
    except Exception: return None
    if isinstance(v, str):
        try: v = json.loads(v)
        except Exception: return None
    return v

def jid(u): return (u or '').rsplit('/', 1)[-1].replace('.html', '')

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
            if t in EDU_SET: edu = t; break
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

def is_hh(row):
    if HH_ATTR.search(row.get('招聘者','') or ''): return True
    if HH_COMPANY.search(row.get('公司','') or ''): return True
    if HH_TITLE.search(row.get('职位名称','') or ''): return True
    return False

def clean_jd_tail(row):
    """剔除 JD 末尾混入的招聘者卡片行（姓名/活跃状态/公司/·/职位）。"""
    jd = row.get('岗位JD','') or ''
    if not jd: return jd
    recruiter = row.get('招聘者','') or ''
    parts = [p for p in re.split(r'[·]', recruiter) if p.strip()]
    ban = set()
    for v in parts + [row.get('公司',''), row.get('发布时间',''), '·', '-', '|']:
        v = (v or '').strip()
        if v: ban.add(v)
    lines = jd.split('\n')
    n = len(lines)
    while n > 1:
        t = lines[n-1].strip()
        if t == '' or t in ban: n -= 1; continue
        break
    return '\n'.join(lines[:n]).strip()

# ---------- 1) 已有 CSV（第 1、2 批）----------
base = []
if os.path.exists(OUT):
    for r in csv.DictReader(open(OUT, encoding='utf-8-sig')):
        base.append({k: r.get(k,'') for k in FIELDS if k != '#'})

# ---------- 2) 新批次详情 ----------
def load_batch(listpath, detdir):
    lst = jload(listpath) or []
    by_id = {jid(x.get('href','')): x for x in lst}
    out, i = [], 0
    while True:
        i += 1
        if i > 300: break
        p = os.path.join(detdir, f'{i}.json')
        if not os.path.exists(p): continue
        det = jload(p)
        if not det: continue
        k = jid(det.get('url',''))
        out.append(build(det, by_id.get(k)))
    return out

b3 = load_batch('/tmp/list_b3.json', '/tmp/db3')
b4 = load_batch('/tmp/list_b4.json', '/tmp/db4')

pool, seen_ids, dup = [], set(), 0
for row in base + b3 + b4:
    k = jid(row.get('岗位链接',''))
    if not row.get('职位名称'): continue
    if k in seen_ids: dup += 1; continue
    seen_ids.add(k)
    pool.append(row)

print(f'候选池：{len(pool)} 条（去重 {dup}）')

kept, dropped = [], {'猎头/外包':0,'实习':0,'JD过短':0}
for row in pool:
    if INTERN.search(row['职位名称']): dropped['实习'] += 1; continue
    if is_hh(row):                     dropped['猎头/外包'] += 1; continue
    if len(row['岗位JD']) < 80:        dropped['JD过短'] += 1; continue
    kept.append(row)
print('剔除统计:', dropped, '| 保留:', len(kept))

final = kept[:TARGET]
for i, r in enumerate(final, 1):
    r['#'] = i
    r['岗位JD'] = clean_jd_tail(r)

with open(OUT, 'w', newline='', encoding='utf-8-sig') as f:
    w = csv.DictWriter(f, fieldnames=FIELDS)
    w.writeheader()
    for r in final: w.writerow(r)

print(f'最终导出 {len(final)} 条 -> {OUT}')
print('备用剩余:', max(0, len(kept) - TARGET))
