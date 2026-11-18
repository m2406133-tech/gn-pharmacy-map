const test = require('node:test');
const assert = require('node:assert/strict');
const B = require('../bldg.js');

test('주소 열쇠: 쉼표나 괄호 앞 도로명주소만 띄어쓰기 없이 쓴다', () => {
  assert.equal(B.addrKey('경상남도 창원시 성산구 중앙대로 124, 3층 (중앙동)'), '경상남도창원시성산구중앙대로124');
  assert.equal(B.addrKey('경상남도 창원시 성산구 중앙대로 124 (중앙동, 메디빌딩)'), '경상남도창원시성산구중앙대로124');
  assert.equal(B.addrKey('경상남도  창원시 성산구 중앙대로 124'), '경상남도창원시성산구중앙대로124');
  assert.equal(B.addrKey(undefined), '');
});

const A = '경상남도 창원시 성산구 중앙대로 124', Z = '경상남도 진주시 진주대로 1';
const c = (n, a) => ({ n, a });

test('의원이 min곳 이상인 주소만 메디컬 빌딩이고, 이름이 없으면 빈 문자열이다', () => {
  const cs = [c('가내과', A + ', 2층'), c('나소아과', A + ', 3층'), c('다이비인후과', A + ' (중앙동)'), c('라의원', Z), c('마의원', Z + ', 2층')];
  const bs = B.medicalBuildings(cs, { [B.addrKey(A)]: '메디타워' }, 3);
  assert.equal(bs.length, 1);
  assert.equal(bs[0].name, '메디타워');
  assert.deepEqual(bs[0].c.map(x => x.n), ['가내과', '나소아과', '다이비인후과']);
  assert.equal(B.medicalBuildings(cs, {}, 2)[1].name, '');
});

test('의원이 많은 순', () => {
  const cs = [...'ab'].map(n => c(n, A)).concat([...'cde'].map(n => c(n, Z)));
  assert.deepEqual(B.medicalBuildings(cs, {}, 2).map(b => b.c.length), [3, 2]);
});
