"""심평원 '전국 병의원 및 약국 현황' 엑셀에서 중소병원과 로컬 의원·약국을 뽑아 local.json을 만든다.

    python tools/build_local.py "<엑셀 폴더>" 2026-06-30

- 중소병원: 7개 시의 병원·종합병원 중 index.html의 병원권 28곳(의과전문의 15명 이상)에 들지 않은 곳.
  요양·정신·한방·치과병원은 넣지 않는다.
- 로컬 의원: 7개 시의 의과 의원(종별 '의원'). index.html의 병원권 28곳에 든 의원은 뺀다.
- 로컬 약국: 7개 시의 약국 중 병원권 186곳(이름과 좌표 50m로 대조)을 뺀 나머지.
  병원 500m 안인데 186곳에 없는 약국은 병원권 기준일 전에 문을 닫은 것으로 보고 뺀다.
- id는 암호화요양기호의 해시 앞 8자리다. 다시 빌드해도 같은 기관은 같은 id라서 메모가 그대로 붙는다.
표준 라이브러리만 쓴다.
"""
import hashlib, json, math, re, sys, zipfile
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


def base(r):
    return {
        'id': hashlib.sha1(r['암호화요양기호'].encode()).hexdigest()[:8],
        'n': r['요양기관명'], 'sgg': r['시군구코드명'], 'emd': r['읍면동'] or '', 'r': region(r['시군구코드명']),
        'a': r['주소'] or '', 't': r['전화번호'] or '', 'o': opened(r['개설일자']),
        'x': round(float(r['좌표(X)']), 6), 'y': round(float(r['좌표(Y)']), 6),
    }


def main(folder, basis):
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

    allph = hph + local
    for c in clinics + mids:
        c['p100'] = sum(gap(c, p) <= 100 for p in allph)
    for p in local:
        p['c100'] = sum(gap(p, c) <= 100 for c in clinics)
    ids = [x['id'] for x in mids + clinics + local]
    assert len(ids) == len(set(ids)), 'id가 겹칩니다'

    out = ROOT / 'local.json'
    out.write_text(json.dumps({'basis': basis, 'm': mids, 'c': clinics, 'p': local}, ensure_ascii=False, separators=(',', ':')) + '\n',
                   encoding='utf-8')
    print(f'중소병원 {len(mids)}곳, 의원 {len(clinics)}곳, 로컬 약국 {len(local)}곳 (병원권 28곳과 대조된 기관 {in28}곳, '
          f'병원권 약국과 대조 {matched}곳, 병원 500m 안 미등재 {closed}곳 제외)')
    big = [f"{x['n']}({x['sp']}명)" for x in mids if x['sp'] >= 15]
    if big:
        print('주의: 병원권 기준(의과전문의 15명 이상)인데 병원권에 없는 곳 ' + ', '.join(big))
    print(f'{out} {out.stat().st_size // 1024}KB')


if __name__ == '__main__':
    main(*sys.argv[1:3])
