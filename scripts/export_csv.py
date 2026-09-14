#!/usr/bin/env python3
# 合并列表页 + 详情页数据，按 boss表头.csv 的 14 个字段导出
import csv, json, os, sys

BASE = os.environ.get('BOSS_WORKDIR', os.getcwd())
LIST = os.path.join(BASE, 'list_page1.json')
OUT  = os.path.join(BASE, 'boss_AI产品经理_北京.csv')

def load_json_line(path):
    if not os.path.exists(path):
        return None
    s = open(path, encoding='utf-8').read().strip()
    if not s:
        return None
    try:
        return json.loads(json.loads(s))
    except Exception:
        return None

list_items = load_json_line(LIST) or []

FIELDS = ['#','职位名称','薪资','公司','行业','融资阶段','公司规模',
          '城市·区域','经验要求','学历要求','技能标签','招聘者','发布时间','岗位JD','岗位链接']

rows = []
for i, item in enumerate(list_items, 1):
    det = load_json_line(f'/tmp/detail_{i}.json')
    if det is None:
        continue   # 只导出已采集详情页的条目

    name    = det.get('name') or item.get('name','')
    salary  = det.get('salary') or item.get('salary','')
    company = det.get('companyName') or item.get('company','')
    industry= det.get('industry','') or ''
    financing = det.get('financing','') or ''
    scale   = det.get('scale','') or ''
    area    = item.get('area','') or det.get('city') or ''

    tags = item.get('tags') or []
    exp = det.get('exp') or ''
    edu = det.get('edu') or ''
    if not exp:
        for t in tags:
            if t in ('应届生','经验不限') or ('年' in t and ('-' in t or '以内' in t or '以上' in t)):
                exp = t
                break
    if not edu:
        for t in tags:
            if t in ('初中及以下','中专/中技','高中','大专','本科','硕士','博士','学历不限'):
                edu = t
                break

    skills = det.get('skills') or []
    recruiter = det.get('recruiter','') or ''
    attr = det.get('recruiterAttr','') or ''
    if recruiter and attr and '·' in attr:
        recruiter_full = f"{recruiter}·{attr.split('·')[-1]}"
    else:
        recruiter_full = recruiter

    jd = (det.get('jd') or '').strip()
    url = det.get('url') or ('https://www.zhipin.com' + item.get('href',''))

    rows.append({
        '#': i,
        '职位名称': name,
        '薪资': salary,
        '公司': company,
        '行业': industry,
        '融资阶段': financing,
        '公司规模': scale,
        '城市·区域': area,
        '经验要求': exp,
        '学历要求': edu,
        '技能标签': '；'.join(skills),
        '招聘者': recruiter_full,
        '发布时间': det.get('recruiterActive','') or '',
        '岗位JD': jd,
        '岗位链接': url,
    })

with open(OUT, 'w', newline='', encoding='utf-8-sig') as f:
    w = csv.DictWriter(f, fieldnames=FIELDS)
    w.writeheader()
    for r in rows:
        w.writerow(r)

print('导出', len(rows), '条 ->', OUT)
for r in rows[:3]:
    print('-', r['职位名称'], '|', r['薪资'], '|', r['公司'], '|', r['行业'], '|', r['融资阶段'], '|', r['公司规模'], '|', r['招聘者'], '| JD长度', len(r['岗位JD']))
