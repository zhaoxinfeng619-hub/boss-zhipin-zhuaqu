#!/usr/bin/env python3
"""从 harvest 输出里筛出「新的 + 相关的」候选职位。

用法:
  filter_candidates.py /tmp/harvest_b5.txt
  filter_candidates.py /tmp/harvest_b5.txt --seen /tmp/seen_ids.txt --out-prefix b5

产物:
  /tmp/cand_<prefix>.txt    候选职位 URL 清单（喂给 scrape_batch.sh）
  /tmp/list_<prefix>.json   候选列表数据（含 name/salary/company/area/href）

思路:
  1) 把所有 harvest 行解析、合并、按 job id 去重
  2) 剔除「已在已交付 CSV 里」的（黑名单来自 --seen 文件，由 run_task.sh 从 CSV 导出）
  3) 按相关性规则过滤（AI 线索 + 产品岗角色词 − 非产品职能）
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from relevance import relevant


def jl_line(ln):
    ln = ln.strip()
    if not ln:
        return []
    try:
        v = json.loads(ln)
    except Exception:
        return []
    if isinstance(v, str):
        try:
            v = json.loads(v)
        except Exception:
            return []
    return v if isinstance(v, list) else []


def jid(u):
    return (u or '').rsplit('/', 1)[-1].replace('.html', '')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('harvest', nargs='+', help='harvest_multi.sh 的输出文件')
    ap.add_argument('--seen', default='/tmp/seen_ids.txt',
                    help='已有职位 id 黑名单（每行一个 id）')
    ap.add_argument('--out-prefix', default='batch',
                    help='输出文件名后缀，产物为 /tmp/cand_<prefix>.txt')
    a = ap.parse_args()

    seen = set()
    if os.path.exists(a.seen):
        for ln in open(a.seen, encoding='utf-8'):
            if ln.strip():
                seen.add(ln.strip())

    allrows, dup = {}, 0
    for p in a.harvest:
        if not os.path.exists(p):
            continue
        for ln in open(p, encoding='utf-8'):
            for x in jl_line(ln):
                k = jid(x.get('href'))
                if not k:
                    continue
                if k in allrows:
                    dup += 1
                    continue
                allrows[k] = x
    print(f'原始唯一职位: {len(allrows)}（去重 {dup}）')

    cand, old = {}, 0
    for k, x in allrows.items():
        if k in seen:
            old += 1
            continue
        if not relevant(x.get('name')):
            continue
        cand[k] = x
    print(f'已在已交付 CSV 中: {old} | 新候选（相关性过滤后）: {len(cand)}')

    urls = ['https://www.zhipin.com' + x['href'] for x in cand.values() if x.get('href')]
    cand_path = f'/tmp/cand_{a.out_prefix}.txt'
    list_path = f'/tmp/list_{a.out_prefix}.json'
    with open(cand_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(urls) + '\n')
    json.dump(list(cand.values()), open(list_path, 'w', encoding='utf-8'),
              ensure_ascii=False, indent=0)
    print(f'已写 {cand_path} 与 {list_path}')
    print(f'预估详情采集耗时：约 {len(urls) * 9.5 / 60:.0f} 分钟')


if __name__ == '__main__':
    main()
