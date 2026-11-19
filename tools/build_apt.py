"""fetch_apt.py로 받은 아파트 단지(K-apt)에 네이버 검색 API로 좌표를 붙여 apt.json을 만든다.

    python tools/build_apt.py "<fetch_apt.py로 받은 JSON>" [--retry | --geocode]

- K-apt 기본정보에는 좌표가 없다. 단지명으로 네이버 지역 검색을 하고, 검색 결과의 도로명주소(길 이름+건물번호)가
  K-apt 도로명주소(doroJuso)와 같거나 지번(동·리+번지)이 K-apt 지번주소(kaptAddr)와 같은 곳을 고른다.
  '시 단지명' → '시군구 동 단지명' → 도로명주소 순서로 찾고, 셋 다 아니면 뺀다. --retry를 주면 전에 못 찾은 단지도 다시 찾고,
  이때는 주소가 달라도 같은 동·리·읍·면에 이름이 닮은(LOOSE) 결과를 받는다.
- --geocode를 주면 검색 대신 네이버 클라우드 Maps Geocoding으로 아직 좌표가 없는 단지의 도로명주소(없으면 지번)를
  좌표로 바꾸고, 결과의 도로명주소나 지번이 K-apt와 같을 때만 받는다. 키는 Maps Application의 Client ID와 Secret이다.
- 키는 fetch_poi.py처럼 네이버 클라우드 Client ID와 Client Secret을 공백으로 이어 클립보드에 복사해 두면 읽는다.
- 조회 결과는 입력 파일 옆 .cache.json에 쌓아 두어, 중간에 멈춰도 같은 명령으로 이어 받는다.
- apt.json은 { basis: 받은 날, a: [[단지명, 세대수, 경도, 위도], …] }이다. 세대수는 kaptdaCnt다.
표준 라이브러리만 쓴다.
"""
import difflib, json, os, re, sys, time, urllib.error, urllib.parse, urllib.request
from datetime import date
import dataio
import fetch_poi as fp


LOT = re.compile(r'([가-힣0-9]+(?:동|리|가))\s+(\d+(?:-\d+)?)\b')


def lot(addr):
    """지번 주소에서 '상남동45-1'처럼 동·리 이름과 번지를 뽑는다. 번지가 없으면 None."""
    m = LOT.findall(addr or '')
    return ''.join(m[-1]) if m else None


def pick(a, items):
    want, lot_want = fp.road(a.get('doroJuso')), lot(a.get('kaptAddr'))
    for it in items:
        if (want and fp.road(it.get('roadAddress')) == want) or (lot_want and lot(it.get('address')) == lot_want):
            return fp.lonlat(it)
    return None


LOOSE = 0.6   # 주소가 맞지 않을 때, 같은 동·읍면 안에서 이름만으로 받아들이는 닮음 기준


def core(name):
    """'성원아파트2단지(임대)' → '성원2단지'처럼 비교에 방해되는 말을 뺀다."""
    return re.sub(r'아파트|APT|apt', '', fp.norm(name))


def loose(a, items):
    """주소가 다른 결과 중, 지번주소에 같은 동·리·읍·면이 들어 있고 이름이 LOOSE 이상 닮은 곳. 없으면 None"""
    towns = re.findall(r'(\S+(?:동|리|가|읍|면))\s', a.get('kaptAddr') or '')
    want, best = core(a['kaptName']), None
    for it in items:
        if not towns or towns[-1] not in (it.get('address') or '').split():
            continue
        sim = difflib.SequenceMatcher(None, want, core(it['title'])).ratio()
        if sim >= LOOSE and (not best or sim > best[0]):
            best = (sim, fp.lonlat(it), re.sub(r'<[^>]+>', '', it['title']))
    return best


def dong_query(a):
    """'경상남도 창원성산구 상남동 45-1 성원아파트2단지' → '창원성산구 상남동 성원아파트2단지'"""
    m = re.search(r'경상남도\s+(\S+)\s+(?:\S+[읍면]\s+)?(\S+(?:동|리|가))', a.get('kaptAddr') or '')
    return m and f'{m.group(1)} {m.group(2)} {a["kaptName"]}'


GEOCODE = ('https://maps.apigw.ntruss.com/map-geocode/v2/geocode',            # 새 주소
           'https://naveropenapi.apigw.ntruss.com/map-geocode/v2/geocode')    # 예전 주소


