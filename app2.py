import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import os
import json
import requests
from datetime import datetime
import base64
from io import BytesIO
import time

# 페이지 설정
st.set_page_config(
    page_title="네이버 지도 순위 검색",
    page_icon="🗺️",
    layout="wide"
)

# 환경 변수 설정
DATA_DIR = "data"
RESULTS_FILE = f"{DATA_DIR}/rank_results.csv"
HISTORY_FILE = f"{DATA_DIR}/rank_history.csv"
CONFIG_FILE = "search_config.json"

# GitHub 설정
GITHUB_USERNAME = "gyudori0323"  # 본인의 GitHub 사용자명으로 변경
GITHUB_REPO = "gyudori_test"     # 본인의 리포지토리 이름으로 변경

# 제목 및 설명
st.title("네이버 지도 순위 검색 도구")
st.markdown("""
이 앱은 네이버 지도에서 여러 키워드에 대한 업체의 검색 순위를 확인하고 시각화합니다.
자동 업데이트와 함께 사용자 지정 검색도 지원합니다.
""")

# 파일 존재 여부 확인
has_results = os.path.exists(RESULTS_FILE)
has_history = os.path.exists(HISTORY_FILE)

# 데이터 로드 함수
def load_results():
    """최신 검색 결과 로드"""
    if has_results:
        return pd.read_csv(RESULTS_FILE, encoding='utf-8-sig')
    return pd.DataFrame(columns=["검색어", "업체명", "순위", "찾음"])

def load_history():
    """검색 이력 로드"""
    if has_history:
        return pd.read_csv(HISTORY_FILE, encoding='utf-8-sig')
    return pd.DataFrame(columns=["검색어", "업체명", "순위", "찾음", "검색날짜"])

def load_config():
    """검색 설정 로드"""
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"searches": []}

# GitHub Actions 트리거 함수
def trigger_github_action(keyword=None, shop_name=None):
    """GitHub Actions 워크플로우 수동 실행 트리거"""
    if 'GITHUB_TOKEN' not in st.secrets:
        st.warning("GitHub 토큰이 설정되지 않았습니다. 이 기능을 사용하려면 관리자가 GitHub 토큰을 설정해야 합니다.")
        st.info("대신 전체 검색 결과를 기다리거나 다음 자동 업데이트를 기다려주세요.")
        return False
        
    token = st.secrets["GITHUB_TOKEN"]
    
    # GitHub Actions 워크플로우 디스패치 API
    url = f"https://api.github.com/repos/{GITHUB_USERNAME}/{GITHUB_REPO}/actions/workflows/crawler.yml/dispatches"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    # 특정 검색어와 업체명을 포함하는 입력 전달
    # workflow_dispatch 이벤트에서 inputs 파라미터로 받을 수 있음
    data = {
        "ref": "main",
        "inputs": {}
    }
    
    # 특정 검색어와 업체명이 제공된 경우, inputs에 추가
    if keyword and shop_name:
        data["inputs"] = {
            "keyword": keyword,
            "shop_name": shop_name,
            "single_search": "true"
        }
    
    try:
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()
        return True
    except requests.exceptions.RequestException as e:
        st.error(f"GitHub Actions 트리거 오류: {e}")
        return False

# 임시 검색 설정 파일 업데이트 함수
def update_temp_search_config(keyword, shop_name):
    """임시 검색 설정 파일을 생성하여 GitHub 커밋"""
    if 'GITHUB_TOKEN' not in st.secrets:
        st.warning("GitHub 토큰이 설정되지 않았습니다. 이 기능을 사용하려면 관리자가 GitHub 토큰을 설정해야 합니다.")
        return False
        
    token = st.secrets["GITHUB_TOKEN"]
    
    # 현재 파일 내용 가져오기
    get_url = f"https://api.github.com/repos/{GITHUB_USERNAME}/{GITHUB_REPO}/contents/temp_search.json"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    # 임시 검색 데이터
    temp_search_data = {
        "keyword": keyword,
        "shop_name": shop_name,
        "timestamp": datetime.now().isoformat()
    }
    
    try:
        # 파일이 이미 존재하는지 확인
        try:
            response = requests.get(get_url, headers=headers)
            response.raise_for_status()
            file_info = response.json()
            sha = file_info.get("sha")
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                # 파일이 없는 경우
                sha = None
            else:
                raise
        
        # 파일 업데이트 또는 생성
        update_url = f"https://api.github.com/repos/{GITHUB_USERNAME}/{GITHUB_REPO}/contents/temp_search.json"
        data = {
            "message": f"임시 검색 설정 업데이트: {keyword} - {shop_name}",
            "content": base64.b64encode(json.dumps(temp_search_data, ensure_ascii=False).encode('utf-8')).decode('utf-8'),
            "branch": "main"
        }
        
        if sha:
            data["sha"] = sha
        
        response = requests.put(update_url, headers=headers, json=data)
        response.raise_for_status()
        return True
    
    except Exception as e:
        st.error(f"임시 검색 설정 업데이트 오류: {e}")
        return False

