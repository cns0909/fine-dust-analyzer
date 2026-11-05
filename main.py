import streamlit as st
import requests
import pandas as pd
from datetime import date
from urllib.parse import unquote

# ─────────────────────────────────────────────
# 페이지 설정 및 디자인
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="미세먼지 분석 도우미",
    page_icon="🌿",
    layout="wide",
)

st.markdown("""
<style>
.stApp {
    background: linear-gradient(135deg, #f2f8fb 0%, #edf6f6 55%, #f5f9f3 100%);
    color: #203746;
    font-family: "Pretendard", "Noto Sans KR", sans-serif;
}
.block-container {
    max-width: 1250px;
    padding-top: 2rem;
    padding-bottom: 3rem;
}
h1, h2, h3 {
    color: #174d70;
    letter-spacing: -0.035em;
}
h1 { font-weight: 800; }
h2, h3 { font-weight: 700; }
[data-testid="stCaptionContainer"] { color: #64808d; }

div[data-testid="stMetric"],
div[data-testid="stForm"],
div[data-testid="stExpander"] {
    background: rgba(255,255,255,.9);
    border: 1px solid #d8e8ee;
    border-radius: 16px;
    box-shadow: 0 5px 18px rgba(32,87,112,.06);
}
div[data-testid="stMetric"] { padding: 1rem 1.1rem; }
div[data-testid="stMetricLabel"] {
    color: #527487;
    font-weight: 600;
}
div[data-testid="stMetricValue"] {
    color: #126b9a;
    font-weight: 800;
}
.stButton > button,
.stFormSubmitButton > button,
.stDownloadButton > button {
    border-radius: 10px;
    border: 1px solid #1679ad;
    background: #1679ad;
    color: white;
    font-weight: 700;
}
.stButton > button:hover,
.stFormSubmitButton > button:hover,
.stDownloadButton > button:hover {
    background: #105d86;
    border-color: #105d86;
    color: white;
}
div[data-baseweb="input"] > div,
div[data-baseweb="select"] > div,
div[data-testid="stDateInput"] input {
    border-radius: 10px;
    border-color: #c9dfe8;
    background: white;
}
section[data-testid="stSidebar"] {
    background: #e8f3f6;
    border-right: 1px solid #d3e5eb;
}
section[data-testid="stSidebar"] h2,
section[data-testid="stSidebar"] label {
    color: #174d70;
}
div[data-testid="stDataFrame"] {
    border: 1px solid #d8e8ee;
    border-radius: 12px;
    overflow: hidden;
}
div[data-testid="stAlert"] { border-radius: 12px; }
hr { border-color: #d8e8ee; }
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────
# API 설정
# ─────────────────────────────────────────────
AIR_API_URL = (
    "https://apis.data.go.kr/B552584/ArpltnInforInqireSvc/"
    "getMsrstnAcctoRltmMesureDnsty"
)
METAL_API_URL = (
    "https://apis.data.go.kr/1480523/MetalMeasuringResultService/MetalService"
)


def clean_key(key):
    if not key:
        return ""
    return unquote(str(key).strip())


def get_secret(name):
    try:
        return st.secrets.get(name, "")
    except Exception:
        return ""


def fetch_air_data(api_key, station_name, data_term):
    params = {
        "serviceKey": clean_key(api_key),
        "returnType": "json",
        "numOfRows": 100,
        "pageNo": 1,
        "stationName": station_name,
        "dataTerm": data_term,
        "ver": "1.0",
    }

    response = requests.get(AIR_API_URL, params=params, timeout=25)
    response.raise_for_status()
    payload = response.json()

    root = payload.get("response", {})
    header = root.get("header", {})

    if str(header.get("resultCode", "00")) not in ("00", "0"):
        raise ValueError(
            "미세먼지 API 오류: "
            + str(header.get("resultMsg", "원인을 확인할 수 없음"))
        )

    items = root.get("body", {}).get("items", [])

    if not items:
        return pd.DataFrame()

    if isinstance(items, dict):
        items = [items]

    df = pd.DataFrame(items)

    for col in ("pm10Value", "pm25Value"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    if "dataTime" in df.columns:
        df["dataTime"] = pd.to_datetime(
            df["dataTime"], errors="coerce"
        )

    return df


def fetch_metal_data(
    api_key, selected_date, station_code, item_code, time_code
):
    params = {
        "ServiceKey": clean_key(api_key),
        "pageNo": 1,
        "numOfRows": 100,
        "resultType": "JSON",
        "date": selected_date.strftime("%Y%m%d"),
        "stationcode": str(station_code).strip(),
        "itemcode": str(item_code).strip(),
        "timecode": str(time_code).strip(),
    }

    response = requests.get(METAL_API_URL, params=params, timeout=25)
    response.raise_for_status()

    try:
        payload = response.json()
    except ValueError as exc:
        raise ValueError(
            "금속 성분 API 응답을 JSON으로 읽지 못했어. "
            "인증키와 응답 형식을 확인해 줘."
        ) from exc

    service = payload.get("MetalService", {})
    header = service.get("header", {})
    code = str(header.get("code", "00"))

    if code not in ("00", "0"):
        raise ValueError(
            "금속 성분 API 오류: "
            + str(header.get("message", "원인을 확인할 수 없음"))
        )

    items = service.get("item") or []

    if isinstance(items, dict):
        items = [items]

    df = pd.DataFrame(items)

    if df.empty:
        return df

    if "SDATE" in df.columns:
        df["SDATE"] = pd.to_datetime(
            df["SDATE"].astype(str),
            format="%Y%m%d%H%M%S",
            errors="coerce",
        )

    if "VALUE" in df.columns:
        df["VALUE"] = pd.to_numeric(df["VALUE"], errors="coerce")

    if "SDATE" in df.columns:
        df = df.sort_values("SDATE")

    return df


def csv_bytes(df):
    return df.to_csv(
        index=False, encoding="utf-8-sig"
    ).encode("utf-8-sig")


def make_air_report(df, station, period):
    lines = [
        "미세먼지 분석 보고서",
        f"측정소: {station}",
        f"조회 기간 설정: {period}",
        f"조회 자료 수: {len(df)}건",
        "",
    ]

    for col, label in (
        ("pm10Value", "PM10"),
        ("pm25Value", "PM2.5"),
    ):
        if col not in df.columns:
            continue

        values = pd.to_numeric(df[col], errors="coerce").dropna()
        if values.empty:
            continue

        idx_max = values.idxmax()
        idx_min = values.idxmin()

        max_time = (
            df.loc[idx_max, "dataTime"]
            if "dataTime" in df.columns
            else "확인 불가"
        )
        min_time = (
            df.loc[idx_min, "dataTime"]
            if "dataTime" in df.columns
            else "확인 불가"
        )

        lines.extend([
            label,
            f"- 평균: {values.mean():.2f} µg/m³",
            f"- 최댓값: {values.max():g} µg/m³ (측정 시각: {max_time})",
            f"- 최솟값: {values.min():g} µg/m³ (측정 시각: {min_time})",
            "",
        ])

    lines.extend([
        "해석 시 주의점",
        "- 이 보고서는 API 측정값을 요약한 것이며 원인을 확정하지 않아.",
        "- 측정소, 조회 기간, 결측값 여부를 함께 고려해야 해.",
        "- 미세먼지 농도만으로 특정 오염원이나 화학 반응을 단정할 수 없어.",
    ])

    return "\n".join(lines)


def explain_air_data(df):
    explanations = []

    if "pm10Value" in df.columns and df["pm10Value"].notna().any():
        explanations.append(
            f"PM10 평균 측정값은 {df['pm10Value'].mean():.2f} µg/m³이야."
        )

    if "pm25Value" in df.columns and df["pm25Value"].notna().any():
        explanations.append(
            f"PM2.5 평균 측정값은 {df['pm25Value'].mean():.2f} µg/m³이야."
        )

    explanations.extend([
        "PM10은 공기역학적 직경이 10 µm 이하인 입자상 물질이고, "
        "PM2.5는 2.5 µm 이하인 입자상 물질이야.",
        "미세먼지는 한 가지 물질이 아니라 여러 성분이 섞인 혼합물이야.",
        "일부 입자는 배출원에서 직접 나오고, 일부는 대기 중 화학 반응으로 생성될 수 있어.",
        "측정 농도만으로 특정 배출원이나 화학 반응을 확정할 수는 없어.",
    ])

    return explanations


# ─────────────────────────────────────────────
# 앱 상단
# ─────────────────────────────────────────────
st.markdown("""
<div style="
    padding: 1.4rem 1.6rem;
    border-radius: 20px;
    background: linear-gradient(110deg, #dceff5, #e8f4e9);
    border: 1px solid #d0e5e8;
    margin-bottom: 1.3rem;">
    <div style="font-size: 0.9rem; color: #47778a; font-weight: 700;">
        AIR QUALITY · DATA LAB
    </div>
    <div style="font-size: 2rem; color: #174d70; font-weight: 850; margin-top: .25rem;">
        🌿 미세먼지 분석 도우미
    </div>
    <div style="color: #527487; margin-top: .4rem;">
        공공데이터로 대기오염 농도와 금속 성분 측정값을 살펴보는 탐구 앱
    </div>
</div>
""", unsafe_allow_html=True)

air_key = get_secret("AIRKOREA_API_KEY")
metal_key = get_secret("METAL_API_KEY")

with st.sidebar:
    st.markdown("## 🌱 분석 메뉴")
    section = st.radio(
        "원하는 분석을 선택해 줘",
        [
            "미세먼지 농도 분석",
            "날짜별 측정값 비교",
            "금속 성분 측정 결과",
            "화학 개념 알아보기",
        ],
    )
    st.divider()
    st.caption(
        "API 키는 코드에 직접 입력하지 말고 "
        "Streamlit Cloud의 Secrets에 저장해 줘."
    )


# ─────────────────────────────────────────────
# 1. 미세먼지 분석
# ─────────────────────────────────────────────
if section == "미세먼지 농도 분석":
    st.subheader("📊 미세먼지 농도 분석")
    st.write("측정소와 조회 기간을 선택해 농도 변화와 통계값을 확인해.")

    if not air_key:
        st.warning("AIRKOREA_API_KEY가 없어. Streamlit Secrets에 등록해 줘.")
    else:
        with st.form("air_form"):
            c1, c2 = st.columns([2, 1])
            station = c1.text_input("측정소 이름", value="종로구")
            period = c2.selectbox("조회 기간", ["일간", "월간", "3개월"])
            term_map = {"일간": "DAILY", "월간": "MONTH", "3개월": "3MONTH"}
            air_submit = st.form_submit_button("미세먼지 조회", type="primary")

        if air_submit:
            try:
                with st.spinner("측정 자료를 불러오는 중..."):
                    df = fetch_air_data(air_key, station.strip(), term_map[period])
                st.session_state["air_df"] = df
                st.session_state["air_station"] = station.strip()
                st.session_state["air_period"] = period
            except Exception as exc:
                st.error(f"미세먼지 조회 실패: {exc}")

        air_df = st.session_state.get("air_df")

        if air_df is not None:
            if air_df.empty:
                st.info("조회된 자료가 없어. 측정소 이름이나 기간을 확인해 줘.")
            else:
                station_saved = st.session_state.get("air_station", "-")
                period_saved = st.session_state.get("air_period", "-")

                st.success(f"{station_saved} 측정소 자료 {len(air_df)}건을 불러왔어.")

                # PM10 / PM2.5 지표
                for col, label in (("pm10Value", "PM10"), ("pm25Value", "PM2.5")):
                    if col in air_df.columns:
                        vals = pd.to_numeric(air_df[col], errors="coerce").dropna()
                        if not vals.empty:
                            st.markdown(f"#### {label}")
                            a, b, c = st.columns(3)
                            a.metric("평균 농도", f"{vals.mean():.1f} µg/m³")
                            b.metric("최댓값", f"{vals.max():g} µg/m³")
                            c.metric("최솟값", f"{vals.min():g} µg/m³")

                # 그래프
                if "dataTime" in air_df.columns:
                    chart_df = air_df.sort_values("dataTime").set_index("dataTime")
                    chart_cols = [
                        c for c in ("pm10Value", "pm25Value")
                        if c in chart_df.columns
                    ]
                    if chart_cols:
                        st.markdown("#### 📈 시간에 따른 농도 변화")
                        st.line_chart(chart_df[chart_cols], use_container_width=True)

                # 해석
                with st.expander("🧪 측정값과 화학적 해석", expanded=True):
                    for explanation in explain_air_data(air_df):
                        st.write("• " + explanation)

                with st.expander("원본 측정 자료"):
                    st.dataframe(air_df, use_container_width=True, hide_index=True)

                st.download_button(
                    "📥 미세먼지 CSV 다운로드",
                    data=csv_bytes(air_df),
                    file_name="air_quality_data.csv",
                    mime="text/csv",
                )

                report = make_air_report(air_df, station_saved, period_saved)
                with st.expander("📝 자동 분석 보고서 미리보기"):
                    st.text(report)

                st.download_button(
                    "📄 분석 보고서 TXT 다운로드",
                    data=report.encode("utf-8-sig"),
                    file_name="air_quality_report.txt",
                    mime="text/plain",
                )


# ─────────────────────────────────────────────
# 2. 날짜별 측정값 비교
# ─────────────────────────────────────────────
elif section == "날짜별 측정값 비교":
    st.subheader("🗓️ 날짜별 측정값 비교")
    st.write("앞서 조회한 자료에서 두 시점을 선택해 농도 변화량과 변화율을 비교해.")

    air_df = st.session_state.get("air_df")

    if air_df is None or air_df.empty or "dataTime" not in air_df.columns:
        st.info("먼저 ‘미세먼지 농도 분석’ 메뉴에서 자료를 조회해 줘.")
    else:
        compare_df = air_df.dropna(subset=["dataTime"]).copy()
        compare_df = compare_df.sort_values("dataTime")
        compare_df["시각 선택"] = compare_df["dataTime"].dt.strftime("%Y-%m-%d %H:%M")
        options = compare_df["시각 선택"].drop_duplicates().tolist()

        if len(options) < 2:
            st.info("비교할 수 있는 측정 시점이 2개 이상 필요해.")
        else:
            c1, c2 = st.columns(2)
            first = c1.selectbox("첫 번째 시점", options, index=0)
            second = c2.selectbox("두 번째 시점", options, index=len(options) - 1)

            if first == second:
                st.warning("서로 다른 시점을 선택해 줘.")
            else:
                row1 = compare_df[compare_df["시각 선택"] == first].iloc[0]
                row2 = compare_df[compare_df["시각 선택"] == second].iloc[0]
                rows = []

                for col, label in (("pm10Value", "PM10"), ("pm25Value", "PM2.5")):
                    if col not in compare_df.columns:
                        continue

                    v1 = pd.to_numeric(pd.Series([row1[col]]), errors="coerce").iloc[0]
                    v2 = pd.to_numeric(pd.Series([row2[col]]), errors="coerce").iloc[0]

                    if pd.notna(v1) and pd.notna(v2):
                        diff = v2 - v1
                        change = diff / v1 * 100 if v1 != 0 else None
                        rows.append({
                            "항목": label,
                            first: v1,
                            second: v2,
                            "변화량": diff,
                            "변화율 (%)": round(change, 2) if change is not None else "첫 값이 0이어서 계산 불가",
                        })

                if rows:
                    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
                    st.caption("변화율 = (두 번째 값 - 첫 번째 값) ÷ 첫 번째 값 × 100")
                else:
                    st.info("두 시점에 비교 가능한 수치가 없어.")


# ─────────────────────────────────────────────
# 3. 금속 성분 분석
# ─────────────────────────────────────────────
elif section == "금속 성분 측정 결과":
    st.subheader("⚗️ 대기 중 금속 성분 측정 결과")
    st.write("날짜와 측정소·성분 코드를 입력해 금속 성분 측정값을 확인해.")

    if not metal_key:
        st.warning("METAL_API_KEY가 없어. Streamlit Secrets에 등록해 줘.")
    else:
        with st.form("metal_form"):
            selected_date = st.date_input(
                "측정 날짜",
                value=date(2017, 12, 8),
                max_value=date.today(),
            )

            c1, c2 = st.columns(2)
            station_code = c1.text_input("측정소 코드", value="1")
            item_code = c2.text_input("성분 코드 (itemcode)", value="90303")

            time_code = st.selectbox(
                "시간 구분",
                ["RH02", "RH24"],
                format_func=lambda x: "RH02 (2시간 평균)" if x == "RH02" else "RH24 (24시간 평균)",
            )

            metal_submit = st.form_submit_button("금속 성분 조회", type="primary")

        if metal_submit:
            try:
                with st.spinner("금속 성분 자료를 불러오는 중..."):
                    df = fetch_metal_data(
                        metal_key, selected_date, station_code, item_code, time_code
                    )

                st.session_state["metal_df"] = df
                st.session_state["metal_query"] = {
                    "date": selected_date.isoformat(),
                    "station": station_code,
                    "item": item_code,
                    "time": time_code,
                }
            except Exception as exc:
                st.error(f"금속 성분 조회 실패: {exc}")

        metal_df = st.session_state.get("metal_df")

        if metal_df is not None:
            info = st.session_state.get("metal_query", {})
            st.caption(
                f"조회 날짜: {info.get('date', '-')} · "
                f"측정소 코드: {info.get('station', '-')} · "
                f"성분 코드: {info.get('item', '-')} · "
                f"시간 구분: {info.get('time', '-')}"
            )

            if metal_df.empty:
                st.info("해당 조건의 자료가 없어. 날짜나 코드를 바꿔서 조회해 줘.")
            else:
                st.success(f"금속 성분 측정 자료 {len(metal_df)}건을 불러왔어.")

                if "VALUE" in metal_df.columns:
                    vals = pd.to_numeric(metal_df["VALUE"], errors="coerce").dropna()
                    a, b, c = st.columns(3)
                    a.metric("자료 수", f"{len(vals)}건")
                    b.metric("평균값", f"{vals.mean():.4g}" if not vals.empty else "자료 없음")
                    c.metric("최댓값", f"{vals.max():.4g}" if not vals.empty else "자료 없음")

                if {"SDATE", "VALUE"}.issubset(metal_df.columns):
                    plot_df = metal_df.dropna(subset=["SDATE", "VALUE"]).set_index("SDATE")
                    if not plot_df.empty:
                        st.markdown("#### 📈 측정 시각별 측정값")
                        st.line_chart(plot_df[["VALUE"]], use_container_width=True)

                st.caption("금속 성분 측정값의 단위는 API 공식 설명을 확인하고 해석해 줘.")

                with st.expander("원본 측정 자료"):
                    st.dataframe(metal_df, use_container_width=True, hide_index=True)

                st.download_button(
                    "📥 금속 성분 CSV 다운로드",
                    data=csv_bytes(metal_df),
                    file_name="metal_measurement_data.csv",
                    mime="text/csv",
                )


# ─────────────────────────────────────────────
# 4. 화학 개념
# ─────────────────────────────────────────────
else:
    st.subheader("🔬 화학 개념 알아보기")

    st.markdown("""
    ### 1. 미세먼지와 초미세먼지
    - **PM10**은 공기역학적 직경이 10 µm 이하인 입자상 물질이야.
    - **PM2.5**는 공기역학적 직경이 2.5 µm 이하인 입자상 물질이야.
    - 미세먼지는 여러 물질이 섞인 혼합물이야.

    ### 2. 대기 중 화학 반응
    - 일부 미세먼지는 직접 배출되지만, 일부는 기체 상태의 물질이 대기 중에서 화학 반응을 거쳐 생성될 수 있어.
    - 온도, 습도, 햇빛, 대기 중 다른 물질 등이 생성 과정에 영향을 줄 수 있어.
    - 측정값만으로 특정 반응이 일어났다고 단정할 수는 없어.

    ### 3. 금속 성분 분석
    - 대기 입자에는 금속을 포함한 여러 성분이 존재할 수 있어.
    - 금속 성분 측정값을 미세먼지 농도와 함께 살펴보면 대기오염 특성을 더 구체적으로 탐구할 수 있어.
    - 비교할 때는 측정소, 날짜, 시간, 단위가 서로 맞는지 확인해야 해.
    - 성분 코드와 금속 이름은 공식 코드표로 확인된 경우에만 연결해야 해.

    ### 4. 데이터를 해석할 때 주의할 점
    - 값이 높다고 특정 오염원이 원인이라고 바로 결론 내릴 수 없어.
    - 자료가 없다는 것이 농도가 0이라는 뜻은 아니야.
    - 측정소 위치, 측정 시간, 결측값 등을 고려해야 해.

    ### 탐구 질문
    **미세먼지 농도 변화와 금속 성분 측정값은 어떤 관계를 보일까?**

    같은 날짜와 시간대의 자료를 모아 비교하고, 관찰한 경향과 자료의 한계를 함께 정리해 볼 수 있어.
    """)


st.divider()
st.caption(
    "자료 출처: AirKorea 및 공공데이터포털 금속 성분 측정 API. "
    "결과 해석은 측정 자료와 API 설명을 바탕으로 해야 해."
)
