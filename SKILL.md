---
name: boss-zhipin-scraper
description: 用真实浏览器（computer use 方式）采集 BOSS 直聘职位数据，并处理其反爬：HeadlessChrome 指纹识别、极验点选验证码、薪资私用区数字混淆、JD 隐藏噪声 span。当用户要求「爬 BOSS 直聘 / zhipin 的岗位」「按表头采集招聘信息」「爬某城市某关键词的职位」时使用。
agent_created: true
---

# BOSS 直聘职位采集（浏览器驱动）

采集字段通常为：职位名称、薪资、公司、行业、融资阶段、公司规模、城市·区域、经验、学历、技能标签、招聘者、活跃时间、岗位JD、岗位链接。

## 🚀 快速开始（一键流程）

正常情况下**不要手工敲每一步**，直接用编排脚本：

```bash
# 0) 只做一次：装环境
~/.workbuddy/skills/boss-zhipin-scraper/scripts/setup.sh

# 1) 起后台 Chrome（必须 run_in_background: true）
~/.workbuddy/skills/boss-zhipin-scraper/scripts/launch_chrome.sh ~/boss-zhipin-work

# 2) 确认已登录（未登录先扫码，见 §3）
~/boss-zhipin-work/ab.sh eval 'document.cookie.indexOf("bst")>=0?"LOGGED":"NOLOGIN"'
#    ↑ 若报 SecurityError / 只返回 about:blank / 列表恒 0 条 → 见 §1 第 4 条的代理与锁污染排查

# 3) 一键采集（必须 run_in_background: true，全程 20~60 分钟）
~/.workbuddy/skills/boss-zhipin-scraper/scripts/run_task.sh \
  ~/boss-zhipin-work 101010100 "AI产品经理,AI产品,大模型产品经理" 200 \
  ~/boss-zhipin-work/boss_AI产品经理_北京.csv
```

`run_task.sh` 内部依次做：导黑名单 → 生成检索 URL → 采职位池 → 过滤候选 → 采详情 → 合并导出。
**输出 CSV 既是数据来源也是写入目标**，所以对同一个文件重复跑会自动累加、不丢历史、不重复。

后面的章节是这套流程的原理、坑位和手工排障方法。

## 0. 前置：装工具（只做一次）

> 📌 用户想直接下发任务时，可复用的**提示词模板**见 `references/采集任务提示词.md`（含标准版 / 精简版 / 参数表 / 已自动绕开的坑清单）。

```bash
mkdir -p ~/.workbuddy/binaries/node/workspace
cd ~/.workbuddy/binaries/node/workspace
~/.workbuddy/binaries/node/versions/*/bin/npm install agent-browser
# Chromium 下载必须走代理，否则 storage.googleapis.com 超时
export HTTPS_PROXY=http://127.0.0.1:7890 HTTP_PROXY=http://127.0.0.1:7890
./node_modules/.bin/agent-browser install
```

## 1. 四个必踩的环境坑

1. **沙箱代理挡住 localhost**：Bash 沙箱注入 `HTTP_PROXY=http://127.0.0.1:<port>`，会让 CDP 连接 9222 失败。所有浏览器命令前必须：
   ```bash
   unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY ALL_PROXY all_proxy
   export NO_PROXY="127.0.0.1,localhost"
   ```
   建议封装成 `ab.sh`（见 `scripts/ab.sh`）。
2. **后台进程会被回收**：启动 Chrome 必须用 `run_in_background: true` 的 Bash，否则命令一结束进程就没了。
3. **agent-browser 自带的 daemon 是 headless 的**：UA 里带 `HeadlessChrome`、`navigator.webdriver=true`，BOSS 立刻识别并反复弹验证码。
4. ⚠️ **启动 Chrome 前必须 unset 代理，否则页面根本加载不出来（最隐蔽的坑）**
   沙箱注入的 `HTTP_PROXY/HTTPS_PROXY=127.0.0.1:<port>` 会被 Chrome **继承**，Chrome 把所有外网请求发给这个沙箱代理，而它不放行 zhipin.com。
   **症状极具误导性**：`open` 照常打印 `✓ BOSS直聘` + 正确的 URL，看起来完全成功；但 `eval` 永远只能读到 `about:blank`，`/json/list` 里也只有 about:blank、没有目标页面，手动 `PUT /json/new?<url>` 建的新标签也会立即消失。
   **排查动作**：`env | grep -i proxy` 确认有注入 → 检查 Chrome 是否是**在 unset 之后**启动的。
   **解法**：`launch_chrome.sh` 和 `ab.sh` 内部都已 unset；另外 agent-browser 的 **daemon 同样会继承启动时的环境**，怀疑被污染时先 `ab.sh close --all` 把 daemon 清掉重建。用 curl 探测 9222 时务必带 `--noproxy '*'`。
   （另有一类**症状相同**的原因：profile 被上次非正常退出的锁占住，Chrome 以「profile 正被其他计算机使用」的降级模式启动。`launch_chrome.sh` 已内置清锁逻辑。）

