"""심평원 '전국 병의원 및 약국 현황' 엑셀에서 중소병원과 로컬 의원·약국을 뽑아 local.json을 만든다.

    python tools/build_local.py "<엑셀 폴더>" 2026-06-30 ["<지방행정 인허가 약국 CSV 또는 ZIP>"]

- 중소병원: 7개 시의 병원·종합병원 중 index.html의 병원권 28곳(의과전문의 15명 이상)에 들지 않은 곳.
  요양·정신·한방·치과병원은 넣지 않는다.
- 로컬 의원: 7개 시의 의과 의원(종별 '의원'). index.html의 병원권 28곳에 든 의원은 뺀다.
- 로컬 약국: 7개 시의 약국 중 병원권 186곳(이름과 좌표 50m로 대조)을 뺀 나머지.
  병원 500m 안인데 186곳에 없는 약국은 병원권 기준일 전에 문을 닫은 것으로 보고 뺀다.
- id는 암호화요양기호의 해시 앞 8자리다. 다시 빌드해도 같은 기관은 같은 id라서 메모가 그대로 붙는다.
- 인허가 약국 파일(행정안전부 전국약국표준데이터)을 주면 약국영업면적(㎡)을 이름과 도로명주소로 맞춰 붙인다.
  로컬 약국은 ar, 병원권 약국은 hp({ 약국 id: 면적 })에 넣는다. 창고형약국 판정에 쓴다.
  심평원 기준일 뒤에 문을 연 창고형약국은 인허가 자료로 로컬 약국에 더한다(lic: 1, id는 관리번호의 해시).
표준 라이브러리만 쓴다.
"""
import csv, hashlib, io, json, math, re, sys, zipfile
from datetime import date, timedelta
from pathlib import Path
import xml.etree.ElementTree as ET

NS = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
REGIONS = ['창원', '진주', '김해', '양산', '거제', '사천', '통영']
ROOT = Path(__file__).resolve().parent.parent


def rows(path):
    """첫 시트를 {머리글: 값} 행으로 읽는다."""
    z = zipfile.ZipFile(path)
    ss = []
    if 'xl/sharedStrings.xml' in z.namelist():
        for _, el in ET.iterparse(z.open('xl/sharedStrings.xml')):
            if el.tag == NS + 'si':
                ss.append(''.join(t.text or '' for t in el.iter(NS + 't')))
                el.clear()
    sheet = sorted(n for n in z.namelist() if n.startswith('xl/worksheets/sheet'))[0]
    head = None
    for _, el in ET.iterparse(z.open(sheet)):
        if el.tag != NS + 'row':
            continue
        row = {}
        for c in el.findall(NS + 'c'):
            col = re.match(r'[A-Z]+', c.get('r')).group()
            v = c.find(NS + 'v')
            if c.get('t') == 's' and v is not None:
                row[col] = ss[int(v.text)]
            elif c.get('t') == 'inlineStr':
                row[col] = ''.join(x.text or '' for x in c.iter(NS + 't'))
            else:
                row[col] = v.text if v is not None else None
        el.clear()
        if head is None:
            head = row
        else:
            yield {name: row.get(col) for col, name in head.items()}


def find(folder, pattern):
    hits = sorted(Path(folder).glob(pattern))
    if not hits:
        sys.exit(f'{folder}에서 {pattern} 파일을 찾지 못했습니다')
    return hits[0]


def region(sgg):
    return next((r for r in REGIONS if (sgg or '').startswith(r)), None)


def opened(v):
    """개설일자는 엑셀 일련번호(30808) 또는 20200210 형식이다."""
    if not v:
        return ''
    v = v.split('.')[0]
    if len(v) == 8:
        return f'{v[:4]}-{v[4:6]}-{v[6:]}'
    return (date(1899, 12, 30) + timedelta(days=int(v))).isoformat()


def gap(a, b):
    k = math.pi / 180
    x = (b['x'] - a['x']) * k * math.cos((a['y'] + b['y']) / 2 * k)
    y = (b['y'] - a['y']) * k
    return 6371000 * math.hypot(x, y)


squash = lambda s: re.sub(r'\s', '', s or '')
addr_key = lambda a: squash(re.split(r'[,(]', a)[0])   # '경상남도 창원시 성산구 중앙대로 123'까지
city = lambda a: ' '.join(a.split()[:2])


def num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def licenses(path):
    """인허가 약국 파일에서 영업 중인 경남 약국을 읽는다. 좌표는 EPSG:5174(중부원점 TM) 미터 값 그대로 둔다."""
    if str(path).endswith('.zip'):
        z = zipfile.ZipFile(path)
        raw = z.read(z.namelist()[0])
    else:
        raw = Path(path).read_bytes()
    try:
        text = raw.decode('utf-8-sig')
    except UnicodeDecodeError:
        text = raw.decode('cp949')
    out = []
    for r in csv.DictReader(io.StringIO(text)):
        # 예전 LOCALDATA 파일과 지금 공공데이터포털 파일은 열 이름이 조금씩 다르다
        addr = r.get('도로명전체주소') or r.get('도로명주소') or r.get('소재지전체주소') or r.get('지번주소') or ''
        if not addr.startswith('경상남도') or r.get('영업상태명') != '영업/정상':
            continue
        out.append({'no': r['관리번호'], 'n': r['사업장명'], 'a': addr, 'o': r['인허가일자'],
                    't': r.get('전화번호') or r.get('소재지전화') or '', 'ar': num(r.get('약국영업면적')) or 0,
                    'X': num(r.get('좌표정보(X)') or r.get('좌표정보(x)')), 'Y': num(r.get('좌표정보(Y)') or r.get('좌표정보(y)'))})
    return out