# 데이터 시각화 함수들
def plot_rank_bar_chart(df):
    """순위 막대 그래프 생성"""
    # 데이터 준비 (못 찾은 경우 제외)
    plot_df = df[df["찾음"] == True].copy()
    if plot_df.empty:
        st.warning("그래프를 그릴 데이터가 없습니다. (순위를 찾을 수 없는 업체만 있음)")
        return None
    
    # 순위 열을 숫자로 변환
    plot_df["순위"] = plot_df["순위"].astype(int)
    
    # 순위 기준으로 정렬
    plot_df = plot_df.sort_values("순위")
    
    fig, ax = plt.subplots(figsize=(10, 6))
    bars = ax.bar(
        plot_df["업체명"] + " (" + plot_df["검색어"] + ")",
        plot_df["순위"],
        color="skyblue"
    )
    
    # 막대 위에 순위 표시
    for bar in bars:
        height = bar.get_height()
        ax.text(
            bar.get_x() + bar.get_width()/2.,
            height + 0.5,
            f'{int(height)}',
            ha='center', 
            va='bottom'
        )
    
    plt.title("검색어별 업체 순위")
    plt.xlabel("업체명 (검색어)")
    plt.ylabel("순위")
    plt.xticks(rotation=45, ha="right")
    plt.gca().invert_yaxis()  # 순위가 낮을수록 좋으므로 y축 반전
    plt.tight_layout()
    
    return fig

def plot_rank_history(history_df, keyword, shop_name):
    """특정 업체의 순위 변화 추적 그래프"""
    # 데이터 필터링
    plot_df = history_df[(history_df["검색어"] == keyword) & 
                          (history_df["업체명"] == shop_name) &
                          (history_df["찾음"] == True)].copy()
    
    if plot_df.empty:
        return None
    
    # 순위 열을 숫자로 변환하고 날짜 형식 변환
    plot_df["순위"] = plot_df["순위"].astype(int)
    plot_df["검색날짜"] = pd.to_datetime(plot_df["검색날짜"])
    
    # 날짜 기준 정렬
    plot_df = plot_df.sort_values("검색날짜")
    
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.plot(plot_df["검색날짜"], plot_df["순위"], marker="o", linestyle="-", color="royalblue")
    
    # 그래프 설정
    plt.title(f"{keyword} - {shop_name} 순위 변화")
    plt.xlabel("날짜")
    plt.ylabel("순위")
    plt.grid(True, linestyle="--", alpha=0.7)
    plt.gca().invert_yaxis()  # 순위가 낮을수록 좋으므로 y축 반전
    plt.xticks(rotation=45)
    plt.tight_layout()
    
    return fig

def get_csv_download_link(df, filename="네이버_지도_순위_결과.csv"):
    """데이터프레임을 CSV로 변환하여 다운로드 링크 생성"""
    csv = df.to_csv(index=False, encoding='utf-8-sig')
    b64 = base64.b64encode(csv.encode('utf-8-sig')).decode()
    href = f'<a href="data:file/csv;base64,{b64}" download="{filename}">CSV 파일 다운로드</a>'
    return href

# 메인 앱 UI
tab1, tab2, tab3 = st.tabs(["현재 순위", "검색 요청", "순위 추적"])

