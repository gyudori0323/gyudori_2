import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import os
import json
from datetime import datetime
import base64
from io import BytesIO

# 페이지 설정
st.set_page_config(
    page_title="네이버 지도 순위 검색",
    page_icon="🗺️",
    layout="wide"
)

# 데이터 경로
DATA_DIR = "data"
RESULTS_FILE = f"{DATA_DIR}/rank_results.csv"
HISTORY_FILE = f"{DATA_DIR}/rank_history.csv"
CONFIG_FILE = "search_config.json"

# 제목 및 설명
st.title("네이버 지도 순위 검색 도구")
st.markdown("""
이 앱은 네이버 지도에서 여러 키워드에 대한 업체의 검색 순위를 확인하고 시각화합니다.
데이터는 자동으로 매일 업데이트됩니다.
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

def plot_keyword_comparison(df):
    """검색어별 순위 비교 (여러 검색어에 동일 업체가 있는 경우)"""
    # 데이터 준비 (못 찾은 경우 제외)
    plot_df = df[df["찾음"] == True].copy()
    if plot_df.empty:
        return None
    
    # 순위 열을 숫자로 변환
    plot_df["순위"] = plot_df["순위"].astype(int)
    
    # 중복된 업체가 있는지 확인
    if plot_df["업체명"].nunique() < len(plot_df):
        # 업체별 여러 검색어의 순위를 비교하는 그래프
        fig, ax = plt.subplots(figsize=(10, 6))
        
        # 피벗 테이블 생성
        pivot_df = plot_df.pivot(index="업체명", columns="검색어", values="순위")
        
        # 히트맵 생성
        sns.heatmap(pivot_df, annot=True, cmap="YlGnBu_r", ax=ax, fmt="d")
        
        plt.title("업체별 검색어 순위 비교")
        plt.tight_layout()
        
        return fig
    return None

def get_csv_download_link(df, filename="네이버_지도_순위_결과.csv"):
    """데이터프레임을 CSV로 변환하여 다운로드 링크 생성"""
    csv = df.to_csv(index=False, encoding='utf-8-sig')
    b64 = base64.b64encode(csv.encode('utf-8-sig')).decode()
    href = f'<a href="data:file/csv;base64,{b64}" download="{filename}">CSV 파일 다운로드</a>'
    return href

# 메인 앱 UI
tab1, tab2, tab3 = st.tabs(["현재 순위", "검색 설정", "순위 추적"])

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
        
        # 검색어별 비교 (해당하는 경우)
        keyword_chart = plot_keyword_comparison(results_df)
        if keyword_chart:
            st.subheader("검색어별 순위 비교")
            st.pyplot(keyword_chart)
            
        # 상위 20위 내 업체 수
        st.subheader("검색어별 상위 20위 내 업체 수")
        top20_df = results_df[results_df["찾음"] == True].copy()
        top20_df["순위"] = pd.to_numeric(top20_df["순위"], errors="coerce")
        top20_df = top20_df[top20_df["순위"] <= 20]
        top20_count = top20_df.groupby("검색어").size().reset_index(name="상위20위_업체수")
        st.dataframe(top20_count, use_container_width=True)
    else:
        st.warning("아직 검색 결과가 없습니다. GitHub Actions가 실행되면 데이터가 업데이트됩니다.")

# 탭 2: 검색 설정
with tab2:
    st.header("검색 설정")
    st.markdown("""
    현재 설정된 검색 조건을 확인할 수 있습니다.
    검색 설정을 변경하려면 GitHub 리포지토리의 `search_config.json` 파일을 수정하세요.
    """)
    
    # 검색 설정 표시
    searches = config.get("searches", [])
    if searches:
        searches_df = pd.DataFrame(searches)
        st.dataframe(searches_df, use_container_width=True)
    else:
        st.warning("검색 설정이 없습니다.")

# 탭 3: 순위 추적
with tab3:
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
    - 순위 데이터는 시간에 따라 변할 수 있으며, 네이버의 알고리즘 변경 등에 영향을 받을 수 있습니다.
    
    ### 데이터 업데이트
    
    - 마지막 업데이트 시간은 "현재 순위" 탭에서 확인할 수 있습니다.
    - 수동으로 데이터를 업데이트하려면 GitHub 리포지토리에서 Actions 탭의 "Naver Map Rank Crawler" 워크플로우를 수동으로 실행하세요.
    
    ### 검색 설정 변경
    
    검색 설정을 변경하려면:
    1. GitHub 리포지토리에서 `search_config.json` 파일을 수정합니다.
    2. 다음 형식을 따릅니다:
    ```json
    {
      "searches": [
        {
          "keyword": "검색어1",
          "shop_name": "업체명1"
        },
        {
          "keyword": "검색어2",
          "shop_name": "업체명2"
        }
      ]
    }
    ```
    """)

# 푸터
st.markdown("---")
st.markdown("© 2025 네이버 지도 순위 검색 도구 | GitHub Actions로 자동화됨")
