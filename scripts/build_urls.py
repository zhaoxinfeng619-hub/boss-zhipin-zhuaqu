#!/usr/bin/env python3
"""生成扩池用的检索 URL 清单（多关键词 × 筛选组合）。

用法:
  build_urls.py --city 101010100 --kw "AI产品经理,AI产品,大模型产品经理" --out /tmp/urls.txt
  build_urls.py --city 101020100 --kw "数据分析师" --kw "数据产品经理" --out /tmp/urls.txt

说明:
- 第 1 个关键词跑「全量组合」（基线 + 经验/薪资/学历/规模/融资），其余关键词跑「精选组合」，
  避免重复劳动。单关键词池子会封顶（约 325 条唯一职位），要更多必须换关键词。
- 城市码：北京 101010100 / 上海 101020100 / 深圳 101280600 / 广州 101280100 / 杭州 101210100
"""
import argparse
import urllib.parse

CITY_DEFAULT = '101010100'
BASE = 'https://www.zhipin.com/web/geek/jobs'

# 实测编码（2026-09）
EXP   = [101, 102, 103, 104, 105, 106, 107, 108]
SAL   = [402, 403, 404, 405, 406, 407]
DEG   = [202, 203, 204, 205, 206, 208, 209]
SCALE = [301, 302, 303, 304, 305, 306]
STAGE = [801, 802, 803, 804, 805, 806, 807, 808]

# 其余关键词的精选组合
PICK_EXP   = [104, 105, 106]
PICK_SAL   = [405, 406, 407]
PICK_DEG   = [203, 204]
PICK_SCALE = [304, 305, 306]
PICK_STAGE = [803, 804, 806, 807]


def build(keywords, city):
    urls = []

    def add(kw, extra=''):
        u = f'{BASE}?query={urllib.parse.quote(kw)}&city={city}'
        if extra:
            u += '&' + extra
        urls.append(u)

    for idx, kw in enumerate(keywords):
        add(kw)
        exp = EXP if idx == 0 else PICK_EXP
        sal = SAL if idx == 0 else PICK_SAL
        deg = DEG if idx == 0 else PICK_DEG
        sca = SCALE if idx == 0 else PICK_SCALE
        sta = STAGE if idx == 0 else PICK_STAGE
        for v in exp:   add(kw, f'experience={v}')
        for v in sal:   add(kw, f'salary={v}')
        for v in deg:   add(kw, f'degree={v}')
        for v in sca:   add(kw, f'scale={v}')
        for v in sta:   add(kw, f'stage={v}')

    out, seen = [], set()
    for u in urls:
        if u in seen:
            continue
        seen.add(u)
        out.append(u)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--city', default=CITY_DEFAULT)
    ap.add_argument('--kw', action='append', required=True,
                    help='关键词，可重复传；第 1 个跑全量组合')
    ap.add_argument('--out', default='/tmp/urls.txt')
    a = ap.parse_args()

    kws = []
    for k in a.kw:
        kws += [x.strip() for x in k.split(',') if x.strip()]

    urls = build(kws, a.city)
    with open(a.out, 'w', encoding='utf-8') as f:
        f.write('\n'.join(urls) + '\n')
    print(f'关键词 {len(kws)} 个 → URL {len(urls)} 个 → {a.out}')
    print(f'预估列表采集耗时：约 {len(urls) * 8.5 / 60:.0f} 分钟')


if __name__ == '__main__':
    main()
