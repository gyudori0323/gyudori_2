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
GITHUB_REPO = "gyudori_2"     # 본인의 리포지토리 이름으로 변경

# 제목 및 설명
st.title("네이버 지도 순위 검색 도구")
st.markdown("""
이 앱은 네이버 지도에서 여러 키워드에 대한 업체의 검색 순위를 확인하고 시각화합니다.
자동 업데이트 외에도 직접 검색 요청을 할 수 있습니다.
""")

# 파일 존재 여부 확인
has_results = os.path.exists(RESULTS_FILE)
has_history = os.path.exists(HISTORY_FILE)

# 데이터 로드 함수
def load_results():
    """최신 검색 결과 로드"""
    if has_results:
        return pd.read_csv(RESULTS_FILE, encoding='utf-8-sig')
    return None

def load_history():
    """검색 이력 로드"""
    if has_history:
        return pd.read_csv(HISTORY_FILE, encoding='utf-8-sig')
    return None

def load_config():
    """검색 설정 로드"""
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"searches": []}

# GitHub 관련 함수
def create_github_issue(title, body):
    """GitHub 이슈 생성 함수"""
    # GitHub 토큰이 필요합니다 - Streamlit Secrets 사용 권장
    if 'GITHUB_TOKEN' not in st.secrets:
        st.error("GitHub 토큰이 설정되지 않았습니다. 관리자에게 문의하세요.")
        return False
        
    token = st.secrets["GITHUB_TOKEN"]
    
    url = f"https://api.github.com/repos/{GITHUB_USERNAME}/{GITHUB_REPO}/issues"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json"
    }
    data = {
        "title": title,
        "body": body,
        "labels": ["search-request"]
    }
    
    try:
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()
        return True
    except Exception as e:
        st.error(f"GitHub 이슈 생성 중 오류 발생: {e}")
        return False

def trigger_github_action():
    """GitHub Actions 워크플로우 수동 실행 트리거"""
    if 'GITHUB_TOKEN' not in st.secrets:
        st.error("GitHub 토큰이 설정되지 않았습니다. 관리자에게 문의하세요.")
        return False
        
    token = st.secrets["GITHUB_TOKEN"]
    
    url = f"https://api.github.com/repos/{GITHUB_USERNAME}/{GITHUB_REPO}/actions/workflows/crawler.yml/dispatches"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json"
    }
    data = {
        "ref": "main"
    }
    
    try:
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()
        return True
    except Exception as e:
        st.error(f"GitHub Actions 트리거 오류: {e}")
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
tab1, tab2, tab3, tab4 = st.tabs(["현재 순위", "검색 요청", "검색 설정", "순위 추적"])

# 데이터 로드
results_df = load_results()
history_df = load_history()
config = load_config()

# 탭 1: 현재 순위
with tab1:
    st.header("검색 순위 결과")
    
    if results_df is not None:
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
        st.warning("아직 검색 결과가 없습니다. GitHub Actions가 실행되면 데이터가 업데이트됩니다.")
        if st.button("지금 업데이트"):
            with st.spinner("GitHub Actions 실행 요청 중..."):
                if trigger_github_action():
                    st.success("GitHub Actions 실행 요청을 보냈습니다. 수 분 내에 데이터가 업데이트될 예정입니다.")
                else:
                    st.error("GitHub Actions 실행 요청을 실패했습니다.")

