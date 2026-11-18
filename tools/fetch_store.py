"""소상공인시장진흥공단 '상가(상권)정보 API'(공공데이터포털 15012005)에서 경남 7개 시의 보건의료 업소를 받아 JSON으로 저장한다.

    python tools/fetch_store.py "<저장할 JSON 경로>"

- 경남 전체(시도 코드 48)를 업종 대분류 '보건의료'로 걸러 받고, 7개 시 업소만 남긴다.
  응답에 건물관리번호(bldMngNo)와 층(flrNo)이 있어서 한 건물에 의원이 몇 곳 모였는지 셀 수 있다.
- 서비스키는 fetch_hours.py처럼 클립보드에서 읽는다.
표준 라이브러리만 쓴다.
"""
import json, sys, urllib.error, urllib.parse, urllib.request
from fetch_hours import clipboard_key

REGIONS = ['창원', '진주', '김해', '양산', '거제', '사천', '통영']
API = 'https://apis.data.go.kr/B553077/api/open/sdsc2/'
ROWS = 1000


def get(op, svc, **params):
    q = urllib.parse.urlencode({'serviceKey': svc, 'type': 'json', **params})
    try:
        raw = urllib.request.urlopen(f'{API}{op}?{q}', timeout=60).read()
    except urllib.error.HTTPError as e:
        sys.exit(f'HTTP {e.code}: ' + e.read()[:300].decode('utf-8', 'replace'))
    try:
        r = json.loads(raw)
    except ValueError:
        # 키가 틀리거나 아직 등록되지 않았으면 XML(OpenAPI_ServiceResponse)로 사유가 온다
        sys.exit('응답을 읽지 못했습니다: ' + raw[:300].decode('utf-8', 'replace'))
    if r.get('header', {}).get('resultCode') != '00':
        sys.exit(f'오류: {json.dumps(r.get("header", r), ensure_ascii=False)[:300]}')
    return r['body']


def main(out):
    key = urllib.parse.unquote(clipboard_key())
    large = get('largeUpjongList', key)['items']
    code = next(x['indsLclsCd'] for x in large if '보건' in x['indsLclsNm'])
    items, no, total = [], 0, 1
    while len(items) < total:
        no += 1
        body = get('storeListInDong', key, divId='ctprvnCd', key='48', indsLclsCd=code, pageNo=no, numOfRows=ROWS)
        total = int(body['totalCount'])
        if not body['items']:
            break
        items += body['items']
    keep = [x for x in items if any(x['signguNm'].startswith(c) for c in REGIONS)]
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(keep, f, ensure_ascii=False)
    print(f'경남 보건의료 {len(items)}/{total}곳 중 7개 시 {len(keep)}곳 저장: {out}')


if __name__ == '__main__':
    main(sys.argv[1])
