(function(){
  // BOSS 数字混淆：私用区码点 - 0xE031 = 真实数字
  function decodeDigits(s){
    var out='';
    for(var i=0;i<s.length;i++){
      var c=s.charCodeAt(i);
      if(c>=0xE030 && c<=0xE03A){ out += String(c-0xE031); }
      else out += s[i];
    }
    return out;
  }
  function clean(s){
    return (s||'').replace(/\u00a0/g,' ').replace(/[ \t\u200b]+/g,' ').replace(/\n{3,}/g,'\n\n').trim();
  }
  function oneLine(s){ return clean((s||'').replace(/\s+/g,' ')); }
  // 过滤 BOSS 的隐藏干扰文本
  function junkFree(s){
    return oneLine(s)
      .replace(/来自BOSS直聘/g,'')
      .replace(/\bkanzhun\b/gi,'')
      .replace(/\bboss\b/gi,'')
      .replace(/\s{2,}/g,' ')
      .trim();
  }
  window.__bossDecode = decodeDigits;
  window.__bossClean = clean;
  window.__bossJunkFree = junkFree;

  window.__bossExtractList = function(){
    var cards = document.querySelectorAll('div.job-card-wrap');
    var res = [];
    for (var i=0;i<cards.length;i++){
      var c = cards[i];
      var nameEl = c.querySelector('.job-name');
      var salEl  = c.querySelector('.job-salary');
      var tags = [];
      c.querySelectorAll('ul.tag-list li').forEach(function(t){ var v=oneLine(t.textContent); if(v) tags.push(v); });
      res.push({
        name: clean(nameEl?nameEl.textContent:''),
        salary: salEl? decodeDigits(oneLine(salEl.textContent)) : '',
        company: oneLine((c.querySelector('.boss-name')||{}).textContent),
        area: oneLine((c.querySelector('.company-location')||{}).textContent),
        tags: tags,
        bossOnline: !!c.querySelector('.boss-online-icon'),
        href: nameEl? nameEl.getAttribute('href') : ''
      });
    }
    return JSON.stringify(res);
  };

  window.__bossExtractDetail = function(){
    var out = {};
    var q = function(sel){ return document.querySelector(sel); };

    var st = q('.info-primary .name h1') || q('.job-primary .name h1');
    out.name = clean(st? (st.getAttribute('title') || st.textContent) : '');

    var salEl = q('.info-primary .salary') || q('.job-primary .salary');
    out.salary = salEl? decodeDigits(oneLine(salEl.textContent)) : '';

    out.city = oneLine((q('.info-primary .text-city')||{}).textContent);
    out.exp  = oneLine((q('.info-primary .text-experiece')||{}).textContent);
    out.edu  = oneLine((q('.info-primary .text-degree')||{}).textContent);
    out.status = oneLine((q('.info-primary .job-status')||{}).textContent);

    // 公司信息：sider-company
    var sc = q('.sider-company');
    if (sc){
      var ca = sc.querySelector('.company-info a[title]');
      out.companyName = clean(ca? ca.getAttribute('title') : '');
      var ps = [];
      sc.querySelectorAll('.company-info ~ p, p').forEach(function(p){
        var t = oneLine(p.innerText||p.textContent);
        if (t && t !== '公司基本信息' && t !== '查看全部职位' && ps.indexOf(t)<0) ps.push(t);
      });
      out.companyPs = ps;
      var fin = ps.find(function(t){ return /(不需要融资|未融资|天使轮|A轮|B轮|C轮|D轮及以上|已上市|战略投资|已融资)/.test(t); });
      var scl = ps.find(function(t){ return /(人以上|\d+-\d+人|人)$/.test(t) && /\d/.test(t); });
      out.financing = fin || '';
      out.scale = scl || '';
      out.industry = '';
      for (var i=0;i<ps.length;i++){
        var t = ps[i];
        if (t===fin || t===scl) continue;
        if (t===out.companyName) continue;
        out.industry = t; break;
      }
    }

    // 招聘者
    var ACT_RE = /(刚刚活跃|今日活跃|本周活跃|\d+周内活跃|\d+月内活跃|\d+天内活跃|\d+日内活跃|半年前活跃|刚刚|1周内|1月内|3日内|在线)/;
    var bi = q('.job-boss-info');
    if (bi){
      var nm = bi.querySelector('.name') || bi.querySelector('h2') || bi.querySelector('h3');
      var nmText = oneLine(nm? nm.textContent : '');
      var am = nmText.match(ACT_RE);
      out.recruiterActive = am? am[1] : '';
      out.recruiter = oneLine(nmText.replace(ACT_RE,'').replace(/[·|]/g,'').trim());
      var attr = bi.querySelector('.boss-info-attr');
      out.recruiterAttr = oneLine(attr? attr.textContent : '');
      if (!out.recruiterActive){
        var bm = oneLine(bi.innerText||'').match(ACT_RE);
        out.recruiterActive = bm? bm[1] : '';
      }
    }

    // 技能标签（容器 innerText 会自动排除 BOSS 的隐藏干扰节点）
    var JUNK = {'boss':1,'kanzhun':1,'直聘':1,'boss直聘':1,'来自boss直聘':1,'':1};
    var kw = [];
    var kwBox = q('.job-keyword-list');
    if (kwBox){
      (kwBox.innerText||'').split(/[\n\/、|]+/).forEach(function(t){
        t = junkFree(t);
        if (!t || t.length>24) return;
        if (JUNK[t.toLowerCase()]) return;
        if (/^(来自|boss|kanzhun|直聘)/i.test(t)) return;
        if (kw.indexOf(t)<0) kw.push(t);
      });
    }
    out.skills = kw;

    // 岗位 JD
    var jd = '';
    var sec = q('.job-detail-section');
    if (sec){
      var raw = (sec.innerText||'');
      var idx = raw.indexOf('职位描述');
      if (idx >= 0) raw = raw.slice(idx + '职位描述'.length);
      jd = clean(raw);
    }
    out.jd = jd;
    // 去掉 JD 开头重复的技能标签行
    if (kw.length){
      var lines = out.jd.split('\n');
      var cut = 0;
      while (cut < lines.length && kw.indexOf(lines[cut].trim()) >= 0) cut++;
      if (cut > 0) out.jd = clean(lines.slice(cut).join('\n'));
    }
    // 去掉 JD 结尾混入的招聘者卡片（姓名 / 活跃状态 / 公司名 / · / 职位）
    (function(){
      var lines = out.jd.split('\n');
      var bossSet = {};
      [out.recruiter, out.recruiterActive, out.companyName, out.recruiterAttr, '·', '-', '|']
        .forEach(function(v){ if (v) bossSet[String(v).trim()] = 1; });
      var attrRaw = oneLine(out.recruiterAttr||'');
      if (attrRaw) attrRaw.split(/[·\s]+/).forEach(function(v){ if (v) bossSet[v]=1; });
      var n = lines.length;
      while (n > 1){
        var t = lines[n-1].trim();
        if (t === '' || bossSet[t]) { n--; continue; }
        break;
      }
      if (n < lines.length) out.jd = clean(lines.slice(0, n).join('\n'));
    })();

    out.url = location.href.split('?')[0];
    return JSON.stringify(out);
  };

  return 'ready';
})()