## 2. 起一个「看起来正常」的浏览器

不要用 `agent-browser open` 直接起浏览器。改成自己起系统 Chrome（已落成 `scripts/launch_chrome.sh`，直接跑它即可）：

```bash
exec "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  --headless=new --remote-debugging-port=9222 \
  --user-data-dir="$PWD/.chrome-profile" \
  --user-agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36" \
  --no-first-run --no-default-browser-check --no-sandbox --disable-gpu \
  --window-size=1440,1000 "about:blank"
```
（`run_in_background: true`；macOS 上 `--no-sandbox` 必需，否则沙箱里 Chrome 起不来。）

然后全程用 `agent-browser --cdp 9222 --session boss <cmd>`。验证指纹：`navigator.webdriver === false` 且 UA 不含 Headless。

`open` 每次会新开标签，容易和旧标签混淆；固定用法是 `open` 后用 CDP `/json/list` 关掉多余的 page target，只留一个。

## 3. 扫码登录（用户不用看窗口）

```bash
ab.sh open "https://www.zhipin.com/web/user/"
# 截图找「APP扫码登录」标签坐标，鼠标点击切换
ab.sh eval 'document.body.innerText.indexOf("请重新刷新二维码")'   # >=0 表示已过期
```
二维码是 `blob:` 图片，**取原图**：
```js
(function(){var i=null;document.querySelectorAll("img").forEach(function(e){
  var b=e.getBoundingClientRect(); if(b.width>100&&b.height>100)i=e;});
  var c=document.createElement("canvas");c.width=i.naturalWidth;c.height=i.naturalHeight;
  c.getContext("2d").drawImage(i,0,0);return c.toDataURL("image/png")})()
```
输出是 `"data:image/png;base64,..."`，去掉外层引号、按 `base64,` 切分、base64 解码成 PNG，放大 3 倍再 `present_files` 给用户扫。

- 二维码 **1-2 分钟就过期**，生成后立刻展示，并叫用户马上扫。
- 登录成功标志：`document.cookie` 里出现 **`bst`**，且 URL 离开 `/web/user/`。
- 轮询登录状态要放 `run_in_background`。

## 4. 破解两个反爬点

**a) 薪资数字混淆**：DOM 里是私用区码点，真实数字 = `码点 - 0xE031`。
```js
function decodeDigits(s){var o='';for(var i=0;i<s.length;i++){var c=s.charCodeAt(i);
  o += (c>=0xE030&&c<=0xE03A)? String(c-0xE031) : s[i];}return o;}
```

**b) JD / 标签里的隐藏噪声 span**：BOSS 在文本中插入 `visibility:hidden`、0.1px 的 `<span>`，内容是 `boss` / `来自BOSS直聘` / `kanzhun` 等。
- 取文本要用**容器级 `innerText`**（会自动排除隐藏节点）。
- **不要**对单个元素取 innerText —— 元素自身 `display:none` 时 innerText 会回退成 `textContent`，噪声就跑出来了。
- 技能标签用 `.job-keyword-list` 的 innerText 按换行切分。

## 5. 选择器（2026-09 实测有效）

搜索结果页 `https://www.zhipin.com/web/geek/job?query=<kw>&city=<code>&page=N`
（城市码：北京 101010100，上海 101020100，深圳 101280600，广州 101280100，杭州 101210100）

卡片 `div.job-card-wrap`：
| 字段 | 选择器 |
|---|---|
| 职位名称 | `.job-name` |
| 薪资 | `.job-salary`（需 decodeDigits） |
| 经验/学历 | `ul.tag-list li` |
| 公司 | `.boss-name` |
| 城市·区域 | `.company-location` |
| 岗位链接 | `.job-name[href]` |

