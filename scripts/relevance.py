# -*- coding: utf-8 -*-
import json, os, re

# 强排除：非产品岗职能
BAD = re.compile(r'(标注|剪辑|漫剧|编导|学徒|开发|工程师|算法|测试|美工|写帖|抽卡|编剧|生图|校验|客服|讲师|导师|文案|设计|外贸|采购|行政|人事|财务|运营|BD|商务|市场|大客户|KA|实习)')
# 产品岗角色词
ROLE = re.compile(r'(产品经理|产品专家|产品负责人|产品总监|产品策划|产品岗|产品Lead|产品lead|产品Owner|产品owner|产品Leader)')
AIHINT = re.compile(r'(AI|ai|Ai|人工智能|智能|大模型|Agent|GPT|LLM)')

def load_seen(paths):
    seen = {}
    for p in paths:
        if not os.path.exists(p): continue
        for ln in open(p):
            ln = ln.strip()
            if not ln: continue
            try: arr = json.loads(json.loads(ln))
            except Exception: continue
            for x in arr:
                k = (x.get('href') or '').rsplit('/',1)[-1].replace('.html','')
                if k: seen.setdefault(k, x)
    return seen

def relevant(name):
    n = name or ''
    if not AIHINT.search(n): return False
    if BAD.search(n): return False
    if not ROLE.search(n): return False
    # 销售类：只有在同时含产品经理角色词时才保留（如「AI销售产品经理」）
    return True

def jl(p):
    s = open(p, encoding='utf-8').read().strip()
    try: v = json.loads(s)
    except Exception: return None
    return json.loads(v) if isinstance(v, str) else v
