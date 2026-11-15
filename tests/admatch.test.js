const test = require('node:test');
const assert = require('node:assert/strict');
const M = require('../admatch.js');

const BASIS = '2026-06-30';
const MON_SAT = '0900-1900,0900-1900,0900-1900,0900-1900,0900-1900,0900-1600,,';
const Q = o => ({ region: '', emd: '', shop: '', depts: [], joint: false, fee: 0, days: 0, ps: 0, py: 0, year: 0, close: '', sat: '', sun: '', ...o });
const C = o => ({ key: 'l:x', name: '가약국', sgg: '진주시', emd: '장대동', pk: 'l', ps: 1, area: null, opened: '', hr: null, nearDp: [], smallMid: false, ...o });
const mark = (r, k) => r.marks.find(m => m.k === k);

test('기본 투약일수', () => {
  assert.equal(M.defaultDays(Q({ shop: 'gen' })), 75);
  assert.equal(M.defaultDays(Q({ shop: 'hosp' })), 45);
  assert.equal(M.defaultDays(Q({ depts: ['11', '13'] })), 3);
  assert.equal(M.defaultDays(Q({ depts: ['11', '01'] })), 7);
  assert.equal(M.defaultDays(Q({})), 7);
  assert.equal(M.defaultDays(Q({ shop: 'gen', days: 30 })), 30);
});

test('필요 약사 수: 정답이 알려진 광고는 1명', () => {
  // 2,200만원 ÷ 19,755원 ÷ 25.8일 ÷ 75 = 0.58 → 1명
  assert.equal(M.needPharm(Q({ shop: 'gen', fee: 2200 }), MON_SAT), 1);
  // 7일 기본값이면 2,200만원 ÷ 8,660원 ÷ 25.8 ÷ 75 = 1.31 → 2명
  assert.equal(M.needPharm(Q({ fee: 2200 }), MON_SAT), 2);
  // 영업시간 자료가 없으면 22일로 본다: 2,200만원 ÷ 19,755 ÷ 22 ÷ 75 = 0.67 → 1명
  assert.equal(M.needPharm(Q({ shop: 'gen', fee: 2200 }), null), 1);
});

test('상권: 종병·병원 앞은 병원권·중소병원 반경이면 ✓, 작은 병원이면 △', () => {
  assert.equal(mark(M.judge(C({ pk: 'h' }), Q({ shop: 'gen' }), BASIS), '상권').v, 'ok');
  assert.equal(mark(M.judge(C({ pk: 'm' }), Q({ shop: 'hosp' }), BASIS), '상권').v, 'ok');
  assert.equal(mark(M.judge(C({ smallMid: true }), Q({ shop: 'gen' }), BASIS), '상권').v, 'mid');
  assert.equal(mark(M.judge(C({}), Q({ shop: 'gen' }), BASIS), '상권').v, 'no');
});

test('상권: 의원 앞은 주변 의원이 있고 병원권이 아니면 ✓', () => {
  assert.equal(mark(M.judge(C({ nearDp: [['01']] }), Q({ shop: 'clinic' }), BASIS), '상권').v, 'ok');
  assert.equal(mark(M.judge(C({ pk: 'h', nearDp: [['01']] }), Q({ shop: 'clinic' }), BASIS), '상권').v, 'no');
  assert.equal(mark(M.judge(C({}), Q({ shop: 'clinic' }), BASIS), '상권').v, 'no');
});

test('처방 과목과 연합의원', () => {
  const q = Q({ depts: ['11', '13'] }), qj = Q({ depts: ['11', '13'], joint: true });
  assert.equal(mark(M.judge(C({ nearDp: [['11', '13']] }), qj, BASIS), '과목').v, 'ok');
  assert.equal(mark(M.judge(C({ nearDp: [['11'], ['13']] }), q, BASIS), '과목').v, 'ok');
  assert.equal(mark(M.judge(C({ nearDp: [['11'], ['13']] }), qj, BASIS), '과목').v, 'mid');
  assert.equal(mark(M.judge(C({ nearDp: [['11']] }), q, BASIS), '과목').v, 'mid');
  assert.equal(mark(M.judge(C({ nearDp: [['01']] }), q, BASIS), '과목').v, 'no');
});

test('약사 수는 다르면 △이고 빼지 않는다', () => {
  assert.equal(mark(M.judge(C({ ps: 1 }), Q({ ps: 1 }), BASIS), '약사').v, 'ok');
  assert.equal(mark(M.judge(C({ ps: 2 }), Q({ ps: 1 }), BASIS), '약사').v, 'mid');
});

test('조제료는 약사 수를 적으면 ⓘ, 안 적으면 추정 약사 수로 판정', () => {
  const c = C({ ps: 1, hr: MON_SAT });
  assert.equal(mark(M.judge(c, Q({ shop: 'gen', fee: 2200, ps: 1 }), BASIS), '조제료').v, 'info');
  assert.equal(mark(M.judge(c, Q({ shop: 'gen', fee: 2200 }), BASIS), '조제료').v, 'ok');
  assert.equal(mark(M.judge(c, Q({ fee: 2200 }), BASIS), '조제료').v, 'mid');        // 추정 2명, 신고 1명
  assert.equal(mark(M.judge(c, Q({ fee: 6000 }), BASIS), '조제료').v, 'no');         // 추정 4명
});

