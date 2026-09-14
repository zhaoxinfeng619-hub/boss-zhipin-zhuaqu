#!/usr/bin/env python3
"""增量合成：已有 CSV + 新一批详情 → 剔除猎头/外包/实习 → 补到目标条数导出。

用法:
  finalize_batch.py --csv <输出CSV> --list /tmp/list_b5.json --det /tmp/db5 --target 200

说明:
  --csv 既是「已有数据的来源」也是「输出目标」，所以重复跑会自动累加、不会丢历史数据。
  --list / --det 是 filter_candidates.py 与 scrape_batch.sh 的产物。
"""
import argparse, csv, json, os, re, sys

_ap = argparse.ArgumentParser()
_ap.add_argument('--csv', required=True, help='输出（同时作为已有数据来源）的 CSV 路径')
_ap.add_argument('--list', dest='listpath', required=True, help='filter_candidates.py 产出的 list_*.json')
_ap.add_argument('--det', required=True, help='scrape_batch.sh 产出的详情目录')
_ap.add_argument('--target', type=int, default=200, help='最终目标条数')
_a = _ap.parse_args()

OUT = _a.csv
TARGET = _a.target

FIELDS = ['#','职位名称','薪资','公司','行业','融资阶段','公司规模',
          '城市·区域','经验要求','学历要求','技能标签','招聘者','发布时间','岗位JD','岗位链接']
EDU_SET = ('初中及以下','中专/中技','高中','大专','本科','硕士','博士','学历不限')

HH_ATTR    = re.compile(r'猎头')
HH_COMPANY = re.compile(r'(人力资源|人力|人才|劳务|锐仕方达|佰钧成|外派|外包)')
HH_TITLE   = re.compile(r'(外派|外包|猎头)')
INTERN     = re.compile(r'实习')

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

# ---------- 1) 已有 CSV ----------
base = []
if os.path.exists(OUT):
    for r in csv.DictReader(open(OUT, encoding='utf-8-sig')):
        base.append({k: r.get(k,'') for k in FIELDS if k != '#'})
print(f'已有 CSV: {len(base)} 条')

# ---------- 2) 新批次详情 ----------
def load_batch(listpath, detdir):
    lst = jload(listpath) or []
    by_id = {jid(x.get('href','')): x for x in lst}
    out, missing = [], 0
    for i in range(1, 600):
        p = os.path.join(detdir, f'{i}.json')
        if not os.path.exists(p):
            continue
        det = jload(p)
        if not det:
            missing += 1; continue
        k = jid(det.get('url',''))
        out.append(build(det, by_id.get(k)))
    return out

new = load_batch(_a.listpath, _a.det)
print(f'本批详情: {len(new)} 条')

pool, seen_ids, dup = [], set(), 0
for row in base + new:
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
