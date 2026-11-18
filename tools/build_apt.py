"""fetch_apt.py로 받은 아파트 단지(K-apt)에 네이버 검색 API로 좌표를 붙여 apt.json을 만든다.

    python tools/build_apt.py "<fetch_apt.py로 받은 JSON>"

- K-apt 기본정보에는 좌표가 없다. 단지명으로 네이버 지역 검색을 하고, 검색 결과의 도로명주소(길 이름+건물번호)가
  K-apt 도로명주소(doroJuso)와 같은 곳을 고른다. 이름으로 못 찾으면 도로명주소로 한 번 더 찾는다. 둘 다 아니면 뺀다.
- 키는 fetch_poi.py처럼 네이버 클라우드 Client ID와 Client Secret을 공백으로 이어 클립보드에 복사해 두면 읽는다.
- 조회 결과는 입력 파일 옆 .cache.json에 쌓아 두어, 중간에 멈춰도 같은 명령으로 이어 받는다.
- apt.json은 { basis: 받은 날, a: [[단지명, 세대수, 경도, 위도], …] }이다. 세대수는 kaptdaCnt다.
표준 라이브러리만 쓴다.
"""
import json, os, re, sys, time
from datetime import date
import dataio
import fetch_poi as fp


def pick(a, items):
    want = fp.road(a.get('doroJuso'))
    for it in items:
        if want and fp.road(it.get('roadAddress')) == want:
            return fp.lonlat(it)
    return None


def main(src):
    apts = [a for a in json.load(open(src, encoding='utf-8')) if a.get('kaptdaCnt') and a.get('doroJuso')]
    cache_path = src + '.cache.json'
    cache = json.load(open(cache_path, encoding='utf-8')) if os.path.exists(cache_path) else {}
    todo = [a for a in apts if a['kaptCode'] not in cache]
    ids = fp.clipboard_keys() if todo else None
    for i, a in enumerate(todo, 1):
        city = ' '.join(a['doroJuso'].split()[1:3])   # '창원시 의창구' 또는 '진주시 진주대로'의 앞 두 낱말
        hit = pick(a, fp.search(ids, f"{city} {a['kaptName']}"))
        if hit is None:
            time.sleep(0.12)
            hit = pick(a, fp.search(ids, a['doroJuso']))
        cache[a['kaptCode']] = hit and [round(hit[0], 6), round(hit[1], 6)]
        if i % 50 == 0 or i == len(todo):
            json.dump(cache, open(cache_path, 'w', encoding='utf-8'))
            print(f'{i}/{len(todo)} 조회', flush=True)
        time.sleep(0.12)
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
