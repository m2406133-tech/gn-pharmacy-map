"""fetch_house.py로 받은 건축물대장 표제부에서 아파트(K-apt) 밖의 주택 세대수를 세어 약 100m 격자로 모은 house.json을 만든다.

    python tools/build_house.py "<fetch_house.py JSONL>" "<fetch_apt.py JSON>" [--geocode [개수]]

- 세는 값: 세대수(hhldCnt)가 있으면 세대수, 없으면 가구수(fmlyCnt), 둘 다 없으면 단독주택·상가주택(근생+기타용도 '주택')은 1,
  그 밖의 용도는 0으로 본다. 부속건축물은 뺀다.
- K-apt 단지 건물은 apt.json에서 이미 세므로 뺀다. 도로명주소(길 이름+건물번호)나 지번(동·리+번지)이 K-apt 단지와 같은 건물이다.
  주소가 달라도 apt.json 단지와 이름이 닮고(SIMILAR 이상) NEAR_APT 안에 있는 공동주택은 같은 단지로 보고 빼되,
  아직 덜 찬 단지에서만, 주소로 이미 뺀 세대와 합쳐 그 단지의 K-apt 세대수(FILL배까지)를 넘지 않을 만큼만 뺀다. 그래서 '주영에이스빌1차'처럼
  이름은 닮았지만 다른 차수인 단지는, 닮은 단지('3차')가 주소로 이미 다 찼으면 남는다.
  K-apt에 없거나 K-apt 세대수가 비어 apt.json에 빠진 아파트는 여기서 센다.
- 좌표는 네이버 클라우드 Maps Geocoding으로 도로명주소를 바꾼 값이다. 결과는 입력 파일 옆 .geo.json에 쌓는다.
  --geocode를 주면 아직 없는 주소를 받는다(개수를 주면 그만큼만, 시험용). 키는 build_apt.py --geocode와 같은
  Maps Application의 Client ID와 Secret을 공백으로 이어 클립보드에 복사해 둔다. --geocode가 없으면 캐시만 쓴다.
- 좌표가 없는 건물(도로명주소가 없거나 지오코딩이 못 찾은 건물)은 같은 법정동에서 번지가 가장 가까운 건물
  (지번 차이 MAX_GAP 이하)의 좌표를 빌려 쓴다.
- house.json은 { basis: 받은 날, cell: 격자 크기(도), h: [[경도, 위도, 세대수], …] }이다. 경위도는 격자 안 건물들의 세대 가중 평균이다.
표준 라이브러리만 쓴다.
"""
import bisect, difflib, json, math, os, re, sys, time, urllib.error, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor
from collections import defaultdict
from datetime import date
import dataio
import fetch_poi as fp

CELL = 0.001     # 격자 크기(도). 위도 0.001도는 약 111m, 경도 0.001도는 경남에서 약 91m
MAX_GAP = 10     # 도로명주소 없는 건물이 좌표를 빌릴 때 허용하는 번지 차이
WORKERS = 6      # 지오코딩을 나란히 부르는 수
SAVE_EVERY = 1000
NEAR_APT = 300   # 이름이 닮은 K-apt 단지와 이 거리(m) 안이면 같은 단지로 본다
SIMILAR = 0.7    # 이름 닮음 기준(한쪽이 다른 쪽을 품으면 1.0, 아니면 difflib 비율)
FILL = 1.1       # 덜 찬 단지는 이름으로 뺄 때 세대수의 이 배까지 채운다(K-apt와 건축물대장 세대수 차이 여유)


def count(x):
    h, f = int(x.get('hhldCnt') or 0), int(x.get('fmlyCnt') or 0)
    if h or f:
        return h or f
    main, etc = x.get('mainPurpsCdNm') or '', x.get('etcPurps') or ''
    return 1 if main == '단독주택' or ('근린생활' in main and '주택' in etc) else 0


def core(name):
    """'창원 롯데캐슬 포레스트 1단지 아파트' → '창원롯데캐슬포레스트1'처럼 이름 비교에 방해되는 말을 뺀다."""
    return re.sub(r'아파트|APT|단지', '', fp.norm(name or ''))


def city_of(tokens):
    """주소 낱말 목록에서 시(창원은 구)를 고른다. K-apt 지번주소는 '창원의창구'처럼 붙여 쓴다."""
    t = tokens[1]
    if t == '창원시':
        return tokens[2]
    return t[2:] if t.startswith('창원') and t.endswith('구') else t


