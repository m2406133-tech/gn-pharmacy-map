"""네이버 검색 API(지역 검색)로 병원·의원·약국의 지도 위 위치(POI 좌표)를 받아 poi.json으로 저장한다.

    python tools/fetch_poi.py "<저장할 poi.json 경로>" [--limit N] [--legacy]

- 심평원 좌표는 건물 단위라 같은 건물의 의원과 약국이 한 점에 겹친다. 네이버 지도가 아이콘을 찍는 업소별 좌표로 바꾸려고
  index.html의 DATA(병원·병원권 약국)와 local.json(중소병원·의원·로컬 약국)의 이름과 주소로 한 곳씩 찾는다.
- 네이버 클라우드 콘솔 > NAVER API HUB에서 Application을 등록(검색 API 선택)해 받은 Client ID와 Client Secret을 '공백으로 이어 한 줄로' 복사해 두고
  실행하면 클립보드에서 읽는다. 함께 쓰는 PC라서 읽자마자 클립보드를 비우고 어디에도 저장하지 않는다.
- 결과는 { 'h:병원 no' | 'p:약국 id' | 'm:중소병원 id' | 'c:의원 id' | 'l:로컬 약국 id': [경도, 위도] } 이다.
  찾지 못하거나 도로명 주소가 다른 곳은 넣지 않으므로 심평원 좌표를 그대로 쓴다.
- 조회 결과는 저장 경로 옆 .cache.json에 쌓아 두어, 중간에 멈춰도 같은 명령으로 이어 받는다.
표준 라이브러리만 쓴다.
"""
import difflib, json, os, re, subprocess, sys, time, urllib.error, urllib.parse, urllib.request
import dataio

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
# 기본은 네이버 클라우드의 NAVER API HUB(콘솔에서 발급한 키). 예전 개발자센터(developers.naver.com) 키는 --legacy로 쓴다
HUB = ('https://naverapihub.apigw.ntruss.com/search/v1/local', 'X-NCP-APIGW-API-KEY-ID', 'X-NCP-APIGW-API-KEY')
LEGACY = ('https://openapi.naver.com/v1/search/local.json', 'X-Naver-Client-Id', 'X-Naver-Client-Secret')
API = HUB
MAX_M = 300          # 심평원 좌표에서 이보다 멀리 떨어진 결과는 다른 곳으로 보고 버린다
NAME_OK = 0.6        # 같은 도로명 주소일 때 이름 닮음 기준
NAME_ONLY = 0.85     # 주소가 맞지 않을 때 이름만으로 받아들이는 기준(MAX_M 안일 때만)


def clipboard_keys():
    raw = subprocess.run(['powershell', '-NoProfile', '-Command', 'Get-Clipboard -Raw'],
                         capture_output=True, text=True).stdout.strip()
    parts = re.split(r'[\s,:]+', raw)
    if len(parts) != 2 or any(len(p) < 8 for p in parts):
        sys.exit('클립보드에 Client ID와 Client Secret이 없습니다. 두 값을 공백으로 이어 한 줄로 복사한 뒤 다시 실행하세요.')
    subprocess.run(['clip'], input=b'')
    return parts


def norm(s):
    s = re.sub(r'<[^>]+>', '', s or '')
    s = re.sub(r'\([^)]*\)', '', s)
    return re.sub(r'[\s·ㆍ.,\-]+', '', s)


ROAD = re.compile(r'([가-힣0-9]+(?:로|길)\s?\d+(?:-\d+)?)')


def road(addr):
    m = ROAD.search((addr or '').split(',')[0].split('(')[0])
    return m.group(1).replace(' ', '') if m else None


def meters(x1, y1, x2, y2):
    import math
    return math.hypot((x1 - x2) * 91000, (y1 - y2) * 110574)


def lonlat(it):
    x, y = float(it['mapx']), float(it['mapy'])
    return (x / 1e7, y / 1e7) if x > 1e6 else (x, y)