def license_of(p, by_key, by_name):
    """이름과 도로명주소가 같은 곳, 없으면 같은 시에 이름이 하나뿐인 곳."""
    lic = by_key.get((squash(p['n']), addr_key(p['a'])))
    if lic is None:
        same_name = by_name.get((squash(p['n']), city(p['a'])), [])
        lic = same_name[0] if len(same_name) == 1 else None
    return lic


def det3(m):
    return (m[0][0] * (m[1][1] * m[2][2] - m[1][2] * m[2][1]) - m[0][1] * (m[1][0] * m[2][2] - m[1][2] * m[2][0])
            + m[0][2] * (m[1][0] * m[2][1] - m[1][1] * m[2][0]))


def to_lonlat(pairs, X, Y, k=12):
    """EPSG:5174 좌표를 경위도로 바꾼다. 두 자료에 모두 있는 약국 중 가장 가까운 k곳으로 국소 선형식
    (값 = c0 + c1·dX + c2·dY)을 최소제곱으로 맞추고, 그 자리의 값 c0을 쓴다. 측지 변환식과 원점 보정을 직접 쓰지 않아도 된다."""
    near = sorted(pairs, key=lambda q: (q[0] - X) ** 2 + (q[1] - Y) ** 2)[:k]
    rows_ = [(1, q[0] - X, q[1] - Y) for q in near]
    m = [[sum(a[i] * a[j] for a in rows_) for j in range(3)] for i in range(3)]
    d = det3(m)
    out = []
    for col in (2, 3):
        v = [sum(a[i] * q[col] for a, q in zip(rows_, near)) for i in range(3)]
        out.append(det3([[v[i]] + m[i][1:] for i in range(3)]) / d)   # 크라메르 공식으로 c0만 구한다
    return out


def place_of(addr):
    """'경상남도 창원시 성산구 중앙대로 123, ... (중앙동)'에서 심평원 형식의 시군구('창원성산구')와 읍면동을 뽑는다."""
    t = addr.split()
    sgg = '창원' + t[2] if t[1] == '창원시' and t[2].endswith('구') else t[1]
    paren = re.search(r'\(([^,)]+)', addr)
    emd = paren.group(1) if paren else (t[2] if re.search(r'[읍면동]$', t[2]) else '')
    return sgg, emd


def base(r):
    return {
        'id': hashlib.sha1(r['암호화요양기호'].encode()).hexdigest()[:8],
        'n': r['요양기관명'], 'sgg': r['시군구코드명'], 'emd': r['읍면동'] or '', 'r': region(r['시군구코드명']),
        'a': r['주소'] or '', 't': r['전화번호'] or '', 'o': opened(r['개설일자']),
        'x': round(float(r['좌표(X)']), 6), 'y': round(float(r['좌표(Y)']), 6),
    }


