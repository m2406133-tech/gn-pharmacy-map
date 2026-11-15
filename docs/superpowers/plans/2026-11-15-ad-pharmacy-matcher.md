# 매물 광고로 약국 찾기 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 편집 비밀번호를 넣은 브라우저에서 매물 광고의 조건을 입력하면, 그 광고일 수 있는 약국을 점수 순으로 보여 준다.

**Architecture:** 정적 사이트(index.html + local.json)에 기능을 더한다. 비교 규칙은 화면과 떨어진 순수 함수 파일 `admatch.js`에 두어 node로 시험하고, index.html은 후보 목록을 만들고 입력판·결과 목록을 그린다. 의원 진료과목은 `tools/build_local.py`가 심평원 진료과목 파일에서 읽어 local.json에 `dp` 열로 넣는다.

**Tech Stack:** 순수 JavaScript(빌드 도구 없음), Node 24의 `node:test`, Python 3 표준 라이브러리(build_local.py), 네이버 지도 API(기존).

**Spec:** `docs/superpowers/specs/2026-11-15-ad-pharmacy-matcher-design.md`

## Global Constraints

- 입력값과 결과는 저장하거나 전송하지 않는다. localStorage·sessionStorage·fetch를 새로 쓰지 않는다.
- "매물 찾기" 단추는 `sess.get(TOKEN_KEY)`가 있을 때만 그린다.
- 기존 `id`(ykiho 해시), rank·memo 키(h, p, m, c, l), local.json의 기존 열 순서는 바꾸지 않는다. 새 열 `dp`는 `m`·`c` 배열의 맨 끝에 붙는다.
- 상수: `ZONE = 100`, `MID_MIN = 10`, 약사 1명 하루 75건, 1평 = 3.3058㎡.
- 투약일수별 조제료(원): 1→6150, 3→7020, 5→7800, 7→8660, 10→9550, 15→11590, 30→14440, 45→16745, 60→19050, 75→19755, 90→20460, 91→20990 (45와 75는 30·60일, 60·90일 금액의 중간값).
- 기본 투약일수: 종병 앞 75, 병원 앞 45, 처방 과목이 소아청소년과(11)·이비인후과(13)뿐이면 3, 그 밖에는 7.
- 판정 점수: ✓ 2, △ 1, ✗ 0, —와 ⓘ는 점수 없음.
- 화면 문구와 주석은 한국어로 쓰고, 기존 코드의 문체(주석에 이유를 적는 방식)를 따른다.

## 명세와 달라지는 점(구현하며 정한 것)

- 비교 규칙을 index.html 안이 아니라 별도 파일 `admatch.js`에 둔다. node로 시험하기 위해서다.
- "매물 찾기" 단추는 지도 오른쪽 위가 아니라 기존 "편집" 단추 옆(`#editBar`)에 둔다. 토큰 처리와 다시 그리는 시점을 그대로 쓰기 위해서다.
- 입력판 `<dialog>`는 HTML에 늘 있지만 닫혀 있다. 여는 단추가 토큰이 있을 때만 생기므로 결과는 같다.
- "주변 의원"은 약국에서 `ZONE`(100m) 안의 의원과 중소병원이다(명세의 `localNear`는 같은 건물 30m 판정이라 맞지 않는다). 병원권 병원(DATA.hosp)에는 진료과목 자료가 없어서 과목 비교에 넣지 않는다.

## 파일 구성

| 파일 | 할 일 |
|---|---|
| `tools/build_local.py` (수정) | 진료과목 파일을 읽어 의원·중소병원에 `dp`를 넣는다. 마지막 줄의 정의되지 않은 `out` 변수를 고친다. |
| `local.json`, `version.json` (재생성) | `dp` 열이 더해진 자료 |
| `admatch.js` (새 파일) | 조제료 표, 기본 투약일수, 필요 약사 수, 조건별 판정(`judge`), 거르기와 순위(`rank`) |
| `tests/admatch.test.js` (새 파일) | `admatch.js`의 단위 시험 |
| `index.html` (수정) | CSS, `<script src="admatch.js">`, 입력판 dialog, 후보 목록(`adCandidates`), 결과 그리기, 단추와 클릭 처리 |

---