def apt_keys(apts):
    """주소 열쇠 → K-apt 단지명"""
    keys = {}
    for a in apts:
        road = fp.road(a.get('doroJuso'))
        if road:
            keys[('r', city_of(a['doroJuso'].split()), road)] = a['kaptName']
        t = (a.get('kaptAddr') or '').split()
        m = re.search(r'(\S+(?:동|리|가))\s+(?:산\s*)?(\d+)(?:-(\d+))?(?=\s|$)', a.get('kaptAddr') or '')
        if m and len(t) > 2:
            keys[('j', city_of(t), m.group(1), int(m.group(2)), int(m.group(3) or 0))] = a['kaptName']
    return keys


def similar(a, b):
    """이름 닮음: 한쪽이 다른 쪽을 품으면 1.0, 아니면 difflib 비율. 세 글자 미만이면 0"""
    if len(a) < 3 or len(b) < 3:
        return 0
    return 1.0 if a in b or b in a else difflib.SequenceMatcher(None, a, b).ratio()


def bld_keys(x, dong):
    t = (x.get('platPlc') or '').split()
    out = [('j', city_of(t), dong, int(x.get('bun') or 0), int(x.get('ji') or 0))] if len(t) > 2 else []
    road = fp.road(x.get('newPlatPlc'))
    if road:
        out.append(('r', city_of(x['newPlatPlc'].split()), road))
    return out


GEOCODE = 'https://maps.apigw.ntruss.com/map-geocode/v2/geocode'


def addr_of(x):
    """'경상남도 창원시 성산구 중앙대로 123 (상남동)' → 괄호 앞 도로명주소. 도로명주소가 없으면 None"""
    a = (x.get('newPlatPlc') or '').split('(')[0].strip()
    return a if fp.road(a) else None


def geocode(ids, addr):
    """Maps Geocoding으로 도로명주소의 경위도. 결과의 길 이름+건물번호가 같을 때만 받고, 아니면 None.
    429·5xx는 잠시 쉬고 다시 부르며, 키 오류 등 다른 오류는 RuntimeError로 알린다."""
    req = urllib.request.Request(GEOCODE + '?' + urllib.parse.urlencode({'query': addr}),
                                 headers={'X-NCP-APIGW-API-KEY-ID': ids[0], 'X-NCP-APIGW-API-KEY': ids[1]})
    for wait in (2, 10, 30, 60, None):
        try:
            got = json.loads(urllib.request.urlopen(req, timeout=30).read()).get('addresses') or []
            want = fp.road(addr)
            hit = next((it for it in got if fp.road(it.get('roadAddress')) == want), None)
            return hit and [round(float(hit['x']), 6), round(float(hit['y']), 6)]
        except urllib.error.HTTPError as e:
            err = f'HTTP {e.code} ' + e.read()[:200].decode('utf-8', 'replace')
            if e.code != 429 and e.code < 500:
                break
        except (urllib.error.URLError, TimeoutError) as e:
            err = str(e)
        if wait:
            time.sleep(wait)
    raise RuntimeError('Geocoding 실패: ' + err)


def fill(cache, cache_path, todo):
    """todo 주소를 WORKERS개씩 나란히 지오코딩해 cache에 넣고 SAVE_EVERY개마다 저장한다. 오류로 멈춰도 받은 데까지 남는다."""
    ids = fp.clipboard_keys()
    try:
        with ThreadPoolExecutor(WORKERS) as pool:
            for i, (addr, hit) in enumerate(zip(todo, pool.map(lambda a: geocode(ids, a), todo)), 1):
                cache[addr] = hit
                if i % SAVE_EVERY == 0 or i == len(todo):
                    json.dump(cache, open(cache_path, 'w', encoding='utf-8'), ensure_ascii=False)
                    print(f'{i:,}/{len(todo):,} 지오코딩 (찾음 {sum(1 for v in cache.values() if v):,})', flush=True)
    finally:
        json.dump(cache, open(cache_path, 'w', encoding='utf-8'), ensure_ascii=False)


