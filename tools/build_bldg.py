"""소상공인시장진흥공단 '상가(상권)정보'(fetch_store.py로 받은 JSON)에서 의원이 든 건물의 이름을 뽑아 bldg.json을 만든다.

    python tools/build_bldg.py "<fetch_store.py로 받은 JSON>"

- bldg.json은 { 주소 열쇠: 건물명 }이다. 주소 열쇠는 도로명주소에서 쉼표·괄호 앞만 띄어쓰기 없이 쓴 값으로, bldg.js의 addrKey와 같다.
- 메디컬 빌딩은 심평원 주소로 가르고(bldg.js), 이 파일은 이름만 붙인다. 상가정보는 7개 시 의원의 절반도 담고 있지 않아서다.
- local.json의 로컬 의원 주소에 있는 건물만 넣는다. local.json을 다시 빌드했으면 이 스크립트도 다시 돌린다.
표준 라이브러리만 쓴다.
"""
import json, re, sys
from collections import Counter
import dataio

addr_key = lambda a: re.sub(r'\s', '', re.split(r'[,(]', a or '')[0])


def main(src):
    want = {addr_key(c['a']) for c in dataio.load_local()['c']}
    names = {}
    for s in json.loads(open(src, encoding='utf-8').read()):
        k, n = addr_key(s.get('rdnmAdr')), (s.get('bldNm') or '').strip()
        if k in want and n:
            names.setdefault(k, Counter())[n] += 1
    out = {k: c.most_common(1)[0][0] for k, c in sorted(names.items())}
    (dataio.ROOT / 'bldg.json').write_text(json.dumps(out, ensure_ascii=False, separators=(',', ':')) + '\n', encoding='utf-8')
    dataio.write_version()
    print(f'로컬 의원 주소 {len(want)}곳 중 {len(out)}곳에 건물명을 붙였습니다: {dataio.ROOT / "bldg.json"}')


if __name__ == '__main__':
    main(sys.argv[1])