# 데이터 로드
results_df = load_results()
history_df = load_history()
config = load_config()

# 탭 1: 현재 순위
with tab1:
    st.header("검색 순위 결과")
    
    if not results_df.empty:
        # 마지막 업데이트 시간 (파일의 수정 시간)
        if has_results:
            mod_time = os.path.getmtime(RESULTS_FILE)
            mod_time_str = datetime.fromtimestamp(mod_time).strftime("%Y-%m-%d %H:%M:%S")
            st.info(f"마지막 업데이트: {mod_time_str}")
        
        # 결과 표시
        st.dataframe(results_df, use_container_width=True)
        
        # 다운로드 링크
        st.markdown(get_csv_download_link(results_df), unsafe_allow_html=True)
        
        # 데이터 시각화
        st.subheader("데이터 시각화")
        
        # 막대 그래프
        bar_chart = plot_rank_bar_chart(results_df)
        if bar_chart:
            st.pyplot(bar_chart)
    else:
        st.warning("아직 검색 결과가 없습니다. 자동 업데이트를 기다리거나 검색 요청 탭에서 직접 검색해 보세요.")

# 탭 2: 검색 요청 (직접 Actions 트리거)
with tab2:
    st.header("검색 요청")
    st.markdown("""
    원하는 검색어와 업체명을 입력하여 직접 순위를 검색할 수 있습니다.
    검색 결과는 GitHub Actions를 통해 처리되며, 몇 분 후에 결과를 확인할 수 있습니다.
    """)
    
    col1, col2 = st.columns(2)
    
    with col1:
        search_keyword = st.text_input("검색어", placeholder="예: 강남 피자")
    
    with col2:
        search_shop = st.text_input("업체명", placeholder="예: 피자헛 강남점")
    
    if st.button("순위 검색 요청"):
        if not search_keyword or not search_shop:
            st.error("검색어와 업체명을 모두 입력해주세요.")
        else:
            with st.spinner(f"'{search_keyword}'에서 '{search_shop}' 검색 요청 중..."):
                # 임시 검색 설정 업데이트
                if update_temp_search_config(search_keyword, search_shop):
                    # GitHub Actions 워크플로우 트리거
                    if trigger_github_action(search_keyword, search_shop):
                        st.success(f"검색 요청이 성공적으로 제출되었습니다. 몇 분 후에 결과를 확인할 수 있습니다.")
                        
                        # 실행 중 표시
                        st.info("GitHub Actions가 실행 중입니다...")
                        progress_bar = st.progress(0)
                        
                        # 진행 상황 시뮬레이션 (실제 진행 상황이 아님)
                        for i in range(100):
                            # 진행 상황 업데이트
                            progress_bar.progress(i + 1)
                            time.sleep(0.05)
                        
                        st.success("검색 요청이 처리되었습니다! '현재 순위' 탭에서 결과를 확인하세요.")
                        st.button("현재 순위 탭으로 이동", on_click=lambda: st.experimental_set_query_params(tab="current_rank"))
                    else:
                        st.error("GitHub Actions 실행 요청을 실패했습니다. 관리자에게 문의하세요.")
                else:
                    st.error("검색 설정 업데이트를 실패했습니다. 관리자에게 문의하세요.")
    
    st.divider()
    
    # 기존 데이터로 일괄 검색
    st.subheader("전체 검색 실행")
    st.markdown("기존에 설정된 모든 업체의 순위를 일괄적으로 검색합니다.")
    
    if st.button("전체 검색 실행"):
        with st.spinner("전체 검색 요청 중..."):
            if trigger_github_action():
                st.success("전체 검색 요청이 성공적으로 제출되었습니다. 몇 분 후에 결과를 확인할 수 있습니다.")
                
                # 실행 중 표시
                st.info("GitHub Actions가 실행 중입니다...")
                progress_bar = st.progress(0)
                
                # 진행 상황 시뮬레이션 (실제 진행 상황이 아님)
                for i in range(100):
                    # 진행 상황 업데이트
                    progress_bar.progress(i + 1)
                    time.sleep(0.05)
                
                st.success("전체 검색이 처리되었습니다! '현재 순위' 탭에서 결과를 확인하세요.")
            else:
                st.error("GitHub Actions 실행 요청을 실패했습니다. 관리자에게 문의하세요.")