详情页 `/job_detail/xxx.html`：
| 字段 | 选择器 |
|---|---|
| 职位名称 | `.info-primary .name h1`（取 title 属性） |
| 薪资 | `.info-primary .salary` |
| 城市/经验/学历 | `.text-city` / `.text-experiece` / `.text-degree` |
| 技能标签 | `.job-keyword-list`（innerText 按换行切分） |
| 公司名 | `.sider-company .company-info a[title]` |
| 融资/规模/行业 | `.sider-company p` 依次第 1/2/3 个（跳过「公司基本信息」） |
| 招聘者 | `.job-boss-info .name`（含活跃时间，需剥离） |
| 岗位JD | `.job-detail-section` innerText，从「职位描述」之后截断 |

**注意**：搜索结果页卡片**没有发布时间**。表头里的「发布时间」实际上是招聘者的活跃时间（`刚刚活跃` / `3日内活跃` / `在线`），从详情页 `.job-boss-info` 取。

**JD 尾部会混入招聘者卡片**（姓名 / 活跃状态 / 公司名 / `·` / 职位，形如「任元 / 在线 / 三个逗号 / · / CEO」），因为 `.job-detail-section` 的 innerText 含右侧 boss 卡片。取完 JD 后必须从**尾部逐行剔除**：行内容 ∈ {招聘者, 活跃状态, 公司名, recruiterAttr 及其按 `·`/空格的分词, `·`}，遇到第一个不匹配的行就停。

## 6. 列表翻页：`page` 参数无效，靠「筛选条件 + 重载」扩池

⚠️ **重要**：`/web/geek/jobs?query=..&city=..&page=N` 里的 `page` **完全无效**。
- 第 1/2/3 页返回同一批 15 条（仅顺序浮动），页面没有任何分页控件，滚动到底也不会加载更多，`div.job-card-wrap` 恒为 15。
- 浏览器内部 `fetch('/wapi/zpgeek/search/joblist.json?...&page=2&pageSize=30')` 确实能翻页（返回 `resCount/hasMore/jobList`），但属于**接口调用**，若用户要求「只用 computer use」则不可用；先确认用户是否接受。

### 6.1 扩池主力手段：换筛选条件（同一批结果会变）

搜索页支持**直接用 URL 参数**加筛选，每换一个条件就换一批 15 条：

```
&experience=<exp>   &degree=<degree>   &salary=<salary>
&scale=<scale>      &stage=<stage>     &jobType=<1901全职|1903兼职>
```

编码不用猜：页面上所有筛选下拉都是 SPA 一次性渲染的，选项的 `ka` 属性里就带编码：

```js
// 导出全部筛选编码（dd 的索引顺序：职位类型/求职类型/薪资/经验/学历/行业/规模/融资阶段）
document.querySelectorAll(".filter-select-dropdown").forEach(function(d,i){
  var o=[]; d.querySelectorAll("li").forEach(function(e){
    o.push((e.textContent||"").trim()+"="+(e.getAttribute("ka")||"").replace(/^sel-job-rec-/,""));
  }); console.log(i, o.join(" "));
});
```

实测编码（2026-09）：

| 维度 | 参数 | 取值 |
|---|---|---|
| 求职类型 | `jobType` | 1901 全职 / 1903 兼职 |
| 薪资 | `salary` | 402 3K以下 / 403 3-5K / 404 5-10K / 405 10-20K / 406 20-50K / 407 50K以上 |
| 经验 | `experience` | 108 在校生 / 102 应届生 / 101 经验不限 / 103 1年以内 / 104 1-3年 / 105 3-5年 / 106 5-10年 / 107 10年以上 |
| 学历 | `degree` | 209 初中及以下 / 208 中专 / 206 高中 / 202 大专 / 203 本科 / 204 硕士 / 205 博士 |
| 规模 | `scale` | 301 0-20人 / 302 20-99人 / 303 100-499人 / 304 500-999人 / 305 1000-9999人 / 306 10000人以上 |
| 融资 | `stage` | 801 未融资 / 802 天使轮 / 803 A轮 / 804 B轮 / 805 C轮 / 806 D轮及以上 / 807 已上市 / 808 不需要融资 |