# 탭 2: 검색 요청 (새로 추가됨)
with tab2:
    st.header("새 검색 요청")
    st.markdown("""
    새로운 검색 요청을 생성할 수 있습니다. 요청은 GitHub 이슈로 등록되며, 관리자가 확인 후 추가합니다.
    """)
    
    col1, col2 = st.columns(2)
    
    with col1:
        new_keyword = st.text_input("검색어", placeholder="예: 강남 피자")
    
    with col2:
        new_shop = st.text_input("업체명", placeholder="예: 피자헛 강남점")
    
    request_reason = st.text_area("요청 사유 (선택사항)", placeholder="이 업체를 추가해야 하는 이유를 간략히 설명해주세요.")
    
    if st.button("검색 요청 제출"):
        if not new_keyword or not new_shop:
            st.error("검색어와 업체명을 모두 입력해주세요.")
        else:
            issue_title = f"검색 요청: {new_keyword} - {new_shop}"
            issue_body = f"""
## 검색 요청

- **검색어**: {new_keyword}
- **업체명**: {new_shop}
- **요청 사유**: {request_reason if request_reason else '없음'}
- **요청 시간**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

/cc @{GITHUB_USERNAME}
            """
            
            with st.spinner("검색 요청 제출 중..."):
                if create_github_issue(issue_title, issue_body):
                    st.success("검색 요청이 성공적으로 제출되었습니다. 관리자가 검토 후 추가할 예정입니다.")
                else:
                    st.error("검색 요청 제출 중 오류가 발생했습니다.")
    
    # 즉시 검색 업데이트 버튼
    st.subheader("업데이트 수동 실행")
    if st.button("전체 검색 실행"):
        with st.spinner("GitHub Actions 실행 요청 중..."):
            if trigger_github_action():
                st.success("GitHub Actions 실행 요청을 보냈습니다. 수 분 내에 데이터가 업데이트될 예정입니다.")
            else:
                st.error("GitHub Actions 실행 요청을 실패했습니다.")

# 탭 3: 검색 설정
with tab3:
    st.header("검색 설정")
    st.markdown("""
    현재 설정된 검색 조건을 확인할 수 있습니다.
    새로운 검색어와 업체를 추가하려면 "검색 요청" 탭을 이용하세요.
    """)
    
    # 검색 설정 표시
    searches = config.get("searches", [])
    if searches:
        searches_df = pd.DataFrame(searches)
        st.dataframe(searches_df, use_container_width=True)
    else:
        st.warning("검색 설정이 없습니다.")

# 탭 4: 순위 추적
with tab4:
    st.header("시간에 따른 순위 변화")
    
    if history_df is not None and not history_df.empty:
        # 업체 선택기
        unique_keywords = history_df["검색어"].unique()
        selected_keyword = st.selectbox("검색어 선택", unique_keywords)
        
        # 선택한 검색어에 해당하는 업체 목록
        shops = history_df[history_df["검색어"] == selected_keyword]["업체명"].unique()
        selected_shop = st.selectbox("업체 선택", shops)
        
        # 순위 변화 그래프
        history_chart = plot_rank_history(history_df, selected_keyword, selected_shop)
        if history_chart:
            st.pyplot(history_chart)
        else:
            st.warning("선택한 업체의 순위 데이터가 충분하지 않습니다.")
        
        # 이력 데이터 표시
        st.subheader("전체 이력 데이터")
        st.dataframe(history_df, use_container_width=True)
        
        # 다운로드 링크
        st.markdown(get_csv_download_link(history_df, "네이버_지도_순위_이력.csv"), unsafe_allow_html=True)
    else:
        st.warning("아직 이력 데이터가 없습니다. 이력은 매일 자동으로 수집됩니다.")

# 애플리케이션 사용 방법 및 정보
with st.expander("애플리케이션 정보"):
    st.markdown("""
    ### 네이버 지도 순위 검색 도구 정보
    
    - 이 앱은 네이버 지도 검색 결과에서 특정 업체의 순위를 확인합니다.
    - 데이터는 GitHub Actions를 통해 매일 자정(UTC 기준)에 자동으로 업데이트됩니다.
    - 새로운 검색어와 업체를 추가하려면 "검색 요청" 탭을 이용하세요.
    
    ### 데이터 업데이트
    
    - 마지막 업데이트 시간은 "현재 순위" 탭에서 확인할 수 있습니다.
    - "검색 요청" 탭에서 "전체 검색 실행" 버튼을 클릭하여 수동으로 데이터를 업데이트할 수 있습니다.
    
    ### 검색 요청 방법
    
    1. "검색 요청" 탭으로 이동합니다.
    2. 검색어와 업체명을 입력합니다.
    3. 요청 사유를 간략히 설명합니다 (선택사항).
    4. "검색 요청 제출" 버튼을 클릭합니다.
    5. 관리자가 검토 후 업체를 추가합니다.
    """)

# 푸터
st.markdown("---")
st.markdown("© 2025 네이버 지도 순위 검색 도구 | GitHub Actions로 자동화됨")
