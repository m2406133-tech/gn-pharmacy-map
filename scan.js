/* 반경 분석: 지도에서 고른 점의 반경 안 아파트 세대수와 병원·의원 의사 수, 약국 약사 수를 센다.
   화면을 건드리지 않아 node로 시험한다(tests/scan.test.js). index.html은 <script src="scan.js">로 읽어 전역 Scan으로 쓴다.
   아파트 세대수는 apt.json(tools/fetch_apt.py → tools/build_apt.py, 국토교통부 공동주택 K-apt)에 있다 */
(function (root) {
  // index.html의 gap과 같은 식(구면 근사, m 단위 반올림)
  const gap = (a, b) => { const k = Math.PI / 180;
    return Math.round(6371000 * Math.hypot((b.x - a.x) * k * Math.cos((a.y + b.y) / 2 * k), (b.y - a.y) * k)); };

  // set.apts는 hh(세대수), set.docs는 d(의사 수), set.pharms는 ps(약사 수)가 있는 {x, y} 목록이다.
  // 반경 R m 안의 것을 가까운 순으로 { x: 원래 객체, d: 거리 }로 두고, 세대·의사·약사 합을 함께 돌려준다
  function summarize(pt, R, set) {
    const near = xs => xs.map(x => ({ x, d: gap(pt, x) })).filter(z => z.d <= R).sort((a, b) => a.d - b.d);
    const sum = (zs, k) => zs.reduce((s, z) => s + (z.x[k] || 0), 0);
    const apts = near(set.apts), docs = near(set.docs), pharms = near(set.pharms);
    return { apts, docs, pharms, hh: sum(apts, 'hh'), d: sum(docs, 'd'), ps: sum(pharms, 'ps') };
  }

  const Scan = { gap, summarize };
  if (typeof module === 'object' && module.exports) module.exports = Scan;
  else root.Scan = Scan;
})(this);
