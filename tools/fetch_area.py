"""국토교통부 건축물대장(건축HUB)에서 약국이 든 건물의 호실별·층별 면적을 받아 JSON으로 저장한다.

    python tools/fetch_area.py "<인허가 약국 CSV>" "<저장할 JSON 경로>" [시 이름]

- 인허가 약국 파일(행정안전부 전국약국표준데이터)의 지번주소를 법정동코드(행정안전부 행정표준코드 API)와
  번·지로 바꿔 건물을 찾는다. 시 이름(예: 사천)을 주면 그 시만 받는다.
- 집합건물이면 전유공용면적(호실별 전유·공용 면적)을, 아니면 층별개요(층별 용도·면적)를 받는다.
  주택 용도 줄은 버린다. 어느 호실이 약국인지는 build_local.py가 고른다.
- 서비스키는 fetch_hours.py처럼 클립보드에서 읽는다. 두 API 모두 공공데이터포털 활용신청이 필요하다.
- API가 가끔 빈 응답을 주므로 몇 번 다시 시도한다. 그래도 멈추면 받은 데까지 저장하고,
  같은 저장 경로로 다시 실행하면 이미 받은 약국은 건너뛴다.
표준 라이브러리만 쓴다.
"""
import csv, json, os, re, sys, time, urllib.error, urllib.parse, urllib.request
from fetch_hours import clipboard_key

REGIONS = ['창원', '진주', '김해', '양산', '거제', '사천', '통영']
HUB = 'https://apis.data.go.kr/1613000/BldRgstHubService/'


def get(url, params):
    for wait in (3, 10, 30, None):
        try:
            raw = urllib.request.urlopen(url + '?' + urllib.parse.urlencode(params), timeout=60).read()
            return json.loads(raw)
        except urllib.error.HTTPError as e:
            last = f'HTTP {e.code}: ' + e.read()[:300].decode('utf-8', 'replace')
            if e.code < 500:   # 키 오류 같은 4xx는 다시 해도 같다
                break
        except (urllib.error.URLError, TimeoutError) as e:
            last = f'연결 실패: {e}'
        except ValueError:
            last = '응답을 읽지 못했습니다: ' + raw[:300].decode('utf-8', 'replace')
        if wait:
            time.sleep(wait)
    sys.exit(last)


def dong_codes(key, city):
    """'경상남도 사천시 사천읍 수석리' 같은 법정동 이름 → 10자리 법정동코드"""
    out, no, seen = {}, 1, 0
    while True:
        r = get('https://apis.data.go.kr/1741000/StanReginCd/getStanReginCdList',
                {'ServiceKey': key, 'pageNo': no, 'numOfRows': 1000, 'type': 'json', 'locatadd_nm': f'경상남도 {city}시'})
        if 'StanReginCd' not in r:
            sys.exit(f'법정동코드 조회 실패: {json.dumps(r, ensure_ascii=False)[:300]}')
        head, body = r['StanReginCd']
        rows = body['row']
        seen += len(rows)
        out.update((x['locatadd_nm'], x['region_cd']) for x in rows)
        if not rows or seen >= head['head'][0]['totalCount']:
            return out
        no += 1


def jibun(addr, codes):
    """지번주소 → (법정동코드, 산 여부, 번, 지). 법정동 이름은 가장 길게 맞는 것을 쓴다."""
    name = max((n for n in codes if addr.startswith(n + ' ')), key=len, default=None)
    m = name and re.match(r'\s*(산\s*)?(\d+)(?:번지)?(?:\s*-\s*(\d+)|\s*(\d+)\s*호)?', addr[len(name):])
    if not m:
        return None
    return codes[name], bool(m.group(1)), int(m.group(2)), int(m.group(3) or m.group(4) or 0)


def hub(key, op, code, san, bun, ji):
    """건축HUB 조회. 한 쪽에 100줄까지만 준다(numOfRows를 더 크게 줘도 100줄). 주택 용도 줄은 버린다.
    큰 아파트 단지는 줄이 수만 개라 100쪽(1만 줄)까지만 본다."""
    items, no, seen = [], 1, 0
    while no <= 100:
        r = get(HUB + op, {'serviceKey': key, 'sigunguCd': code[:5], 'bjdongCd': code[5:], 'platGbCd': int(san),
                           'bun': f'{bun:04d}', 'ji': f'{ji:04d}', 'numOfRows': 100, 'pageNo': no, '_type': 'json'})['response']
        if r['header']['resultCode'] != '00':
            sys.exit(f"{op} 오류 {r['header']['resultCode']}: {r['header']['resultMsg']}")
        got = (r['body'].get('items') or {}).get('item') or []
        got = [got] if isinstance(got, dict) else got
        seen += len(got)
        items += [x for x in got if '주택' not in (x.get('mainPurpsCdNm') or '')]
        if not got or seen >= int(r['body']['totalCount']):
            break
        no += 1
    return items


def main(license_file, out, only=None):
    rows = [r for r in csv.DictReader(open(license_file, encoding='cp949', errors='replace'))
            if r['영업상태명'] == '영업/정상' and r['지번주소'].startswith('경상남도')]
    data = json.load(open(out, encoding='utf-8')) if os.path.exists(out) else {}
    done = len(data)
    key = clipboard_key()
    cache = {}
    try:
        for city in [c for c in REGIONS if not only or c == only]:
            mine = [r for r in rows if r['지번주소'].split()[1].startswith(city) and r['관리번호'] not in data]
            if not mine:
                continue
            codes = dong_codes(key, city)
            for i, r in enumerate(mine, 1):
                j = jibun(r['지번주소'], codes)
                if j is None:
                    data[r['관리번호']] = {'n': r['사업장명'], 'jibun': r['지번주소'], 'err': '지번을 읽지 못함'}
                    continue
                if j not in cache:
                    expos = hub(key, 'getBrExposPubuseAreaInfo', *j)
                    cache[j] = {'expos': expos} if expos else {'flr': hub(key, 'getBrFlrOulnInfo', *j)}
                data[r['관리번호']] = dict(cache[j], n=r['사업장명'], jibun=r['지번주소'])
                if i % 50 == 0:
                    print(f'{city}: {i}/{len(mine)}곳')
            print(f'{city}: 약국 {len(mine)}곳 받음')
    finally:
        with open(out, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False)
        print(f'{len(data)}곳 저장(이번에 {len(data) - done}곳): {out}')


if __name__ == '__main__':
    main(*sys.argv[1:4])
