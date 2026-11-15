/* 매물 광고 조건과 약국 후보를 비교하는 순수 함수 모음. 화면을 건드리지 않아 node로 시험한다(tests/admatch.test.js).
   index.html은 <script src="admatch.js">로 읽어 전역 AdMatch로 쓴다.
   규칙의 근거는 docs/superpowers/specs/2026-11-15-ad-pharmacy-matcher-design.md에 있다 */
(function (root) {
  // 2026년 투약일수별 처방 1건당 조제료(원, 내복약, 점수당 105.5원). 45와 75는 30·60일, 60·90일 금액의 중간값이다.
  // 1·3·5·91일은 기본 금액 보도 그대로이고, 나머지는 마약류 포함 금액 보도에서 마약류 가산 270원을 뺀 값이다
  const FEE = { 1: 6150, 3: 7020, 5: 7800, 7: 8660, 10: 9550, 15: 11590, 30: 14440, 45: 16745, 60: 19050, 75: 19755, 90: 20460, 91: 20990 };
  const PT = { ok: 2, mid: 1, no: 0 };
  const DAY_LIMIT = 75;          // 약사 1명이 하루 75건을 넘으면 조제료가 삭감된다
  const PYEONG = 3.3058;         // 1평(㎡)

  // 투약일수를 고르지 않았으면 상권과 과목으로 정한다. 종병 앞은 60~90일, 병원 앞은 30~60일의 중간이다
  function defaultDays(q) {
    if (q.days) return q.days;
    if (q.shop === 'gen') return 75;
    if (q.shop === 'hosp') return 45;
    if (q.depts.length && q.depts.every(d => d === '11' || d === '13')) return 3;
    return 7;
  }
  // 영업시간 hr은 월~일, 공휴일 8칸을 쉼표로 이은 '0900-1900,…'이고 쉬는 날은 빈칸이다
  const slots = hr => hr.split(',');
  const closeMin = v => { const t = v.split('-')[1]; return +t.slice(0, 2) * 60 + +t.slice(2); };
  const toMin = s => { const [h, m] = s.split(':'); return +h * 60 + +m; };
  const fmt = m => `${String(Math.floor(m / 60)).padStart(2, '0')}:${String(m % 60).padStart(2, '0')}`;
  // 한 달 영업일: 영업하는 요일(월~일) 수 × 4.3주. 자료가 없거나 영업일이 없으면 22일로 본다
  const workDays = hr => (hr ? slots(hr).slice(0, 7).filter(Boolean).length * 4.3 : 0) || 22;

  function needPharm(q, hr) {
    return Math.max(1, Math.ceil(q.fee * 10000 / FEE[defaultDays(q)] / workDays(hr) / DAY_LIMIT));
  }
  // 월~금 마감 시각 중 가장 많이 나온 값(분). 평일에 모두 쉬면 null
  function weekdayClose(hr) {
    const n = {};
    slots(hr).slice(0, 5).filter(Boolean).map(closeMin).forEach(m => { n[m] = (n[m] || 0) + 1; });
    const ks = Object.keys(n).map(Number).sort((a, b) => n[b] - n[a] || a - b);
    return ks.length ? ks[0] : null;
  }

  function judge(c, q, basis) {
    const marks = [], add = (k, v, t) => marks.push({ k, v, t });
    if (q.shop === 'gen' || q.shop === 'hosp') {
      // 광고의 "종병"은 중소병원인 경우가 많아서(정답이 알려진 광고의 종병은 의사 12명인 중소병원이었다) 종병과 병원을 같은 규칙으로 넓게 본다
      add('상권', c.pk === 'h' || c.pk === 'm' ? 'ok' : c.smallMid ? 'mid' : 'no',
        c.pk === 'h' ? '병원권' : c.pk === 'm' ? '중소병원 반경' : c.smallMid ? '작은 병원 반경' : '병원 반경 밖');
    } else if (q.shop === 'clinic') {
      add('상권', c.nearDp.length && c.pk !== 'h' ? 'ok' : 'no', c.pk === 'h' ? '병원권' : `주변 의원·병원 ${c.nearDp.length}곳`);
    }
    if (q.depts.length) {
      const all = new Set(c.nearDp.flat()), hit = q.depts.filter(d => all.has(d)).length;
      const one = c.nearDp.some(ds => q.depts.every(d => ds.includes(d)));
      add('과목', hit === 0 ? 'no' : hit < q.depts.length || (q.joint && !one) ? 'mid' : 'ok',
        `고른 과목 ${hit}/${q.depts.length}` + (q.joint ? (one ? ', 한 의원에 모두' : ', 한 의원에 모두는 아님') : ''));
    }
    if (q.ps) add('약사', c.ps === q.ps ? 'ok' : 'mid', `신고 약사 ${c.ps}명`);
    if (q.fee) {
      const n = needPharm(q, c.hr), d = Math.abs(n - c.ps);
      // 약사 수를 적었으면 그쪽이 더 정확하므로 조제료 추정은 보여 주기만 한다
      if (q.ps) add('조제료', 'info', `추정 약사 ${n}명`);
      else add('조제료', d === 0 ? 'ok' : d === 1 ? 'mid' : 'no', `추정 약사 ${n}명, 신고 ${c.ps}명`);
    }
    if (q.py) {
      if (c.area == null) add('평수', 'na', '면적 자료 없음');
      else {
        const want = q.py * PYEONG, r = Math.abs(c.area - want) / want;
        add('평수', r <= 0.2 ? 'ok' : r <= 0.4 ? 'mid' : 'no', `${Math.round(c.area)}㎡(${Math.round(c.area / PYEONG)}평)`);
      }
    }
    if (q.year) {
      // 광고의 개설 연도는 양도인이 인수한 해일 수도 있어서 넓게 본다
      const y = parseInt(c.opened, 10), d = Math.abs(y - q.year);
      if (!y) add('개설', 'na', '개설일 없음');
      else add('개설', d <= 1 ? 'ok' : d <= 3 ? 'mid' : 'no', `${y}년 개설`);
    }
    const hours = [['close', '평일 마감'], ['sat', '토요일'], ['sun', '일·공휴일']].filter(([k]) => q[k]);
    if (hours.length && !c.hr) hours.forEach(([, k]) => add(k, 'na', '영업시간 자료 없음'));
    else if (hours.length) {
      const s = slots(c.hr);
      if (q.close) {
        const w = weekdayClose(c.hr), d = w == null ? Infinity : Math.abs(w - toMin(q.close));
        add('평일 마감', d <= 30 ? 'ok' : d <= 60 ? 'mid' : 'no', w == null ? '평일 휴무' : `평일 ${fmt(w)} 마감`);
      }
      if (q.sat) {
        const kind = !s[5] ? 'off' : closeMin(s[5]) <= 14 * 60 ? 'am' : 'full';
        add('토요일', kind === q.sat ? 'ok' : 'no', { off: '토 휴무', am: '토 오전만', full: '토 종일' }[kind]);
      }
      if (q.sun) {
        const open = !!(s[6] || s[7]);
        add('일·공휴일', (open ? 'open' : 'off') === q.sun ? 'ok' : 'no', open ? '일·공휴일 영업' : '일·공휴일 휴무');
      }
    }
    return { marks, score: marks.reduce((t, m) => t + (PT[m.v] || 0), 0), miss: marks.filter(m => m.v === 'no').length };
  }

  const scored = q => !!(q.shop || q.depts.length || q.ps || q.fee || q.py || q.year || q.close || q.sat || q.sun);

  // 시군·읍면동만 후보를 거르고, 나머지 조건은 점수만 매긴다. 점수 높은 순, ✗ 적은 순, 이름 순이다
  function rank(cands, q, basis, limit = 20) {
    const emd = q.emd.trim();
    return cands.filter(c => (!q.region || c.sgg.startsWith(q.region)) && (!emd || c.emd.includes(emd)))
      .map(c => ({ c, ...judge(c, q, basis) }))
      .sort((a, b) => b.score - a.score || a.miss - b.miss || a.c.name.localeCompare(b.c.name, 'ko'))
      .slice(0, limit);
  }

  const AdMatch = { FEE, defaultDays, needPharm, judge, scored, rank };
  if (typeof module === 'object' && module.exports) module.exports = AdMatch;
  else root.AdMatch = AdMatch;
})(this);