def search(ids, query):
    q = urllib.parse.urlencode({'query': query, 'display': 5, 'sort': 'random'})
    req = urllib.request.Request(f'{API[0]}?{q}', headers={API[1]: ids[0], API[2]: ids[1]})
    for wait in (2, 8, None):
        try:
            return json.loads(urllib.request.urlopen(req, timeout=30).read())['items']
        except urllib.error.HTTPError as e:
            if e.code in (401, 403):
                sys.exit(f'HTTP {e.code}: 키가 틀렸거나 애플리케이션에 검색 API 사용이 설정되지 않았습니다. ' + e.read()[:200].decode('utf-8', 'replace'))
            last = f'HTTP {e.code}'
        except (urllib.error.URLError, TimeoutError, ValueError) as e:
            last = str(e)
        if wait:
            time.sleep(wait)
    sys.exit('조회 실패: ' + last)


def pick(f, items):
    """심평원 업소 f({'n','a','x','y'})와 가장 맞는 검색 결과의 (경도, 위도, 근거)를 돌려준다. 없으면 None"""
    want_road, want_name = road(f['a']), norm(f['n'])
    best = None
    for it in items:
        name = norm(it['title'])
        sim = difflib.SequenceMatcher(None, want_name, name).ratio()
        lon, lat = lonlat(it)
        d = meters(f['x'], f['y'], lon, lat)
        if d > MAX_M:
            continue
        same_road = want_road and road(it.get('roadAddress')) == want_road
        if same_road and sim >= NAME_OK:
            score = 2 + sim
        elif sim >= NAME_ONLY:
            score = 1 + sim
        else:
            continue
        if not best or score > best[0]:
            best = (score, lon, lat, '도로명' if same_road else '이름', d)
    return best and (best[1], best[2], best[3], best[4])


def facilities():
    s = open(os.path.join(ROOT, 'index.html'), encoding='utf-8').read()
    data, _ = json.JSONDecoder().raw_decode(s[s.index('const DATA = ') + 13:])
    loc = dataio.load_local()
    out = [(f"h:{h['no']}", h['n'], h) for h in data['hosp']] + [(f"p:{p['id']}", p['n'], p) for p in data['ph']]
    out += [(f"{k}:{x['id']}", x['n'], x) for k in 'mc' for x in loc[k]] + [(f"l:{x['id']}", x['n'], x) for x in loc['p']]
    return out


def region(f):
    m = re.search(r'경상남도\s+(\S+시)\s*(\S*구)?', f['a'])
    return ' '.join(g for g in (m.groups() if m else ()) if g)


def main(out, limit=None):
    ids = clipboard_keys()
    cache_path = out + '.cache.json'
    cache = json.load(open(cache_path, encoding='utf-8')) if os.path.exists(cache_path) else {}
    todo = [t for t in facilities() if t[0] not in cache]
    if limit:
        todo = todo[:limit]
    for i, (key, name, f) in enumerate(todo, 1):
        items = search(ids, f"{region(f)} {re.sub(r'<[^>]+>', '', name)}")
        hit = pick(f, items)
        cache[key] = hit and [round(hit[0], 7), round(hit[1], 7), hit[2], round(hit[3])]
        if i % 50 == 0 or i == len(todo):
            json.dump(cache, open(cache_path, 'w', encoding='utf-8'), ensure_ascii=False)
            print(f'{i}/{len(todo)} 조회', flush=True)
        time.sleep(0.12)
    json.dump(cache, open(cache_path, 'w', encoding='utf-8'), ensure_ascii=False)
    poi = {k: v[:2] for k, v in cache.items() if v}
    json.dump(poi, open(out, 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
    dataio.write_version()   # poi.json이 저장소의 poi.json일 때 version.json의 해시를 갱신한다
    kinds = {}
    for k, v in cache.items():
        t = k[0]
        a = kinds.setdefault(t, [0, 0, 0])
        a[0] += 1; a[1] += bool(v); a[2] += bool(v) and v[2] == '도로명'
    for t, (n, ok, rd) in sorted(kinds.items()):
        print(f'{t}: {n}곳 중 {ok}곳 찾음(도로명 일치 {rd})')
    moved = [v[3] for v in cache.values() if v]
    print(f'저장 {len(poi)}곳: {out}  (심평원 좌표와의 거리 중앙값 {sorted(moved)[len(moved) // 2] if moved else 0}m)')


if __name__ == '__main__':
    args = sys.argv[1:]
    if '--legacy' in args:
        API = LEGACY
    lim = int(args[args.index('--limit') + 1]) if '--limit' in args else None
    main(args[0], lim)
