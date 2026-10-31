"""국립중앙의료원 '전국 약국 정보 조회 서비스'(공공데이터포털 15000576)에서 경남 약국의 요일별 영업시간을 받아 JSON으로 저장한다.

    python tools/fetch_hours.py "<저장할 JSON 경로>"

- 서비스키는 공공데이터포털의 일반 인증키(Decoding)를 복사해 두고 실행하면 클립보드에서 읽는다.
  함께 쓰는 PC라서 읽자마자 클립보드를 비우고, 어디에도 저장하지 않는다. (앱 터미널에서는 getpass 입력이 먹지 않았다)
- 받은 파일은 저장소 밖에 두고 build_local.py의 네 번째 인자로 준다.
표준 라이브러리만 쓴다.
"""
import json, subprocess, sys, urllib.error, urllib.parse, urllib.request
import xml.etree.ElementTree as ET

URL = 'https://apis.data.go.kr/B552657/ErmctInsttInfoInqireService/getParmacyListInfoInqire'
ROWS = 500


def page(key, no):
    q = urllib.parse.urlencode({'serviceKey': key, 'Q0': '경상남도', 'pageNo': no, 'numOfRows': ROWS})
    try:
        raw = urllib.request.urlopen(f'{URL}?{q}', timeout=60).read()
    except urllib.error.HTTPError as e:
        # 키가 틀렸거나, 활용신청 직후 키가 아직 등록되지 않았으면(보통 1시간 안팎) 403이 온다
        sys.exit(f'HTTP {e.code}: ' + e.read()[:300].decode('utf-8', 'replace'))
    try:
        root = ET.fromstring(raw)
    except ET.ParseError:
        sys.exit('응답을 읽지 못했습니다: ' + raw[:300].decode('utf-8', 'replace'))
    code = root.findtext('.//resultCode') or root.findtext('.//returnReasonCode')
    if code not in ('00', '0000'):
        # 키가 틀리거나 아직 등록되지 않았으면 OpenAPI_ServiceResponse 형식으로 사유가 온다
        sys.exit(f"오류 {code}: {root.findtext('.//resultMsg') or root.findtext('.//returnAuthMsg')}")
    items = [{c.tag: (c.text or '').strip() for c in it} for it in root.iter('item')]
    return items, int(root.findtext('.//totalCount') or 0)


def clipboard_key():
    key = subprocess.run(['powershell', '-NoProfile', '-Command', 'Get-Clipboard -Raw'],
                         capture_output=True, text=True).stdout.strip()
    if len(key) < 20 or any(c.isspace() for c in key):
        sys.exit('클립보드에 서비스키가 없습니다. 마이페이지에서 일반 인증키(Decoding)를 복사한 뒤 다시 실행하세요.')
    subprocess.run(['clip'], input=b'')
    return key


def main(out):
    key = urllib.parse.unquote(clipboard_key())
    items, total = page(key, 1)
    no = 1
    while len(items) < total:
        no += 1
        more, _ = page(key, no)
        if not more:
            break
        items += more
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(items, f, ensure_ascii=False)
    print(f'경남 약국 {len(items)}/{total}곳 저장: {out}')


if __name__ == '__main__':
    main(sys.argv[1])