def main(folder, basis, license_file=None):
    html = (ROOT / 'index.html').read_text(encoding='utf-8')
    data = json.loads(re.search(r'const DATA = (\{.*?\});\n', html).group(1))
    hosp, hph = data['hosp'], data['ph']
    same = lambda a, b: a['n'] == b['n'] and gap(a, b) < 50

    inst = [r for r in rows(find(folder, '1.병원정보서비스*.xlsx'))
            if r['시도코드명'] == '경남' and r['종별코드명'] in ('의원', '병원', '종합병원') and region(r['시군구코드명']) and r['좌표(X)']]
    clinics, mids, in28 = [], [], 0
    for r in inst:
        c = base(r)
        # 병원권은 다른 분기 자료로 만들어서 병원 이름이 조금 다를 수 있으므로, 병원끼리는 30m 안이면 같은 기관으로 본다
        hospital = r['종별코드명'] != '의원'
        if any(same(c, h) or (hospital and gap(c, h) < 30) for h in hosp):
            in28 += 1
            continue
        c.update(d=int(float(r['총의사수'] or 0)), sp=int(float(r['의과전문의 인원수'] or 0)))
        if r['종별코드명'] == '의원':
            clinics.append(c)
        else:
            mids.append(dict(c, typ=r['종별코드명']))

    pharm = [r for r in rows(find(folder, '2.약국정보서비스*.xlsx'))
             if r['시도코드명'] == '경남' and region(r['시군구코드명']) and r['좌표(X)']]
    keys = {r['암호화요양기호'] for r in pharm}
    staff = {}
    for r in rows(find(folder, '12.*기타인력정보*.xlsx')):
        if r['암호화요양기호'] in keys and r['기타인력코드명'] in ('약사', '한약사'):
            staff.setdefault(r['암호화요양기호'], {})[r['기타인력코드명']] = int(float(r['기타인력수'] or 0))
    local, matched, closed = [], 0, 0
    for r in pharm:
        p = base(r)
        if any(same(p, q) for q in hph):
            matched += 1
            continue
        if any(gap(p, h) <= 500 for h in hosp):
            closed += 1
            continue
        s = staff.get(r['암호화요양기호'], {})
        p.update(ps=s.get('약사', 0), hs=s.get('한약사', 0))
        local.append(p)

    hp, added = {}, []
    if license_file:
        lics = licenses(license_file)
        by_key, by_name = {}, {}
        for lic in lics:
            by_key[(squash(lic['n']), addr_key(lic['a']))] = lic
            by_name.setdefault((squash(lic['n']), city(lic['a'])), []).append(lic)
        used, pairs = set(), []
        for group in (hph, local):
            for p in group:
                lic = license_of(p, by_key, by_name)
                if lic is None:
                    continue
                used.add(lic['no'])
                if lic['ar'] > 0:
                    if group is local:
                        p['ar'] = round(lic['ar'], 1)
                    else:
                        hp[p['id']] = round(lic['ar'], 1)
                if lic['X'] is not None:
                    pairs.append((lic['X'], lic['Y'], p['x'], p['y']))
        print(f"약국영업면적: 로컬 약국 {sum('ar' in p for p in local)}/{len(local)}곳, 병원권 약국 {len(hp)}/{len(hph)}곳 대조")

        # 좌표 변환은 각 쌍을 빼고 나머지로 맞춰 본 오차로 검증하고, 100m 넘게 어긋나는 쌍(잘못 대조된 약국)은 버린다
        err = [gap({'x': q[2], 'y': q[3]}, dict(zip('xy', to_lonlat(pairs[:i] + pairs[i + 1:], q[0], q[1]))))
               for i, q in enumerate(pairs)]
        pairs = [q for q, e in zip(pairs, err) if e < 100]
        ok = sorted(e for e in err if e < 100)
        print(f'인허가 좌표 변환 검증: {len(ok)}쌍, 오차 중앙값 {ok[len(ok) // 2]:.1f}m, 95% {ok[int(len(ok) * .95)]:.1f}m')

        # 심평원 자료에 아직 없는 창고형약국(기준은 index.html의 WH_SINCE·WH_AREA와 같다)은 인허가 자료로 로컬 약국에 더한다
        for lic in lics:
            sgg, emd = place_of(lic['a'])
            if lic['no'] in used or lic['X'] is None or not region(sgg) or lic['o'] < '2025-01-01' or lic['ar'] < 165:
                continue
            lon, lat = to_lonlat(pairs, lic['X'], lic['Y'])
            p = {'id': hashlib.sha1(('lic:' + lic['no']).encode()).hexdigest()[:8], 'n': lic['n'], 'sgg': sgg, 'emd': emd,
                 'r': region(sgg), 'a': lic['a'], 't': re.sub(r'^(0\d{2})(\d{3,4})(\d{4})$', r'\1-\2-\3', lic['t']),
                 'o': lic['o'], 'x': round(lon, 6), 'y': round(lat, 6), 'ps': 0, 'hs': 0, 'ar': round(lic['ar'], 1), 'lic': 1}
            # 주소 표기가 달라 대조되지 않았을 뿐 이미 있는 약국은 뺀다. 상가 건물에는 약국이 여럿이라 좌표만으로는 판단하지 않는다
            if any(squash(q['n']) == squash(p['n']) and gap(p, q) < 50 for q in hph + local):
                continue
            added.append(p)
        local += added
        print('인허가 자료로 더한 창고형약국: ' + (', '.join(f"{p['n']}({p['o']}, {p['ar']}㎡)" for p in added) or '없음'))

    allph = hph + local
    for c in clinics + mids:
        c['p100'] = sum(gap(c, p) <= 100 for p in allph)
    for p in local:
        p['c100'] = sum(gap(p, c) <= 100 for c in clinics)
    ids = [x['id'] for x in mids + clinics + local]
    assert len(ids) == len(set(ids)), 'id가 겹칩니다'

    data = {'basis': basis, 'm': mids, 'c': clinics, 'p': local}
    if license_file:
        data['hp'] = hp

    out = ROOT / 'local.json'
    out.write_text(json.dumps(data, ensure_ascii=False, separators=(',', ':')) + '\n', encoding='utf-8')
    print(f'중소병원 {len(mids)}곳, 의원 {len(clinics)}곳, 로컬 약국 {len(local)}곳 (병원권 28곳과 대조된 기관 {in28}곳, '
          f'병원권 약국과 대조 {matched}곳, 병원 500m 안 미등재 {closed}곳 제외)')
    big = [f"{x['n']}({x['sp']}명)" for x in mids if x['sp'] >= 15]
    if big:
        print('주의: 병원권 기준(의과전문의 15명 이상)인데 병원권에 없는 곳 ' + ', '.join(big))
    print(f'{out} {out.stat().st_size // 1024}KB')


if __name__ == '__main__':
    main(*sys.argv[1:4])
