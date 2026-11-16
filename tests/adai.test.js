const test = require('node:test');
const assert = require('node:assert/strict');
const A = require('../adai.js');
const { FEE } = require('../admatch.js');

const REGIONS = ['전체', '창원', '진주'];
const DEPTS = [['01', '내과'], ['11', '소아청소년과'], ['13', '이비인후과']];
const C = o => ({ key: 'l:x', name: '가약국', sgg: '진주시', emd: '장대동', pk: 'l', ps: 1, area: 50, opened: '20180301',
  hr: '0900-1900,0900-1900,0900-1900,0900-1900,0900-1900,0900-1300,,', nearDp: [['11', '13'], ['01']], smallMid: false, ...o });

test('조건 스키마: 모든 칸이 필수이고 지역·과목은 고를 수 있는 값만', () => {
  const s = A.querySchema(REGIONS, DEPTS);
  assert.deepEqual(s.required.sort(), Object.keys(s.properties).sort());
  assert.equal(s.additionalProperties, false);
  assert.deepEqual(s.properties.region.enum, REGIONS);
  assert.deepEqual(s.properties.depts.items.enum, ['01', '11', '13']);
});

test('요청 본문: Gemini 구조화 출력과 생각 수준', () => {
  const b = A.readBody('진주 소아과 앞', REGIONS, DEPTS);
  assert.match(A.API, /models\/gemini-[^/]+:generateContent$/);
  assert.equal(b.generationConfig.responseMimeType, 'application/json');
  assert.equal(b.generationConfig.responseJsonSchema.properties.region.enum[0], '전체');
  assert.equal(b.generationConfig.thinkingConfig.thinkingLevel, 'low');
  assert.equal(A.pickBody('x', '', [], {}).generationConfig.thinkingConfig.thinkingLevel, 'medium');
  assert.ok(b.systemInstruction.parts[0].text.length > 0);
  assert.match(b.contents[0].parts[0].text, /<ad>\n진주 소아과 앞\n<\/ad>/);
});

test('toQuery: 범위 밖 값과 모르는 값은 비운다', () => {
  const q = A.toQuery({ region: '전체', emd: ' 북면 ', shop: 'gen', depts: ['11', '11', '99'], joint: true, fee: 2200, days: 77,
    ps: 0, py: 15, year: 1800, close: '6시', sat: 'off', sun: 'x', clues: '' }, REGIONS, DEPTS, FEE);
  assert.deepEqual(q, { region: '', emd: '북면', shop: 'gen', depts: ['11'], joint: true, fee: 2200, days: 0,
    ps: 0, py: 15, year: 0, close: '', sat: 'off', sun: '' });
  assert.equal(A.toQuery({ region: '진주', days: 75, close: '18:00' }, REGIONS, DEPTS, FEE).region, '진주');
  assert.equal(A.toQuery({ days: 75 }, REGIONS, DEPTS, FEE).days, 75);
  assert.equal(A.toQuery({ region: '창원마산합포구' }, [...REGIONS, '창원마산합포구'], DEPTS, FEE).region, '창원마산합포구');
  assert.equal(A.toQuery({ region: '창원마산합포구' }, REGIONS, DEPTS, FEE).region, '');
});

test('후보 한 줄: 약사·평수·개설·영업시간·주변 과목을 넣는다', () => {
  const t = A.candLine({ c: C(), score: 5 }, Object.fromEntries(DEPTS));
  assert.match(t, /key=l:x/);
  assert.match(t, /신고 약사 1명/);
  assert.match(t, /50㎡\(15평\)/);
  assert.match(t, /토 09:00-13:00, 일 휴무/);
  assert.match(t, /주변 의원 2곳\(과목: 소아청소년과 1, 이비인후과 1, 내과 1\)/);
  assert.match(t, /가까운 병원 없음/);
  assert.match(A.candLine({ c: C({ hosp: [{ n: '반도병원', typ: '병원', d: 12, g: 39 }, { n: '제일병원', typ: '종합병원', d: 0, g: 250 }] }), score: 0 }, {}),
    /가까운 병원 반도병원\(병원, 의사 12명, 39m\), 제일병원\(종합병원, 250m\)/);
  assert.match(A.candLine({ c: C({ area: null, hr: null, nearDp: [] }), score: 0 }, {}), /면적 자료 없음.*영업 자료 없음.*과목: 없음/);
});

test('cleanPicks: 후보에 없는 key는 버리고 확신도를 0~100으로', () => {
  const rows = [{ c: C({ key: 'l:a' }) }, { c: C({ key: 'p:1' }) }];
  const r = A.cleanPicks({ summary: 's', picks: [{ key: 'l:zz', confidence: 50, reason: '' },
    { key: 'p:1', confidence: 140, reason: 'r' }, { key: 'l:a', confidence: -3, reason: '' }] }, rows);
  assert.deepEqual(r.picks.map(p => [p.key, p.confidence]), [['p:1', 100], ['l:a', 0]]);
});

test('parseReply: 생각 조각을 빼고 글을 JSON으로 읽고, 차단·잘림·키 오류는 문장으로 던진다', () => {
  const ok = { candidates: [{ finishReason: 'STOP', content: { parts: [{ text: '생각', thought: true }, { text: '{"a":1}' }] } }] };
  assert.deepEqual(A.parseReply(200, ok), { a: 1 });
  const bad = { error: { code: 400, details: [{ reason: 'API_KEY_INVALID' }] } };
  assert.throws(() => A.parseReply(400, bad), /키가 맞지/);
  assert.throws(() => A.parseReply(403, {}), /키가 맞지/);
  assert.throws(() => A.parseReply(400, { error: { message: 'schema' } }), /실패했습니다\(400\)\. schema/);
  assert.throws(() => A.parseReply(402, {}), /결제 잔액/);
  assert.throws(() => A.parseReply(200, { promptFeedback: { blockReason: 'SAFETY' } }), /답하지 않았/);
  assert.throws(() => A.parseReply(200, { candidates: [{ finishReason: 'SAFETY', content: { parts: [] } }] }), /답하지 않았/);
  assert.throws(() => A.parseReply(200, { candidates: [{ finishReason: 'MAX_TOKENS', content: { parts: [] } }] }), /끊겼/);
  assert.throws(() => A.parseReply(500, null), /실패했습니다\(500\)/);
});