def geocode(ids, query):
    """Maps Geocoding 결과의 addresses 목록. 새 주소가 401·403·404면 예전 주소로 한 번 더 부른다."""
    q = urllib.parse.urlencode({'query': query})
    for url in GEOCODE:
        req = urllib.request.Request(f'{url}?{q}', headers={'X-NCP-APIGW-API-KEY-ID': ids[0], 'X-NCP-APIGW-API-KEY': ids[1]})
        try:
            return json.loads(urllib.request.urlopen(req, timeout=30).read()).get('addresses') or []
        except urllib.error.HTTPError as e:
            err = f'HTTP {e.code} ' + e.read()[:200].decode('utf-8', 'replace')
            if e.code not in (401, 403, 404):
                break
    sys.exit('Geocoding 실패: ' + err + ' (Maps Application에 Geocoding을 켰는지, Maps 키를 복사했는지 확인하세요)')


def geocode_one(ids, a):
    want, lot_want = fp.road(a['doroJuso']), lot(a.get('kaptAddr'))
    jibun = re.match(r'.*?\d+(?:-\d+)?(?=\s|$)', a.get('kaptAddr') or '')   # 지번주소에서 단지명 앞까지
    for q in (a['doroJuso'], jibun and jibun.group(0)):
        for it in (geocode(ids, q) if q else []):
            if (want and fp.road(it.get('roadAddress')) == want) or (lot_want and lot(it.get('jibunAddress')) == lot_want):
                return float(it['x']), float(it['y'])
        time.sleep(0.12)
    return None


def main(src):
    apts = [a for a in json.load(open(src, encoding='utf-8')) if a.get('kaptdaCnt') and a.get('doroJuso')]
    cache_path = src + '.cache.json'
    cache = json.load(open(cache_path, encoding='utf-8')) if os.path.exists(cache_path) else {}
    retry = '--retry' in sys.argv   # 전에 못 찾은 단지(캐시 값 null)도 다시 찾는다
    geo = '--geocode' in sys.argv   # 못 찾은 단지를 주소 지오코딩으로 찾는다
    todo = [a for a in apts if a['kaptCode'] not in cache or ((retry or geo) and not cache[a['kaptCode']])]
    ids = fp.clipboard_keys() if todo else None
    for i, a in enumerate(todo, 1):
        if geo:
            hit = geocode_one(ids, a)
            cache[a['kaptCode']] = hit and [round(hit[0], 6), round(hit[1], 6)]
            print(f"  {'찾음' if hit else '없음'} {a['kaptName']}", flush=True)
            continue
        city = ' '.join(a['doroJuso'].split()[1:3])   # '창원시 의창구' 또는 '진주시 진주대로'의 앞 두 낱말
        hit, seen = None, []
        for q in (f"{city} {a['kaptName']}", dong_query(a), a['doroJuso']):
            if hit is None and q:
                seen += fp.search(ids, q)
                hit = pick(a, seen[-5:])
                time.sleep(0.12)
        if hit is None and retry:   # 다시 찾을 때만: 주소가 다른 결과도 같은 동·읍면에 이름이 닮았으면 받는다
            m = loose(a, seen)
            if m:
                hit = m[1]
                print(f"  이름으로 찾음 {a['kaptName']} → {m[2]} ({m[0]:.2f})", flush=True)
        cache[a['kaptCode']] = hit and [round(hit[0], 6), round(hit[1], 6)]
        if i % 50 == 0 or i == len(todo):
            json.dump(cache, open(cache_path, 'w', encoding='utf-8'))
            print(f'{i}/{len(todo)} 조회', flush=True)
    json.dump(cache, open(cache_path, 'w', encoding='utf-8'))
    rows = [[a['kaptName'], int(a['kaptdaCnt']), *cache[a['kaptCode']]] for a in apts if cache.get(a['kaptCode'])]
    out = dataio.ROOT / 'apt.json'
    basis = date.fromtimestamp(os.path.getmtime(src)).isoformat()
    out.write_text(json.dumps({'basis': basis, 'a': rows}, ensure_ascii=False, separators=(',', ':')) + '\n', encoding='utf-8')
    dataio.write_version()
    miss = [a['kaptName'] for a in apts if not cache.get(a['kaptCode'])]
    print(f'단지 {len(apts)}곳 중 {len(rows)}곳 좌표 찾음, {sum(r[1] for r in rows):,}세대: {out}')
    if miss:
        print(f'못 찾은 {len(miss)}곳: ' + ', '.join(miss[:30]) + (' …' if len(miss) > 30 else ''))


if __name__ == '__main__':
    main(sys.argv[1])