def main(src, apt_src):
    apts = [a for a in json.load(open(apt_src, encoding='utf-8')) if a.get('kaptdaCnt') and a.get('doroJuso')]
    akeys = apt_keys(apts)
    blds, apt_cnt, near_cnt = [], 0, 0
    used = defaultdict(int)   # 단지명 → 이미 뺀 세대
    for line in open(src, encoding='utf-8'):
        d = json.loads(line)
        dong = d['name'].split()[-1]
        for x in d['items']:
            if x.get('mainAtchGbCdNm') == '부속건축물' or not count(x):
                continue
            hit = next((akeys[k] for k in bld_keys(x, dong) if k in akeys), None)
            if hit:
                apt_cnt += count(x)
                used[hit] += count(x)
                continue
            name = core(x.get('bldNm')) if x.get('mainPurpsCdNm') == '공동주택' else ''
            blds.append({'code': d['code'], 'bun': int(x.get('bun') or 0), 'n': count(x), 'addr': addr_of(x), 'name': name})
    cache_path = src + '.geo.json'
    cache = json.load(open(cache_path, encoding='utf-8')) if os.path.exists(cache_path) else {}
    if '--geocode' in sys.argv:
        todo = sorted({b['addr'] for b in blds if b['addr'] and b['addr'] not in cache})
        rest = sys.argv[sys.argv.index('--geocode') + 1:]
        fill(cache, cache_path, todo[:int(rest[0])] if rest else todo)
    for b in blds:
        b['xy'] = cache.get(b['addr'])
    # 주소가 달라 못 뺀 K-apt 단지 건물: apt.json 단지와 이름이 닮고 NEAR_APT 안에 있으면, 가장 닮은 단지에 붙인다.
    # 단지마다 닮은 순·가까운 순으로, 주소로 뺀 세대와 합쳐 단지 세대수의 FILL배를 넘지 않을 만큼만 뺀다
    rows = json.loads((dataio.ROOT / 'apt.json').read_text(encoding='utf-8'))['a']
    cap = defaultdict(int)
    for r in rows:
        cap[r[0]] += r[1]
    pick = defaultdict(list)
    for i, b in enumerate(blds):
        if not (b['xy'] and b['name']):
            continue
        best = max(((similar(core(r[0]), b['name']), -fp.meters(b['xy'][0], b['xy'][1], r[2], r[3]), r[0]) for r in rows
                    if fp.meters(b['xy'][0], b['xy'][1], r[2], r[3]) < NEAR_APT), default=None)
        if best and best[0] >= SIMILAR:
            pick[best[2]].append((-best[0], -best[1], i))
    drop = set()
    for name, cands in pick.items():
        for _, _, i in sorted(cands):
            if used[name] < cap[name] and used[name] + blds[i]['n'] <= cap[name] * FILL:
                used[name] += blds[i]['n']
                apt_cnt += blds[i]['n']
                near_cnt += blds[i]['n']
                drop.add(i)
    blds = [b for i, b in enumerate(blds) if i not in drop]
    # 좌표 없는 건물: 같은 법정동에서 번지가 가장 가까운, 좌표 있는 건물의 좌표를 빌린다
    known = defaultdict(list)
    for b in blds:
        if b['xy']:
            known[b['code']].append((b['bun'], b['xy']))
    for v in known.values():
        v.sort()
    lent = lost = 0
    for b in blds:
        if b['xy']:
            continue
        v = known.get(b['code'], [])
        i = bisect.bisect_left(v, (b['bun'],))
        near = min((v[j] for j in (i - 1, i) if 0 <= j < len(v)), key=lambda q: abs(q[0] - b['bun']), default=None)
        if near and abs(near[0] - b['bun']) <= MAX_GAP:
            b['xy'], lent = near[1], lent + b['n']
        else:
            lost += b['n']
    cells = defaultdict(lambda: [0.0, 0.0, 0])
    for b in blds:
        if b['xy']:
            lon, lat = b['xy']
            c = cells[(math.floor(lon / CELL), math.floor(lat / CELL))]
            c[0] += lon * b['n']; c[1] += lat * b['n']; c[2] += b['n']
    rows = [[round(c[0] / c[2], 5), round(c[1] / c[2], 5), c[2]] for c in cells.values()]
    out = dataio.ROOT / 'house.json'
    basis = date.fromtimestamp(os.path.getmtime(src)).isoformat()
    out.write_text(json.dumps({'basis': basis, 'cell': CELL, 'h': sorted(rows)}, separators=(',', ':')) + '\n', encoding='utf-8')
    dataio.write_version()
    total = sum(r[2] for r in rows)
    print(f'K-apt 단지 건물로 뺀 세대 {apt_cnt:,}(이름·거리로 뺀 {near_cnt:,}) / 넣은 세대 {total:,}(번지로 좌표를 빌린 {lent:,}) / 좌표 없어 뺀 {lost:,}')
    print(f'격자 {len(rows):,}칸: {out}')


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
