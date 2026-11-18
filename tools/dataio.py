"""local.json의 저장 형식(columns + 값 배열)과 version.json을 다루는 공용 모듈.

local.json은 m·c·p 목록의 행마다 키 이름을 되풀이하지 않도록, 목록별 columns에 키 순서를 한 번만 적고 행은 값만 배열로 둔다.
행에 없는 키는 null로 채우며(원본 값에는 null이 없다), 브라우저와 build_local·fetch_poi가 읽을 때 다시 객체로 되돌린다.
version.json은 local.json·poi.json·bldg.json·apt.json 내용의 해시를 담아, 페이지가 'local.json?v=해시'처럼 받아 브라우저 캐시를 안전하게 오래 쓰게 한다.
"""
import hashlib, json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LISTS = ('m', 'c', 'p')
VERSIONED = ('local', 'poi', 'bldg', 'apt')


def pack(data):
    """객체 목록을 columns + 값 배열로 바꾼 사본을 돌려준다."""
    out = {k: v for k, v in data.items() if k not in LISTS}
    out['columns'] = {}
    for g in LISTS:
        cols = []
        for r in data[g]:
            cols += [k for k in r if k not in cols]
        out['columns'][g] = cols
        out[g] = [[r.get(k) for k in cols] for r in data[g]]
    return out


def unpack(packed):
    """pack의 결과를 원래의 객체 목록으로 되돌린다."""
    data = {k: v for k, v in packed.items() if k != 'columns'}
    for g in LISTS:
        cols = packed['columns'][g]
        data[g] = [{k: v for k, v in zip(cols, row) if v is not None} for row in packed[g]]
    return data


def load_local(path=None):
    """local.json을 읽어 객체 목록 형태로 돌려준다."""
    return unpack(json.loads(Path(path or ROOT / 'local.json').read_text(encoding='utf-8')))


def write_local(data, path=None):
    """객체 목록 형태의 data를 columns + 값 배열로 저장하고 version.json을 갱신한다."""
    Path(path or ROOT / 'local.json').write_text(
        json.dumps(pack(data), ensure_ascii=False, separators=(',', ':')) + '\n', encoding='utf-8')
    write_version()


def write_version():
    """local.json·poi.json·bldg.json·apt.json의 내용 해시를 version.json에 적는다. 없는 파일은 건너뛴다."""
    ver = {}
    for name in VERSIONED:
        f = ROOT / f'{name}.json'
        if f.exists():
            ver[name] = hashlib.sha1(f.read_bytes()).hexdigest()[:10]
    (ROOT / 'version.json').write_text(json.dumps(ver, separators=(',', ':')) + '\n', encoding='utf-8')
    return ver