### Task 1: 의원 진료과목(`dp`)을 local.json에 넣기

**Files:**
- Modify: `tools/build_local.py` (모듈 설명 문자열, `main`의 의원 분류 직후, 마지막 `print`)
- Regenerate: `local.json`, `version.json`

**Interfaces:**
- Produces: local.json의 `columns.c`와 `columns.m` 맨 끝에 `dp` 열. 값은 진료과목코드를 `,`로 이은 문자열(예: `"01,11,13"`)이고, 과목이 없으면 열 값이 `null`(브라우저에서는 키가 없음). 코드 `00`(일반의)은 넣지 않는다.

- [ ] **Step 1: 진료과목 파일의 열 이름과 코드를 확인한다**

Run:
```bash
cd "/d/m24061/OneDrive/클로드코드 주방/proj/gn-pharmacy-map/tools" && PYTHONIOENCODING=utf-8 python -c "
import sys, collections, build_local as b
cnt = collections.Counter()
for i, r in enumerate(b.rows(sys.argv[1])):
    if i == 0: print(list(r.keys()))
    cnt[(r['진료과목코드'], r['진료과목코드명'])] += 1
for k, v in sorted(cnt.items()): print(k, v)
" "/c/Users/hj/Downloads/전국 병의원 및 약국 현황 2026.6/5.의료기관별상세정보서비스_03_진료과목정보(2026.6.).xlsx"
```
Expected: 첫 줄에 `['암호화요양기호', '요양기관명', '진료과목코드', '진료과목코드명', ...]`. 코드표에 `('01','내과')`, `('02','신경과')`, `('03','정신건강의학과')`, `('05','정형외과')`, `('10','산부인과')`, `('11','소아청소년과')`, `('12','안과')`, `('13','이비인후과')`, `('14','피부과')`, `('15','비뇨의학과')`, `('21','재활의학과')`, `('23','가정의학과')`가 있어야 한다. 열 이름이나 코드가 다르면 Task 1 Step 3과 Task 3의 `AD_DEPTS`를 출력값에 맞게 고친다.

- [ ] **Step 2: 지금 local.json을 비교용으로 복사한다**

Run:
```bash
cd "/d/m24061/OneDrive/클로드코드 주방/proj/gn-pharmacy-map" && cp local.json "/c/Users/hj/AppData/Local/Temp/claude/afb51c23930dc717/8688de4d-f0cc-4989-9b35-70f46f39d50d/scratchpad/local.before.json"
```

- [ ] **Step 3: build_local.py에 진료과목을 넣는다**

두 군데를 고친다.

(가) `main`에서 의원·중소병원을 나누는 `for r in inst:` 반복문이 끝난 바로 다음(`pharm = [...]` 앞)에 과목을 읽는 코드를 넣는다.

```python
    # 진료과목: 일반의만 있는 의원도 과목을 신고하므로 전문의 수가 아니라 신고 과목 목록을 쓴다. 00(일반의)은 뺀다
    keyed = {hashlib.sha1(r['암호화요양기호'].encode()).hexdigest()[:8] for r in inst}
    depts = {}
    for r in rows(find(folder, '5.*진료과목정보*.xlsx')):
        k = hashlib.sha1(r['암호화요양기호'].encode()).hexdigest()[:8]
        if k in keyed and r['진료과목코드'] and r['진료과목코드'] != '00':
            depts.setdefault(k, set()).add(r['진료과목코드'])
```

(나) `dp`는 열 순서를 지키려고 `p100` 다음에 붙인다. 기존 `p100` 반복문 바로 뒤에 넣어 다음 모양이 되게 한다.

```python
    allph = hph + local
    for c in clinics + mids:
        c['p100'] = sum(gap(c, p) <= 100 for p in allph)
    for c in clinics + mids:   # 열 순서를 지키려고 p100 다음에 붙인다
        if c['id'] in depts:
            c['dp'] = ','.join(sorted(depts[c['id']]))
    print(f"진료과목: 의원 {sum('dp' in c for c in clinics)}/{len(clinics)}곳, 중소병원 {sum('dp' in m for m in mids)}/{len(mids)}곳")
```

마지막 줄의 `print(f'{out} {out.stat().st_size // 1024}KB')`는 `out`이 정의되지 않아 저장 뒤에 NameError로 끝난다. 다음으로 바꾼다.

