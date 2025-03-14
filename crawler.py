import os
import time
import json
import pandas as pd
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from bs4 import BeautifulSoup
from webdriver_manager.chrome import ChromeDriverManager

# 기본 설정
BASE_URL = "https://map.naver.com/p/search/"
DATA_DIR = "data"
CONFIG_FILE = "search_config.json"
RESULTS_FILE = f"{DATA_DIR}/rank_results.csv"
HISTORY_FILE = f"{DATA_DIR}/rank_history.csv"

# 데이터 디렉토리 생성
os.makedirs(DATA_DIR, exist_ok=True)

def setup_driver():
    """셀레니움 웹드라이버 설정"""
    options = Options()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('--window-size=1920,1080')
    options.add_argument('--log-level=3')
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.4896.127 Safari/537.36")
    
    # ChromeDriverManager 사용 대신 직접 설치된 크롬드라이버 사용
    driver = webdriver.Chrome(options=options)
    return driver

def build_url(keyword):
    """검색어를 기반으로 네이버 지도 검색 URL을 생성"""
    return f"{BASE_URL}{keyword}"

def search_single_business(driver, keyword, shop_name, max_scrolls=50):
    """단일 업체의 검색 순위를 찾는 함수"""
    print(f"'{keyword}'에서 '{shop_name}' 검색 중...")
    
    try:
        url = build_url(keyword)
        driver.get(url)
        print(f"URL: {url}")
        
        # iframe 로딩 대기 및 전환
        try:
            WebDriverWait(driver, 10).until(
                EC.frame_to_be_available_and_switch_to_it((By.ID, "searchIframe"))
            )
        except TimeoutException:
            print(f"iframe 로딩 시간 초과: {keyword}, {shop_name}")
            return -1
        
        # 검색 결과 로딩 대기
        try:
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div.Ryr1F#_pcmap_list_scroll_container"))
            )
        except TimeoutException:
            print(f"페이지 로딩 실패 또는 검색 결과 없음: {keyword}, {shop_name}")
            return -1

        # 검색 결과 스크롤 및 업체 검색
        rank = 0
        found = False
        scroll_count = 0
        
        while not found and scroll_count < max_scrolls:
            scroll_count += 1
            
            # HTML 가져오기
            soup = BeautifulSoup(driver.page_source, "html.parser")
            shop_list_element = soup.select("div.Ryr1F#_pcmap_list_scroll_container > ul > li")
            
            for shop_element in shop_list_element:
                # 광고 요소 건너뛰기
                ad_element = shop_element.select_one(".gU6bV._DHlh")
                if ad_element:
                    continue
                
                rank += 1
                
                shop_name_element = shop_element.select_one(".place_bluelink.tWIhh > span.O_Uah")
                if shop_name_element:
                    current_shop_name = shop_name_element.text.strip()
                    if current_shop_name == shop_name:
                        print(f"'{shop_name}'은(는) '{keyword}' 검색 결과에서 {rank}위입니다.")
                        return rank
            
            # 더 스크롤
            driver.execute_script("document.querySelector('#_pcmap_list_scroll_container').scrollTo(0, document.querySelector('#_pcmap_list_scroll_container').scrollHeight)")
            time.sleep(1)
        
        print(f"'{shop_name}'을(를) 찾을 수 없습니다. (keyword: {keyword})")
        return -1
    
    except Exception as e:
        print(f"오류 발생: {type(e).__name__} - {e}")
        return -1

def load_search_config():
    """검색 설정 파일 로드"""
    # 기본 검색 설정
    default_config = {
        "searches": [
            {"keyword": "의정부 미용실", "shop_name": "준오헤어 의정부역점"},
            {"keyword": "강남 맛집", "shop_name": "봉피양 강남점"}
        ]
    }
    
    # 설정 파일이 없으면 기본값 사용 및 저장
    if not os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(default_config, f, ensure_ascii=False, indent=2)
        return default_config
    
    # 설정 파일 로드
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"설정 파일 로드 오류: {e}")
        return default_config

def save_results(results_df):
    """검색 결과 저장"""
    # 현재 결과 저장
    results_df.to_csv(RESULTS_FILE, index=False, encoding='utf-8-sig')
    print(f"검색 결과가 {RESULTS_FILE}에 저장되었습니다.")
    
    # 이력 데이터에 추가
    today = datetime.now().strftime("%Y-%m-%d")
    
    # 검색 날짜 추가
    results_df['검색날짜'] = today
    
    # 기존 이력 파일이 있으면 로드하고 새 결과 추가
    if os.path.exists(HISTORY_FILE):
        history_df = pd.read_csv(HISTORY_FILE, encoding='utf-8-sig')
        history_df = pd.concat([history_df, results_df], ignore_index=True)
    else:
        history_df = results_df
    
    # 이력 파일 저장
    history_df.to_csv(HISTORY_FILE, index=False, encoding='utf-8-sig')
    print(f"검색 이력이 {HISTORY_FILE}에 저장되었습니다.")

def main():
    """메인 실행 함수"""
    print(f"네이버 지도 순위 크롤러 시작: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 검색 설정 로드
    config = load_search_config()
    search_items = config.get("searches", [])
    
    if not search_items:
        print("검색할 항목이 없습니다. search_config.json 파일을 확인하세요.")
        return
    
    # 검색 실행
    results = []
    driver = setup_driver()
    
    try:
        for item in search_items:
            keyword = item.get("keyword")
            shop_name = item.get("shop_name")
            
            if not keyword or not shop_name:
                print(f"유효하지 않은 검색 항목: {item}")
                continue
            
            rank = search_single_business(driver, keyword, shop_name)
            
            result = {
                "검색어": keyword,
                "업체명": shop_name,
                "순위": rank if rank > 0 else "찾을 수 없음",
                "찾음": rank > 0
            }
            results.append(result)
            
            # 요청 간 간격
            time.sleep(1.5)
    
    finally:
        driver.quit()
    
    # 결과 처리
    if results:
        results_df = pd.DataFrame(results)
        save_results(results_df)
        print(f"총 {len(results)} 개의 검색 결과가 저장되었습니다.")
    else:
        print("저장할 검색 결과가 없습니다.")

if __name__ == "__main__":
    main()
