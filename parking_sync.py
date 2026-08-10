import requests
import json
import urllib.parse
import os

# ==========================================
# 1. 설정 정보 (인증키 및 노션 토큰/DB ID 완료)
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
# 2. 노션 데이터 중복 체크
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
# 4. 공공데이터 API 수집
# ==========================================
def fetch_parking_data():
    decoded_key = urllib.parse.unquote(PUBLIC_DATA_KEY)
    base_url = "http://api.data.go.kr/openapi/tn_pubr_public_prkplce_api"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }

    params = {
        'serviceKey': decoded_key,
        'type': 'json',
        'pageNo': '1',
        'numOfRows': '200'
    }

    try:
        print("📡 전국 공영주차장 공공데이터 API 요청 중...")
        res = requests.get(base_url, params=params, headers=headers, timeout=20)
        print(f"📡 API 응답 코드: {res.status_code}")
        
        if res.status_code == 200:
            try:
                data = res.json()
                items = data.get('response', {}).get('body', {}).get('items', [])
                print(f"📊 수집된 주차장 건수: {len(items)}건")

                for item in items:
                    name = item.get('prkplceNm', '이름없음')
                    rd_addr = item.get('rdnmadr', '')
                    ln_addr = item.get('lnmadr', '')
                    address = rd_addr if rd_addr else (ln_addr if ln_addr else '주소미상')
                    
                    addr_parts = address.split()
                    region = f"{addr_parts[0]} {addr_parts[1]}" if len(addr_parts) > 1 else (addr_parts[0] if addr_parts else '기타')
                    
                    capacity_raw = item.get('prkplceSe', '0')
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
                print(f"응답 내용: {res.text[:200]}")
        else:
            print(f"❌ API 실패 응답: {res.text[:200]}")
    except Exception as e:
        print(f"❌ 주차장 데이터 수집 에러: {e}")

fetch_parking_data()
