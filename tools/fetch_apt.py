"""국토교통부 공동주택(K-apt) API에서 경남 7개 시 아파트 단지의 세대수와 주소를 받아 JSON으로 저장한다.

    python tools/fetch_apt.py "<저장할 JSON 경로>"

- 공동주택 단지 목록제공 서비스(공공데이터포털 15057332)로 경남(시도 코드 48) 단지 코드를 받고,
  공동주택 기본 정보제공 서비스(15058453)로 단지마다 기본정보(세대수 kaptdaCnt, 도로명주소 doroJuso 등)를 받는다.
- 공동주택관리정보시스템에 가입한 단지만 있다. 작은 빌라·단독주택은 없다.
- 응답 원본을 그대로 저장한다. 좌표는 build_apt.py가 붙인다.
- 서비스키는 fetch_hours.py처럼 클립보드에서 읽는다. 받는 도중 멈추면 받은 데까지 저장하고,
  같은 저장 경로로 다시 실행하면 이미 받은 단지는 건너뛴다.
표준 라이브러리만 쓴다.
"""
import json, os, sys, time, urllib.error, urllib.parse, urllib.request
from fetch_hours import clipboard_key

REGIONS = ['창원', '진주', '김해', '양산', '거제', '사천', '통영']
LIST = 'https://apis.data.go.kr/1613000/AptListService4/getSidoAptList4'
INFO = 'https://apis.data.go.kr/1613000/AptBasisInfoServiceV5/getAphusBassInfoV5'


def get(url, svc, **params):
    q = urllib.parse.urlencode({'serviceKey': svc, '_type': 'json', **params})
    for wait in (3, 10, 30, 60, 120, 300, 600, None):   # 게이트웨이 오류가 몇 분씩 이어질 때가 있다
        try:
            raw = urllib.request.urlopen(f'{url}?{q}', timeout=60).read()
            r = json.loads(raw)
            # 게이트웨이가 가끔 HTTP_ERROR(04)·SERVICETIMEOUT_ERROR(05)를 돌려준다. 잠시 뒤 다시 하면 된다
            reason = r.get('OpenAPI_ServiceResponse', {}).get('cmmMsgHeader', {}).get('returnReasonCode')
            if reason in ('04', '05') and wait is not None:
                time.sleep(wait)
                continue
            break
        except urllib.error.HTTPError as e:
            msg = f'HTTP {e.code}: ' + e.read()[:300].decode('utf-8', 'replace')
            if e.code < 500 or wait is None:
                raise SystemExit(msg)
        except ValueError:
            # 키가 틀리거나 활용신청이 안 됐으면 XML(OpenAPI_ServiceResponse)로 사유가 온다
            raise SystemExit('응답을 읽지 못했습니다: ' + raw[:300].decode('utf-8', 'replace'))
        except (urllib.error.URLError, TimeoutError) as e:
            if wait is None:
                raise SystemExit(f'연결 실패: {e}')
        time.sleep(wait)
    r = r.get('response', r)
    code = str(r.get('header', {}).get('resultCode', ''))
    if code not in ('00', '000'):
        raise SystemExit(f'오류: {json.dumps(r.get("header", r), ensure_ascii=False)[:300]}')
    return r['body']


def items(body):
    """목록 응답의 items는 [..], {'item': [..]}, {'item': {..}} 가운데 하나다."""
    xs = body.get('items') or []
    if isinstance(xs, dict):
        xs = xs.get('item') or []
    return xs if isinstance(xs, list) else [xs]


def main(out):
    key = urllib.parse.unquote(clipboard_key())
    apts, no, total = [], 0, 1
    while len(apts) < total:
        no += 1
        body = get(LIST, key, sidoCode='48', pageNo=no, numOfRows=1000)
        total = int(body.get('totalCount', 0))
        got = items(body)
        if not got:
            break
        apts += got
    keep = [a for a in apts if any((a.get('as2') or '').startswith(c) for c in REGIONS)]
    print(f'경남 단지 {len(apts)}/{total}곳 중 7개 시 {len(keep)}곳')

    done = json.load(open(out, encoding='utf-8')) if os.path.exists(out) else []
    have = {d['kaptCode'] for d in done}
    try:
        for i, a in enumerate(keep):
            if a['kaptCode'] in have:
                continue
            info = get(INFO, key, kaptCode=a['kaptCode']).get('item') or {}
            done.append({**a, **info})
            if len(done) % 100 == 0:
                print(f'{len(done)}/{len(keep)}', flush=True)
            time.sleep(0.1)   # 몰아서 부르면 게이트웨이 오류가 잦다
    finally:
        with open(out, 'w', encoding='utf-8') as f:
            json.dump(done, f, ensure_ascii=False)
        print(f'{len(done)}곳 저장: {out}')


if __name__ == '__main__':
    main(sys.argv[1])