**实测产量（单关键词）**：36 个筛选 URL（1 个基线 + 8 经验 + 6 薪资 + 7 学历 + 6 规模 + 8 融资）跑完拿到 **325 条唯一职位**——足够凑首个 100 条。每个 URL 约 8.5s（open 7s + eval），36 个约 6 分钟。

> ⚠️ **单关键词的池子会见顶**。同一关键词重跑这 36 个组合，返回的还是那 325 条，扣掉已交付的 100 条 + 相关性过滤后**不够再凑 100 条**。要追加到 200+ 条，必须**换关键词**（见下）。

### 6.1.1 二级扩池：多关键词 × 筛选组合

把 query 换成同一语义族的多个词，每个词再套筛选组合，结果集互不重叠度很高。

实测（2026-09）用 6 个关键词：

```
AI产品经理 / AI产品 / 大模型产品经理 / AIGC产品经理 / Agent产品经理 / 智能产品经理
```

主关键词跑**全量组合**（基线 + 8 经验 + 6 薪资 + 4 学历 + 6 规模 + 8 融资 = 33 个），其余关键词只跑**精选组合**（基线 + 经验 104/105/106 + 薪资 405/406/407 + 融资 803/804/806/807 + 规模 304/305/306 + 学历 203/204 = 17 个），避免重复劳动：

- 合计 **113 个 URL ≈ 16 分钟** → **593 条唯一职位**（去重 1072 次）
- 剔除已在 CSV 的 97 条 + 相关性过滤 → **270 条新候选**，足够再交付 100 条以上

**注意**：筛选条件比较宽，结果里会混入大量弱相关岗（AI漫剧、AI剪辑、标注、销售…），必须再按标题做相关性过滤。

## 6.2 相关性过滤与猎头识别

**相关性**（用户口径：AI 产品经理大类，不限行业）：
- 必须含 AI 线索：`AI|ai|人工智能|智能|大模型|Agent|GPT|LLM`
- 必须有产品岗角色词：`产品经理|产品专家|产品负责人|产品总监|产品策划|产品岗|产品Lead|产品Owner`
- 强排除非产品职能：`标注|剪辑|漫剧|编导|学徒|开发|工程师|算法|测试|美工|写帖|抽卡|编剧|生图|校验|客服|讲师|导师|文案|设计|外贸|采购|行政|人事|财务|运营|BD|商务|市场|大客户|KA|实习`
- 「销售」不作一刀切：`AI销售产品经理` 含产品经理角色词 → 保留；`AI产品销售经理` → 排除。

**猎头 / 外包帖识别**（用户明确不要）——只看列表页看不出来，**必须抓详情页**：
- `recruiterAttr`（`.job-boss-info .boss-info-attr`）含 **`猎头`** → 典型值 `猎户星·猎头顾问`、`BOSS直聘猎头·猎头顾问`、`凯锐人力·猎头顾问`、`济南锐仕方达人才科技·猎头顾问`、`武汉仕和人力资源公司·猎头顾问`。
- 公司名命中 `人力资源|人力|人才|劳务|锐仕方达|佰钧成|外派|外包`。
- 标题/JD 含 `外派|外包`。
- 这类帖子的公司名常被替换成「某大型互联网公司」「北京某中型云计算公司」——**看到匿名公司名基本就是猎头帖**，可作为早期排除信号。

> ⚠️ **校验阶段别用宽正则扫「人力/人才/人力资源」**。`红杉中国/徐女士·人力资源HR`、`阅文集团/魏丽·人力资源总监`、`水滴科技/张蕊·招聘经理` 都是正常公司的 HR 发帖，会被 `(人力|人才|人力资源)` 全部误判成猎头（实测 13 条「疑似猎头」全是误报）。
> **判断猎头只看两件事**：① `招聘者` 字段里含 `猎头` 二字；② 公司名是匿名「某…公司」。不要把「人力/人才」这类词拿去扫公司名或职位名。
> 同理，JD 校验命中 `BOSS直聘` 时先看公司名——**BOSS 直聘自己发的岗**（公司名=BOSS直聘）正文里出现「BOSS直聘」是正常内容，不是隐藏 span 噪声。

## 7. 采集流程

> 一键版见开头「🚀 快速开始」。下面是分步手工流程，用于排障或只跑其中一段。