test('평수: 20% 안 ✓, 40% 안 △, 자료 없으면 —', () => {
  const want = 24 * 3.3058;
  assert.equal(mark(M.judge(C({ area: want * 1.19 }), Q({ py: 24 }), BASIS), '평수').v, 'ok');
  assert.equal(mark(M.judge(C({ area: want * 0.65 }), Q({ py: 24 }), BASIS), '평수').v, 'mid');
  assert.equal(mark(M.judge(C({ area: want * 1.5 }), Q({ py: 24 }), BASIS), '평수').v, 'no');
  assert.equal(mark(M.judge(C({}), Q({ py: 24 }), BASIS), '평수').v, 'na');
});

test('개설 연도: 1년 차이 안 ✓, 3년 안 △', () => {
  const c = C({ opened: '2013-09-05' });
  assert.equal(mark(M.judge(c, Q({ year: 2013 }), BASIS), '개설').v, 'ok');
  assert.equal(mark(M.judge(c, Q({ year: 2014 }), BASIS), '개설').v, 'ok');
  assert.equal(mark(M.judge(c, Q({ year: 2016 }), BASIS), '개설').v, 'mid');
  assert.equal(mark(M.judge(c, Q({ year: 2018 }), BASIS), '개설').v, 'no');
  assert.equal(mark(M.judge(C({}), Q({ year: 2013 }), BASIS), '개설').v, 'na');
  assert.equal(mark(M.judge(c, Q({ year: 2013 }), BASIS), '개설').t, '2013년 개설');
});

test('영업시간: 평일 마감, 토요일, 일·공휴일', () => {
  const c = C({ hr: MON_SAT });
  assert.equal(mark(M.judge(c, Q({ close: '19:00' }), BASIS), '평일 마감').v, 'ok');
  assert.equal(mark(M.judge(c, Q({ close: '18:00' }), BASIS), '평일 마감').v, 'mid');
  assert.equal(mark(M.judge(c, Q({ close: '17:00' }), BASIS), '평일 마감').v, 'no');
  assert.equal(mark(M.judge(c, Q({ sat: 'full' }), BASIS), '토요일').v, 'ok');
  assert.equal(mark(M.judge(c, Q({ sat: 'am' }), BASIS), '토요일').v, 'no');
  assert.equal(mark(M.judge(C({ hr: '0900-1800,0900-1800,0900-1800,0900-1800,0900-1800,0900-1300,,' }), Q({ sat: 'am' }), BASIS), '토요일').v, 'ok');
  assert.equal(mark(M.judge(c, Q({ sun: 'off' }), BASIS), '일·공휴일').v, 'ok');
  assert.equal(mark(M.judge(c, Q({ sun: 'open' }), BASIS), '일·공휴일').v, 'no');
  assert.equal(mark(M.judge(C({}), Q({ close: '19:00' }), BASIS), '평일 마감').v, 'na');
});

test('점수와 순위: 시군·읍면동으로 거르고 점수, ✗ 개수, 이름 순', () => {
  const cs = [
    C({ key: 'l:a', name: '나약국', ps: 2 }),
    C({ key: 'l:b', name: '가약국', ps: 1 }),
    C({ key: 'l:c', name: '다약국', ps: 1, emd: '상대동' }),
    C({ key: 'l:d', name: '라약국', ps: 1, sgg: '창원시 의창구', emd: '북면' }),
  ];
  const r = M.rank(cs, Q({ region: '진주', emd: '장대', ps: 1 }), BASIS);
  assert.deepEqual(r.map(x => x.c.key), ['l:b', 'l:a']);
  assert.equal(r[0].score, 2);
  assert.equal(r[1].score, 1);
});

test('점수를 매기는 조건이 없으면 scored는 false', () => {
  assert.equal(M.scored(Q({ region: '진주', emd: '북면' })), false);
  assert.equal(M.scored(Q({ depts: ['11'] })), true);
  assert.equal(M.scored(Q({ fee: 1000 })), true);
  assert.equal(M.scored(Q({ year: 2018 })), true);
});

test('동점이면 ✗가 적은 쪽, 그다음 이름 순이고 limit만큼 자른다', () => {
  // 세 곳 모두 2점이다. 가약국은 상권 ✗(0) + 약사 ✓(2)라 ✗가 1개, 나·다약국은 상권 △ + 약사 △라 ✗가 없다
  const cs = [
    C({ key: 'l:a', name: '가약국', pk: 'l', ps: 1 }),
    C({ key: 'l:b', name: '다약국', smallMid: true, ps: 2 }),
    C({ key: 'l:c', name: '나약국', smallMid: true, ps: 2 }),
  ];
  const q = Q({ shop: 'gen', ps: 1 });
  const all = M.rank(cs, q, BASIS);
  assert.deepEqual(all.map(r => [r.c.key, r.score, r.miss]), [['l:c', 2, 0], ['l:b', 2, 0], ['l:a', 2, 1]]);
  assert.deepEqual(M.rank(cs, q, BASIS, 2).map(r => r.c.key), ['l:c', 'l:b']);
});
