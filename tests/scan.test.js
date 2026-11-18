const test = require('node:test');
const assert = require('node:assert/strict');
const S = require('../scan.js');

const O = { x: 128.6, y: 35.2 };
// gap은 지구 반지름 6,371km 구면이라 위도 1도 = 6371000·π/180 ≈ 111,195m다. dy미터 북쪽 점
const N = (dy, o) => ({ x: O.x, y: O.y + dy / (6371000 * Math.PI / 180), ...o });

test('거리: 북쪽 300m', () => {
  assert.equal(S.gap(O, N(300)), 300);
});

test('반경 안 아파트·병원·의원·약국을 세고 합친다', () => {
  const r = S.summarize(O, 300, {
    apts: [N(100, { n: '가아파트', hh: 1200 }), N(250, { n: '나아파트', hh: 800 }), N(400, { n: '먼아파트', hh: 3000 })],
    docs: [N(50, { n: '가내과', d: 2 }), N(120, { n: '나병원', d: 12 }), N(310, { n: '먼의원', d: 5 })],
    pharms: [N(60, { n: '가약국', ps: 2 }), N(500, { n: '먼약국', ps: 1 })],
  });
  assert.deepEqual(r.apts.map(z => z.x.n), ['가아파트', '나아파트']);
  assert.equal(r.hh, 2000);
  assert.equal(r.docs.length, 2);
  assert.equal(r.d, 14);
  assert.equal(r.pharms.length, 1);
  assert.equal(r.ps, 2);
});

test('가까운 순으로 두고 거리를 붙인다', () => {
  const r = S.summarize(O, 300, { apts: [N(200, { hh: 1 }), N(10, { hh: 1 })], docs: [], pharms: [] });
  assert.deepEqual(r.apts.map(z => z.d), [10, 200]);
});