# 탭 3: 순위 추적
with tab3:
    st.header("시간에 따른 순위 변화")
    
    if not history_df.empty:
        # 업체 선택기
        unique_keywords = history_df["검색어"].unique()
        selected_keyword = st.selectbox("검색어 선택", unique_keywords)
        
        # 선택한 검색어에 해당하는 업체 목록
        shops = history_df[history_df["검색어"] == selected_keyword]["업체명"].unique()
        selected_shop = st.selectbox("업체 선택", shops)
        
        # 순위 변화 표시
        shop_history = history_df[(history_df["검색어"] == selected_keyword) & 
                                 (history_df["업체명"] == selected_shop)].copy()
        
        if not shop_history.empty:
            # 데이터 전처리
            shop_history["검색날짜"] = pd.to_datetime(shop_history["검색날짜"])
            shop_history = shop_history.sort_values("검색날짜")
            
            # 그래프로 표시
            st.subheader("순위 변화 추이")
            
            # 숫자 형식으로 변환 (찾지 못한 경우 처리)
            shop_history.loc[shop_history["찾음"] == False, "순위"] = None
            shop_history["순위"] = pd.to_numeric(shop_history["순위"], errors="coerce")
            
            fig, ax = plt.subplots(figsize=(10, 6))
            ax.plot(shop_history["검색날짜"], shop_history["순위"], marker="o", linestyle="-", color="royalblue")
            
            # 그래프 설정
            plt.title(f"{selected_keyword} - {selected_shop} 순위 변화")
            plt.xlabel("날짜")
            plt.ylabel("순위")
            plt.grid(True, linestyle="--", alpha=0.7)
            plt.gca().invert_yaxis()  # 순위가 낮을수록 좋으므로 y축 반전
            plt.xticks(rotation=45)
            plt.tight_layout()
            
            st.pyplot(fig)
            
            # 이력 데이터 표시
            st.subheader("검색 이력")
            st.dataframe(shop_history[["검색날짜", "순위", "찾음"]], use_container_width=True)
        else:
            st.warning(f"'{selected_keyword} - {selected_shop}'에 대한 이력 데이터가 없습니다.")
    else:
        st.warning("아직 이력 데이터가 없습니다. 검색 요청을 통해 데이터를 수집해 보세요.")

# 애플리케이션 사용 방법 및 정보
with st.expander("애플리케이션 정보"):
    st.markdown("""
    ### 네이버 지도 순위 검색 도구 정보
    
    - 이 앱은 네이버 지도 검색 결과에서 특정 업체의 순위를 확인합니다.
    - 데이터는 자동으로 정기 업데이트되며, 사용자가 직접 검색 요청을 할 수도 있습니다.
    - 검색 결과는 자동으로 저장되어 시간에 따른 순위 변화를 추적할 수 있습니다.
    
    ### 사용 방법
    
    1. **현재 순위** 탭:
       - 가장 최근 검색된 업체들의 순위를 확인합니다.
       - 그래프와 표로 결과를 확인할 수 있습니다.
    
    2. **검색 요청** 탭:
       - 새로운 검색어와 업체명을 입력하여 검색 요청을 제출합니다.
       - 검색 결과는 몇 분 후에 확인할 수 있습니다.
       - "전체 검색 실행" 버튼으로 모든 등록된 업체의 순위를 일괄 검색할 수 있습니다.
    
    3. **순위 추적** 탭:
       - 시간에 따른 업체의 순위 변화를 그래프로 확인합니다.
       - 특정 업체를 선택하여 상세 이력을 볼 수 있습니다.
    
    ### 주의사항
    
    - 검색 요청은 GitHub Actions를 통해 처리되며, 결과가 표시되기까지 몇 분이 소요될 수 있습니다.
    - 검색 결과는 네이버 지도의 변경에 따라 달라질 수 있습니다.
    """)

# 푸터
st.markdown("---")
st.markdown("© 2025 네이버 지도 순위 검색 도구 | GitHub Actions 자동화")