```python
    out = ROOT / 'local.json'
    print(f'{out} {out.stat().st_size // 1024}KB')
```

모듈 설명 문자열의 "- 영업시간 JSON..." 항목 다음 줄에 한 줄을 더한다.

```
- 진료과목(5.의료기관별상세정보서비스_03_진료과목정보)은 의원·중소병원의 dp에 과목코드를 ','로 이어 넣는다(00 일반의 제외).
```

- [ ] **Step 4: local.json을 다시 만든다**

Run:
```bash
cd "/d/m24061/OneDrive/클로드코드 주방/proj/gn-pharmacy-map" && PYTHONIOENCODING=utf-8 python tools/build_local.py "C:/Users/hj/Downloads/전국 병의원 및 약국 현황 2026.6" 2026-06-30 "C:/Users/hj/Downloads/건강_약국.csv" "C:/Users/hj/Downloads/nmc_pharmacy_hours_gn.json"
```
Expected: `진료과목: 의원 N/1504곳, 중소병원 M/112곳`(N은 1,400 이상)과 `중소병원 112곳, 의원 1504곳, 로컬 약국 983곳`, 마지막 줄에 `local.json ...KB`. 오류 없이 끝난다.

- [ ] **Step 5: `dp` 말고는 바뀐 것이 없는지 확인한다**

Run:
```bash
cd "/d/m24061/OneDrive/클로드코드 주방/proj/gn-pharmacy-map/tools" && PYTHONIOENCODING=utf-8 python -c "
import sys, json, dataio
a = dataio.unpack(json.load(open(sys.argv[1], encoding='utf-8')))
b = dataio.load_local()
for g in 'mcp':
    A = {x['id']: x for x in a[g]}; B = {x['id']: {k: v for k, v in x.items() if k != 'dp'} for x in b[g]}
    print(g, len(A), len(B), 'same ids' if A.keys() == B.keys() else 'IDS DIFFER', 'diff rows', sum(A[k] != B[k] for k in A if k in B))
print('hp', a['hp'] == b['hp'], 'hh', a['hh'] == b['hh'], 'basis', a['basis'] == b['basis'])
print('columns c', json.load(open('../local.json', encoding='utf-8'))['columns']['c'])
" "/c/Users/hj/AppData/Local/Temp/claude/afb51c23930dc717/8688de4d-f0cc-4989-9b35-70f46f39d50d/scratchpad/local.before.json"
```
Expected:
```
m 112 112 same ids diff rows 0
c 1504 1504 same ids diff rows 0
p 983 983 same ids diff rows 0
hp True hh True basis True
columns c [..., 'p100', 'dp']
```
`diff rows`가 0이 아니면 입력 파일이 예전 빌드와 다른 것이다. 멈추고 사용자에게 알린다(커밋하지 않는다).

- [ ] **Step 6: 커밋**

```bash
cd "/d/m24061/OneDrive/클로드코드 주방/proj/gn-pharmacy-map" && git add tools/build_local.py local.json version.json && git commit -m "feat(data): 의원·중소병원에 진료과목 코드(dp)를 넣음

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: 비교 규칙 `admatch.js`와 단위 시험

**Files:**
- Create: `admatch.js`
- Create: `tests/admatch.test.js`

**Interfaces:**
- Consumes: 없음(순수 함수).
- Produces: 브라우저에서는 전역 `AdMatch`, node에서는 `module.exports`.
  - 후보 객체 `Cand`: `{ key: 'p:<id>'|'l:<id>', name: string, sgg: string, emd: string, pk: 'h'|'m'|'l', ps: number, area: number|null (㎡), opened: 'YYYY-MM-DD'|'', hr: string|null (8칸), nearDp: string[][] (ZONE 안 의원·중소병원마다 과목코드 목록), smallMid: boolean (의사 MID_MIN 미만 중소병원의 zr 안) }`
  - 입력 객체 `Query`: `{ region: string ('' = 전체), emd: string, shop: ''|'gen'|'hosp'|'clinic', depts: string[], joint: boolean, fee: number (만원, 0 = 없음), days: number (0 = 기본값), ps: number, py: number, years: number, close: 'HH:MM'|'', sat: ''|'off'|'am'|'full', sun: ''|'off'|'open' }`
  - `AdMatch.FEE: {[days: number]: number}`
  - `AdMatch.defaultDays(q: Query): number`
  - `AdMatch.needPharm(q: Query, hr: string|null): number`
  - `AdMatch.judge(c: Cand, q: Query, basis: string): { marks: {k: string, v: 'ok'|'mid'|'no'|'na'|'info', t: string}[], score: number, miss: number }`
  - `AdMatch.scored(q: Query): boolean` (점수를 매기는 조건이 하나라도 있는가)
  - `AdMatch.rank(cands: Cand[], q: Query, basis: string, limit = 20): { c: Cand, marks, score, miss }[]`

- [ ] **Step 1: 실패하는 시험을 쓴다**

`tests/admatch.test.js`:

```js
const test = require('node:test');
const assert = require('node:assert/strict');
const M = require('../admatch.js');

