import requests
import json
import urllib.parse
import time
import os

# ==========================================
# 1. 설정 정보
# ==========================================
NOTION_TOKEN = "ntn_n9230455858ahP4EMhkrguf0ld3JV7xXfM2hA9FQ1Ywbzj"
PARKING_DATABASE_ID = "3b82262d943280079f7fec552cce02ae"
PUBLIC_DATA_KEY = "eee7f8f94d68563652f1330f65ec1ddb5e03a16c585a20159864fe8b1abc136f"

notion_headers = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28"
}

# ==========================================
# 2. 노션 중복 체크
# ==========================================
def check_duplicate(parking_name, address):
    url = f"https://api.notion.com/v1/databases/{PARKING_DATABASE_ID}/query"
    payload = {
        "filter": {
            "and": [
                {"property": "주차장명", "title": {"equals": parking_name}},
                {"property": "주소", "rich_text": {"equals": address}}
            ]
        }
    }
    try:
        res = requests.post(url, headers=notion_headers, json=payload, timeout=10)
        if res.status_code == 200:
            return len(res.json().get("results", [])) > 0
    except Exception:
        pass
    return False

# ==========================================
# 3. 노션 표에 주차장 데이터 등록
# ==========================================
def add_parking_to_notion(name, region, address, capacity, operating_days, fee_info, phone):
    if check_duplicate(name, address):
        print(f"⏩ [중복 스킵] {name} ({address})")
        return

    url = "https://api.notion.com/v1/pages"
    properties = {
        "주차장명": {"title": [{"text": {"content": name}}]},
        "지역": {"rich_text": [{"text": {"content": region}}]},
        "주소": {"rich_text": [{"text": {"content": address}}]},
        "주차구획수": {"number": capacity},
        "운영요일": {"rich_text": [{"text": {"content": operating_days}}]},
        "요금정보": {"rich_text": [{"text": {"content": fee_info}}]},
        "전화번호": {"rich_text": [{"text": {"content": phone}}]}
    }

    try:
        res = requests.post(url, headers=notion_headers, json={"parent": {"database_id": PARKING_DATABASE_ID}, "properties": properties}, timeout=10)
        if res.status_code == 200:
            print(f"✅ [주차장 등록 완료] {name} | 구획수: {capacity}대 | {region}")
        else:
            print(f"❌ 노션 등록 실패 ({res.status_code}): {res.text[:150]}")
    except Exception as e:
        print(f"❌ 노션 등록 에러: {e}")

# ==========================================
# 4. 공공데이터 API 수집 (다양한 JSON 응답 구조 호환)
# ==========================================
def fetch_parking_data():
    # URL 직접 조합으로 인증키 변형 방지
    decoded_key = urllib.parse.unquote(PUBLIC_DATA_KEY)
    encoded_key = urllib.parse.quote(decoded_key)
    
    request_url = f"https://api.data.go.kr/openapi/tn_pubr_prkplce_info_api?serviceKey={encoded_key}&type=json&pageNo=1&numOfRows=50"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }

    res = None
    for attempt in range(3):
        try:
            print(f"📡 API 요청 시도 ({attempt+1}/3)...")
            res = requests.get(request_url, headers=headers, timeout=30)
            if res.status_code == 200:
                break
            time.sleep(2)
        except Exception as e:
            print(f"⚠️ 요청 지연: {e}")
            time.sleep(2)

    if not res or res.status_code != 200:
        print(f"❌ API 접속 실패: {res.status_code if res else '응답 없음'}")
        return

    try:
        data = res.json()
        body = data.get('response', {}).get('body', {})
        total_count = body.get('totalCount', 0)
        print(f"📊 공공데이터 전체 주차장 수: {total_count}건")

        raw_items = body.get('items', [])
        items = []

        # JSON 응답 형태별 추출 (리스트 vs 딕셔너리 내 'item' 키)
        if isinstance(raw_items, list):
            items = raw_items
        elif isinstance(raw_items, dict):
            items = raw_items.get('item', [])
            if isinstance(items, dict):
                items = [items]

        print(f"📊 이번 회차 수집 대상: {len(items)}건")

        if len(items) == 0:
            print(f"🔍 원본 응답 확인: {res.text[:300]}")
            return

        for item in items:
            name = item.get('prkplceNm', '이름없음')
            rd_addr = item.get('rdnmadr', '')
            ln_addr = item.get('lnmadr', '')
            address = rd_addr if rd_addr else (ln_addr if ln_addr else '주소미상')
            
            addr_parts = address.split()
            region = f"{addr_parts[0]} {addr_parts[1]}" if len(addr_parts) > 1 else (addr_parts[0] if addr_parts else '기타')
            
            capacity_raw = item.get('prkplceCnt', item.get('prkplceSe', '0'))
            capacity = int(capacity_raw) if str(capacity_raw).isdigit() else 0
            
            operating_days = item.get('operDay', '연중무휴')
            fee_type = item.get('parkingchrgeInfo', '무료')
            basic_time = item.get('basicTime', '')
            basic_charge = item.get('basicCharge', '')
            
            fee_info = f"{fee_type} ({basic_time}분당 {basic_charge}원)" if basic_charge else fee_type
            phone = item.get('phoneNumber', '')

            add_parking_to_notion(name, region, address, capacity, operating_days, fee_info, phone)

    except Exception as parse_e:
        print(f"⚠️ 데이터 파싱 에러: {parse_e}")
        print(f"응답 본문 샘플: {res.text[:300]}")

fetch_parking_data()