1. `ab.sh open <搜索URL>` → `eval "$(cat boss_extract.js)"` 注入 → `eval '__bossExtractList()'` 存列表。
2. 生成检索 URL：`scripts/build_urls.py --city <城市码> --kw "<关键词,逗号分隔>" --out /tmp/urls.txt`（多关键词规则见 §6.1.1）。
3. 扩池：`scripts/harvest_multi.sh <urls.txt> <out.txt>` 批量跑（后台 + `run_in_background: true`）。
4. 过滤候选：`scripts/filter_candidates.py <harvest.txt> --seen <黑名单文件> --out-prefix <批次名>`；黑名单要**先从已交付 CSV 导出 job id**（也可直接用 `run_task.sh`，它会自动做）。
5. 逐条详情：`scripts/scrape_batch.sh <urls.txt> <outdir>`。**实测约 9.5s/条**（open 7s + eval + sleep 2），200 条 ≈ **32 分钟**；单次后台任务用 `TaskOutput block=true` 最多等 10 分钟，需多轮等待。
6. 导出：**首选** `scripts/finalize_batch.py --csv <输出CSV> --list /tmp/list_<批次>.json --det <详情目录> --target <条数>`（兼容累加、剔猎头、清 JD 尾部）。历史遗留的 `export_csv.py` / `export_batch.py` / `export_batch2.py` / `finalize.py` 是早期分步版本，已被 `finalize_batch.py` 覆盖，新任务不必再用。

**批量化经验**：详情采集要按固定条数分批（每批 ≤200 条），每批跑完立即用 `finalize.py` 合并，避免中途失败全部重跑。**候选数量按目标的 1.8~2 倍准备**（猎头剔除率实测约 15~25%，本轮 200 条里剔掉 72 条）。

### ⚠️ 批量操作必须落成 `.sh` 文件

在 Bash 工具里写内联 `for` 循环跑浏览器操作，**会被 SIGTERM 杀掉（exit 137）且不产生任何输出**。同样的循环写进 `.sh` 文件再 `./x.sh` 执行则完全正常。凡是多轮 `open/eval` 的批处理，一律写成脚本文件（参考 `scripts/harvest_loop.sh`、`scripts/scrape_batch.sh`）。

### 其他易踩点

- 详情页 `.job-detail-container` 会随滚动/重渲染消失；`ab.sh open` 复用同一个 tab，但页面 SPA 可能自行跳转。每次关键操作前确认 `location.href` 与 page target 数量（CDP `/json/list`）。
- 列表解析出的薪资是带私用区码点的原始串，**导出时以详情页薪资为准**，列表薪资仅作参考。
- JSON 读取函数要同时兼容**双重编码**（浏览器 `eval` 输出是 `"\"...\""`）和**普通 JSON** 两种输入；只写 `json.loads(json.loads(s))` 会在普通 JSON 上静默失败并丢字段（如「城市·区域」的商圈）。

脚本模板见 `scripts/`：

| 类别 | 脚本 | 用途 |
|---|---|---|
| 入口 | `run_task.sh` | **一键跑完整流程**（建池→过滤→详情→导出） |
| 环境 | `setup.sh` / `launch_chrome.sh` / `ab.sh` | 装依赖 / 起后台 Chrome / agent-browser 包装 |
| 扩池 | `build_urls.py` / `harvest_multi.sh` | 生成检索 URL / 批量采职位池 |
| 过滤 | `filter_candidates.py` / `relevance.py` | 去重 + 相关性过滤规则 |
| 详情 | `scrape_batch.sh` / `boss_extract.js` | 批量采详情 / 页面提取函数 |
| 导出 | `finalize_batch.py` | 累加合并 + 剔猎头 + 清 JD 尾部 |
| 遗留 | `export_csv.py` / `export_batch.py` / `export_batch2.py` / `finalize.py` / `harvest_loop.sh` | 早期分步版本，已被取代，仅作参考 |

**改需求时只动这几处**：城市 → `--city`；岗位方向 → `--kw`；条数 → `--target`；表头/列 → 改 `FIELDS` 常量（`finalize_batch.py`）并同步 CSV 表头；口径松紧 → `relevance.py` 里的 `BAD` / `ROLE` / `AIHINT` 三个正则。

## 8. 合规提醒

只在用户自己的已登录账号下采集公开职位信息，控制频率，不要绕过付费墙或批量骚扰招聘者。