const BASIS = '2026-06-30';
const MON_SAT = '0900-1900,0900-1900,0900-1900,0900-1900,0900-1900,0900-1600,,';
const Q = o => ({ region: '', emd: '', shop: '', depts: [], joint: false, fee: 0, days: 0, ps: 0, py: 0, years: 0, close: '', sat: '', sun: '', ...o });
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

test('개설 연차: 1년 안 ✓, 3년 안 △', () => {
  const c = C({ opened: '2013-09-05' });   // 기준일까지 12.8년
  assert.equal(mark(M.judge(c, Q({ years: 13 }), BASIS), '연차').v, 'ok');
  assert.equal(mark(M.judge(c, Q({ years: 10 }), BASIS), '연차').v, 'mid');
  assert.equal(mark(M.judge(c, Q({ years: 5 }), BASIS), '연차').v, 'no');
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
});
```

- [ ] **Step 2: 시험이 실패하는지 확인한다**

Run: `cd "/d/m24061/OneDrive/클로드코드 주방/proj/gn-pharmacy-map" && node --test tests/admatch.test.js`
Expected: FAIL, `Cannot find module '../admatch.js'`

- [ ] **Step 3: `admatch.js`를 쓴다**

```js
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
  const YEAR_MS = 365.25 * 864e5;

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
    if (q.years) {
      if (!c.opened) add('연차', 'na', '개설일 없음');
      else {
        const y = (Date.parse(basis) - Date.parse(c.opened)) / YEAR_MS, d = Math.abs(y - q.years);
        add('연차', d <= 1 ? 'ok' : d <= 3 ? 'mid' : 'no', `개설 ${Math.floor(y)}년`);
      }
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

  const scored = q => !!(q.shop || q.depts.length || q.ps || q.fee || q.py || q.years || q.close || q.sat || q.sun);

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
```

- [ ] **Step 4: 시험이 통과하는지 확인한다**

Run: `cd "/d/m24061/OneDrive/클로드코드 주방/proj/gn-pharmacy-map" && node --test tests/admatch.test.js`
Expected: `# pass 12`, `# fail 0`

- [ ] **Step 5: 커밋**

```bash
cd "/d/m24061/OneDrive/클로드코드 주방/proj/gn-pharmacy-map" && git add admatch.js tests/admatch.test.js && git commit -m "feat: 매물 광고 조건과 약국을 비교하는 규칙(admatch.js)과 시험

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: index.html에 입력판과 결과 목록을 붙이기

**Files:**
- Modify: `index.html`
  - CSS: `@media (max-width: 860px){` 줄 바로 앞
  - HTML: `<dialog id="pwDlg" ...>` 앞, `#editBar` 바로 아래
  - `<script src="admatch.js"></script>`: 본문 `<script>`(지금 300번째 줄 근처, `const NCP_KEY_ID`가 든 블록) 바로 앞
  - JS: `renderEditBar()` 함수, 문서 클릭 처리(`if (act === 'edit') startEdit();` 묶음), 그리고 `renderEditBar();` 첫 호출 바로 앞에 새 코드 묶음

**Interfaces:**
- Consumes: Task 2의 `AdMatch.rank`, `AdMatch.scored`, `AdMatch.FEE`. 기존 `P`, `LOC`(`c`, `m`, `p`, `hp`, `hh`, `basis`), `gap`, `ZONE`, `MID_MIN`, `REGIONS`, `esc`, `sess`, `TOKEN_KEY`, `focusPh(id: number, pan)`, `focusLoc(id: string, pan)`. 중소병원의 `zr`, 약국의 `pk`는 로컬 자료를 받은 뒤 정해진다.
- Produces: `adCandidates(): Cand[]`, `adQuery(form): Query`, `openAd()`.

- [ ] **Step 1: CSS를 더한다**

`@media (max-width: 860px){` 바로 앞에 넣는다.

```css
/* 매물 찾기: 편집 비밀번호를 넣은 브라우저에서만 여는 입력판. 좁은 화면에서는 아래쪽 절반을 덮는다 */
.ad-dlg{position:fixed;inset:12px 12px auto auto;margin:0;width:min(420px,calc(100vw - 24px));max-height:calc(100dvh - 24px);overflow:auto;padding:14px 16px;border:1px solid var(--line);border-radius:10px;background:#fff;color:var(--ink);box-shadow:0 6px 24px rgba(0,0,0,.18);z-index:50}
.ad-head{display:flex;justify-content:space-between;align-items:center;margin-bottom:8px}
.ad-head button{border:0;background:none;font-size:18px;padding:2px 6px}
.ad-grid{display:grid;grid-template-columns:1fr 1fr;gap:8px}
.ad-grid label{display:flex;flex-direction:column;gap:2px;font-size:12.5px}
.ad-depts{display:flex;flex-wrap:wrap;gap:4px 10px;margin:10px 0;padding:6px 10px;border:1px solid var(--line);border-radius:6px;font-size:12.5px}
.ad-depts label{display:flex;align-items:center;gap:4px}
.ad-go{width:100%;padding:8px;border-radius:6px}
.ad-list{list-style:none;margin:10px 0 0;padding:0}
.ad-list button{display:block;width:100%;padding:8px 4px;border:0;border-bottom:1px solid var(--line);background:none;text-align:left}
.ad-score{float:right;font-weight:600}
.ad-marks{display:block;font-size:12.5px}
.ad-list small{display:block;color:#555}
@media (max-width: 860px){ .ad-dlg{inset:auto 0 0 0;width:100vw;max-height:48dvh;border-radius:10px 10px 0 0} }
```

- [ ] **Step 2: 입력판 HTML을 더한다**

`<div id="editBar"></div>` 바로 다음 줄에 넣는다. 선택지는 Step 4에서 JS로 채운다.

```html
    <dialog id="adDlg" class="ad-dlg" aria-labelledby="adTitle">
      <form id="adForm">
        <div class="ad-head"><strong id="adTitle">매물 찾기</strong><button type="button" data-act="adclose" aria-label="닫기">✕</button></div>
        <div class="ad-grid">
          <label>시군<select name="region"></select></label>
          <label>읍면동<input name="emd" placeholder="예: 북면"></label>
          <label>상권<select name="shop"><option value="">상관없음</option><option value="gen">종병 앞</option><option value="hosp">병원 앞</option><option value="clinic">의원 앞</option></select></label>
          <label>월 조제료(만원)<input name="fee" type="number" min="0" inputmode="numeric"></label>
          <label>평균 투약일수<select name="days"></select></label>
          <label>약사 수(국장 포함)<input name="ps" type="number" min="1" inputmode="numeric"></label>
          <label>전용 평수<input name="py" type="number" min="1" inputmode="numeric"></label>
          <label>개설 연차(년)<input name="years" type="number" min="0" inputmode="numeric"></label>
          <label>평일 마감<input name="close" type="time"></label>
          <label>토요일<select name="sat"><option value="">모름</option><option value="off">휴무</option><option value="am">오전만</option><option value="full">종일</option></select></label>
          <label>일·공휴일<select name="sun"><option value="">모름</option><option value="off">휴무</option><option value="open">영업</option></select></label>
        </div>
        <fieldset class="ad-depts" id="adDepts"><legend>처방 과목</legend></fieldset>
        <button type="submit" class="ad-go">찾기</button>
      </form>
      <p id="adMsg" role="status"></p>
      <ol id="adList" class="ad-list"></ol>
    </dialog>
```

- [ ] **Step 3: `admatch.js`를 읽는다**

본문 `<script>`(바로 아래 줄이 `/* ===== 설정: 네이버 클라우드에서 발급받은 Client ID를 넣으세요 ===== */`인 것) 바로 앞 줄에 넣는다.

```html
<script src="admatch.js"></script>
```

- [ ] **Step 4: 후보 목록, 입력 읽기, 결과 그리기 코드를 더한다**

`renderEditBar();`가 처음 불리는 줄(`document.addEventListener('input', ...)` 묶음 바로 다음 줄) 바로 앞에 넣는다.

```js
/* 매물 찾기: 광고에 적힌 조건(약국 이름은 없다)을 넣으면 그 광고일 수 있는 약국을 점수 순으로 보여 준다.
   비교 규칙은 admatch.js에 있고, 여기서는 후보를 만들고 입력판을 그린다. 입력값과 결과는 어디에도 저장하지 않는다.
   단추는 편집 비밀번호를 넣은 브라우저(sess의 TOKEN_KEY)에서만 보인다(renderEditBar) */
const AD_DEPTS = [['01', '내과'], ['11', '소아청소년과'], ['13', '이비인후과'], ['05', '정형외과'], ['14', '피부과'], ['12', '안과'],
  ['10', '산부인과'], ['23', '가정의학과'], ['03', '정신건강의학과'], ['15', '비뇨의학과'], ['02', '신경과'], ['21', '재활의학과']];
const AD_DAYS = { 45: '30~60일 중간', 75: '60~90일 중간', 91: '91일 이상' };
const AD_SYM = { ok: '✓', mid: '△', no: '✗', na: '—', info: 'ⓘ' };
// 병원권 약국(DATA.ph)과 로컬 약국을 같은 모양으로 만든다. 로컬 자료를 받은 뒤 한 번만 만든다.
// 주변 의원은 약국에서 ZONE 안의 의원과 중소병원이다(병원권 병원은 진료과목 자료가 없어 넣지 않는다)
let adCands = null;
function adCandidates(){
  if (adCands) return adCands;
  const near = p => LOC.c.concat(LOC.m).filter(c => gap(p, c) <= ZONE).map(c => c.dp ? c.dp.split(',') : []);
  const small = p => LOC.m.some(m => m.d < MID_MIN && gap(p, m) <= m.zr);
  const mk = (key, p, ar, hr) => ({ key, name: p.n, sgg: p.sgg, emd: p.emd || '', pk: p.pk, ps: p.ps || 0, area: ar ?? null,
    opened: p.o || '', hr: hr || null, nearDp: near(p), smallMid: small(p) });
  adCands = P.map(p => mk('p:' + p.id, p, (LOC.hp || {})[p.id], (LOC.hh || {})[p.id]))
    .concat(LOC.p.map(p => mk('l:' + p.id, p, p.ar, p.hr)));
  return adCands;
}
function adQuery(f){
  const v = n => f.elements[n].value.trim(), num = n => +v(n) || 0;
  return { region: v('region') === '전체' ? '' : v('region'), emd: v('emd'), shop: v('shop'),
    depts: [...f.querySelectorAll('[name=dept]:checked')].map(x => x.value), joint: f.elements.joint.checked,
    fee: num('fee'), days: num('days'), ps: num('ps'), py: num('py'), years: num('years'),
    close: v('close'), sat: v('sat'), sun: v('sun') };
}
function adRender(rs){
  document.getElementById('adList').innerHTML = rs.map(r => `<li><button type="button" data-adgo="${r.c.key}">
    <b>${esc(r.c.name)}</b> <span>${esc(r.c.emd)}</span><span class="ad-score">${r.score}점</span>
    <span class="ad-marks">${r.marks.map(m => `${esc(m.k)} ${AD_SYM[m.v]}`).join(' · ')}</span>
    <small>${esc(r.marks.map(m => m.t).join(', '))}</small></button></li>`).join('');
}
function openAd(){
  if (!sess.get(TOKEN_KEY)) return;
  document.getElementById('adDlg').show();
}
(function initAd(){
  const f = document.getElementById('adForm'), d = document.getElementById('adDlg'), msg = document.getElementById('adMsg');
  f.elements.region.innerHTML = REGIONS.map(r => `<option>${r}</option>`).join('');
  f.elements.days.innerHTML = '<option value="">기본값</option>' +
    Object.keys(AdMatch.FEE).map(k => `<option value="${k}">${AD_DAYS[k] || k + '일'}</option>`).join('');
  document.getElementById('adDepts').insertAdjacentHTML('beforeend',
    AD_DEPTS.map(([c, n]) => `<label><input type="checkbox" name="dept" value="${c}">${n}</label>`).join('') +
    '<label><input type="checkbox" name="joint">연합의원(한 의원에 모두)</label>');
  f.addEventListener('submit', e => {
    e.preventDefault();
    if (!LOC.basis) { msg.textContent = '로컬 약국 자료를 불러오는 중입니다. 잠시 뒤 다시 눌러 주세요.'; return; }
    const q = adQuery(f);
    if (!AdMatch.scored(q)) { msg.textContent = '조건을 하나 이상 적어 주세요.'; adRender([]); return; }
    const rs = AdMatch.rank(adCandidates(), q, LOC.basis);
    msg.textContent = rs.length ? `점수 순 상위 ${rs.length}곳` : '조건에 맞는 약국이 없습니다.';
    adRender(rs);
  });
  document.getElementById('adList').addEventListener('click', e => {
    const b = e.target.closest('[data-adgo]'); if (!b || !state.map) return;
    const key = b.dataset.adgo;
    if (key[0] === 'p') focusPh(+key.slice(2), true); else focusLoc(key.slice(2), true);
  });
  // 닫으면 입력과 결과를 지운다(저장하지 않는다)
  d.addEventListener('close', () => { f.reset(); msg.textContent = ''; adRender([]); });
})();
```

- [ ] **Step 5: 단추와 클릭 처리를 연결한다**

`renderEditBar()`의 편집 중이 아닐 때 문자열을 바꾼다.

바꾸기 전:
```js
    ? `<button type="button" class="edit-open" data-act="edit">편집</button>${msg}`
```
바꾼 뒤:
```js
    ? `<button type="button" class="edit-open" data-act="edit">편집</button>${sess.get(TOKEN_KEY) ? '<button type="button" class="edit-open" data-act="ad">매물 찾기</button>' : ''}${msg}`
```

문서 클릭 처리에 두 줄을 더한다.

바꾸기 전:
```js
  else if (act === 'done') endEdit();
  else setRank(state.sel ? +b.dataset.ph : b.dataset.ph, +b.dataset.rank);
```
바꾼 뒤:
```js
  else if (act === 'done') endEdit();
  else if (act === 'ad') openAd();
  else if (act === 'adclose') document.getElementById('adDlg').close();
  else setRank(state.sel ? +b.dataset.ph : b.dataset.ph, +b.dataset.rank);
```

- [ ] **Step 6: 단위 시험이 여전히 통과하는지 확인한다**

Run: `cd "/d/m24061/OneDrive/클로드코드 주방/proj/gn-pharmacy-map" && node --test tests/admatch.test.js`
Expected: `# pass 12`, `# fail 0`

- [ ] **Step 7: 커밋**

```bash
cd "/d/m24061/OneDrive/클로드코드 주방/proj/gn-pharmacy-map" && git add index.html && git commit -m "feat: 편집 비밀번호를 넣은 브라우저에 매물 찾기 입력판을 더함

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: 브라우저에서 받아들임 시험

**Files:** 바꾸지 않는다(문제가 나오면 해당 Task의 파일을 고치고 그 Task의 커밋 방식으로 다시 커밋한다).

- [ ] **Step 1: 로컬 서버를 띄운다**

`.claude/launch.json`이 없으면 만든다.

```json
{
  "version": "0.0.1",
  "configurations": [
    { "name": "static", "runtimeExecutable": "python", "runtimeArgs": ["-m", "http.server", "8000"], "port": 8000 }
  ]
}
```
`preview_start {name: "static"}`로 연다. 네이버 지도 키가 localhost를 허용하지 않으면 지도가 뜨지 않으므로, 그때는 지도 없이 할 수 있는 확인(Step 2~4)만 하고 Step 5는 배포 뒤 사용자에게 확인을 부탁한다.

- [ ] **Step 2: 토큰이 없으면 단추가 없는지 확인한다**

javascript_tool:
```js
sessionStorage.removeItem('gn-pharmacy-token'); renderEditBar(); !!document.querySelector('[data-act=ad]')
```
Expected: `false`

- [ ] **Step 3: 정답이 알려진 광고 받아들임 시험**

시험용 가짜 토큰으로 단추만 띄워 본다(메모 불러오기는 401로 실패하지만 입력판 확인에는 상관없다). 로컬 자료가 다 받아진 뒤 실행한다.

```js
sessionStorage.setItem('gn-pharmacy-token', 'test'); renderEditBar();
const base = { region: '진주', emd: '', shop: 'gen', depts: [], joint: false, fee: 2200, days: 0, ps: 1, py: 0, years: 0, close: '', sat: '', sun: '' };
const a = AdMatch.rank(adCandidates(), base, LOC.basis), b = AdMatch.rank(adCandidates(), { ...base, ps: 0 }, LOC.basis);
const pos = rs => rs.findIndex(r => r.c.key === 'l:<정답 약국 id>');
({ btn: !!document.querySelector('[data-act=ad]'), withPs: pos(a), feeOnly: pos(b), marks: a[pos(a)] && a[pos(a)].marks })
```
Expected: `btn: true`, `withPs`와 `feeOnly`가 0~4(상위 5곳), `marks`에 `{k:'상권', v:'ok'}`, `{k:'약사', v:'ok'}`. 끝나면 `sessionStorage.removeItem('gn-pharmacy-token')`.

- [ ] **Step 4: 창원 북면과 거제·사천 광고 확인**

```js
const q = o => ({ region: '', emd: '', shop: '', depts: [], joint: false, fee: 0, days: 0, ps: 0, py: 0, years: 0, close: '', sat: '', sun: '', ...o });
const show = rs => rs.slice(0, 5).map(r => `${r.c.name}(${r.c.emd}) ${r.score} ${r.marks.map(m => m.k + m.v).join(' ')}`);
({
  bukmyeon: show(AdMatch.rank(adCandidates(), q({ region: '창원', emd: '북면', depts: ['11', '13'], joint: true, ps: 1, fee: 1140, close: '18:30' }), LOC.basis)),
  okpo: show(AdMatch.rank(adCandidates(), q({ region: '거제', emd: '옥포', depts: ['11'], fee: 1000, py: 15, close: '18:00', sun: 'off' }), LOC.basis)),
  suseok: show(AdMatch.rank(adCandidates(), q({ region: '사천', emd: '수석', shop: 'gen', fee: 2000, py: 25 }), LOC.basis)),
})
```
Expected: 세 목록 모두 해당 읍면동 약국만 나온다. 북면 목록의 1위는 `과목ok`(두 과목이 한 의원에 있음)이다. 표지와 설명(신고 약사, 면적, 마감 시각)이 local.json 값과 맞는지 1위 약국 하나를 골라 확인한다. 결과를 사용자에게 그대로 보여 준다(정답을 모르는 광고라 판단은 사용자가 한다).

- [ ] **Step 5: 화면 확인**

1. 가짜 토큰을 넣고 `renderEditBar()` 뒤 "매물 찾기"를 눌러 입력판이 열리는지, 진주·종병 앞·2200·약사 1로 "찾기"를 눌러 목록이 나오는지, 정답 약국을 누르면 지도가 그 약국으로 가고 정보창이 열리는지 본다.
2. "✕"로 닫으면 입력과 목록이 비는지 본다.
3. `resize_window {preset: "mobile"}`로 바꿔 입력판이 아래쪽 절반에 뜨고 지도가 보이는지 본다. 끝나면 `preset: "desktop"`.
4. `read_console_messages {onlyErrors: true}`에 새 오류가 없는지 본다(가짜 토큰으로 생긴 401 메모 오류는 무시한다).
5. 가짜 토큰을 지운다.

- [ ] **Step 6: 결과를 사용자에게 알린다**

푸시는 하지 않는다. 명세 문서에 정답이 알려진 광고 내용이 적혀 있고 저장소가 공개이므로, 푸시 여부와 그 내용을 남길지 사용자에게 묻는다.
