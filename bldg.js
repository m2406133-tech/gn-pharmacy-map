/* 메디컬 빌딩: 의원이 여러 곳 모인 건물을 찾는 순수 함수. 화면을 건드리지 않아 node로 시험한다(tests/bldg.test.js).
   index.html은 <script src="bldg.js">로 읽어 전역 Bldg로 쓰고, 지도에 건물 테두리와 이름표로 그린다.
   건물은 심평원 주소의 도로명주소(쉼표·괄호 앞)로 가른다. 상가(상권)정보는 7개 시 의원의 절반도 담고 있지 않아서
   건물을 가르는 데 쓰지 않고, 건물 이름(bldg.json, tools/build_bldg.py)에만 쓴다 */
(function (root) {
  const addrKey = a => (a || '').split(/[,(]/)[0].replace(/\s/g, '');

  // clinics는 주소 a가 있는 객체 목록이다. 의원이 min곳 이상인 주소를 의원이 많은 순으로 돌려준다. 결과의 c에는 받은 객체를 그대로 넣는다
  function medicalBuildings(clinics, names, min) {
    const by = new Map();
    clinics.forEach(x => {
      const k = addrKey(x.a);
      if (!by.has(k)) by.set(k, { key: k, name: names[k] || '', c: [] });
      by.get(k).c.push(x);
    });
    return [...by.values()].filter(b => b.c.length >= min).sort((a, b) => b.c.length - a.c.length);
  }

  const Bldg = { addrKey, medicalBuildings };
  if (typeof module === 'object' && module.exports) module.exports = Bldg;
  else root.Bldg = Bldg;
})(this);
