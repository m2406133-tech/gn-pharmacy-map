"""국토교통부 건축물대장(건축HUB) 표제부에서 경남 7개 시의 주택이 든 건물을 법정동마다 모두 받아 저장한다.

    python tools/fetch_house.py "<저장할 JSONL 경로>"

- 빌라(다세대·연립)·단독·다가구·상가주택의 세대·가구 수를 얻으려는 원자료다. 아파트도 함께 받고, K-apt 단지와
  겹치는 건물을 빼는 일과 좌표 붙이기는 다음 단계(build)에서 한다.
- 법정동코드(행정안전부 행정표준코드 API)로 7개 시의 법정동·리를 모두 구하고, 동마다 번지 없이 표제부(getBrTitleInfo)를
  끝까지 받는다. 주용도나 기타용도에 '주택'이 있거나 세대수·가구수가 있는 건물만 남기고, 필요한 칸만 저장한다.
- 세는 값이 용도마다 다르다: 공동주택은 세대수(hhldCnt), 단독·다가구·상가주택은 가구수(fmlyCnt)에 적혀 있다.
- 서비스키는 fetch_hours.py처럼 클립보드에서 읽는다. 결과는 한 줄에 한 동씩 덧붙이므로, 하루 호출 한도 등으로
  멈추면 같은 명령으로 다시 실행해 이어 받는다(이미 받은 동은 건너뛴다).
표준 라이브러리만 쓴다.
"""
import json, os, sys, urllib.parse
from fetch_hours import clipboard_key
from fetch_area import REGIONS, HUB, get, dong_codes

KEEP = ('mainPurpsCdNm', 'etcPurps', 'mainAtchGbCdNm', 'regstrKindCdNm', 'hhldCnt', 'fmlyCnt', 'hoCnt', 'grndFlrCnt',
        'bldNm', 'dongNm', 'platPlc', 'newPlatPlc', 'bun', 'ji', 'naRoadCd', 'naMainBun', 'naSubBun', 'mgmBldrgstPk')


def housing(x):
    return '주택' in (x.get('mainPurpsCdNm') or '') + (x.get('etcPurps') or '') or \
        int(x.get('hhldCnt') or 0) or int(x.get('fmlyCnt') or 0)


def title(key, code):
    """한 법정동의 표제부 전부. 한 쪽에 100줄까지만 준다."""
    items, no = [], 1
    while True:
        r = get(HUB + 'getBrTitleInfo', {'serviceKey': key, 'sigunguCd': code[:5], 'bjdongCd': code[5:],
                                         'numOfRows': 100, 'pageNo': no, '_type': 'json'})['response']
        if r['header']['resultCode'] != '00':
            sys.exit(f"getBrTitleInfo 오류 {r['header']['resultCode']}: {r['header']['resultMsg']}")
        got = (r['body'].get('items') or {}).get('item') or []
        items += [got] if isinstance(got, dict) else got
        if not got or len(items) >= int(r['body']['totalCount']):
            return items, no
        no += 1


def main(out):
    done = set()
    if os.path.exists(out):
        done = {json.loads(line)['code'] for line in open(out, encoding='utf-8') if line.strip()}
    key = urllib.parse.unquote(clipboard_key())
    calls = 0
    for city in REGIONS:
        codes = dong_codes(key, city)
        dongs = sorted((c, n) for n, c in codes.items() if n.split()[-1][-1] in '동리가' and c not in done)
        for i, (code, name) in enumerate(dongs, 1):
            items, n = title(key, code)
            calls += n
            rows = [{k: x.get(k) for k in KEEP} for x in items if housing(x)]
            with open(out, 'a', encoding='utf-8') as f:
                f.write(json.dumps({'code': code, 'name': name, 'all': len(items), 'items': rows}, ensure_ascii=False) + '\n')
            if i % 20 == 0 or i == len(dongs):
                print(f'{city}: {i}/{len(dongs)}동 (이번 실행 호출 {calls}번)', flush=True)
    print(f'끝: {out}')


if __name__ == '__main__':
    main(sys.argv[1])
