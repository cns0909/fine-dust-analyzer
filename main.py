
import streamlit as st
import requests
import pandas as pd
from datetime import date
from urllib.parse import unquote

st.set_page_config(
    page_title="미세먼지·금속 성분 분석",
    page_icon="🌫️",
    layout="wide",
)

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
            f"미세먼지 API 오류: "
            f"{header.get('resultMsg', '원인을 확인할 수 없음')}"
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

    response = requests.get(
        METAL_API_URL, params=params, timeout=25
    )
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
            f"금속 성분 API 오류: "
            f"{header.get('message', '원인을 확인할 수 없음')}"
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
        df["VALUE"] = pd.to_numeric(
            df["VALUE"], errors="coerce"
        )

    if "SDATE" in df.columns:
        df = df.sort_values("SDATE")

    return df


def csv_bytes(df):
    return df.to_csv(
        index=False, encoding="utf-8-sig"
    ).encode("utf-8-sig")


st.title("🌫️ 미세먼지·금속 성분 분석")
st.caption(
    "공공데이터 API를 활용해 대기오염 농도와 "
    "금속 성분 측정값을 살펴보는 탐구 앱"
)

air_key = get_secret("AIRKOREA_API_KEY")
metal_key = get_secret("METAL_API_KEY")

with st.sidebar:
    st.header("🔎 조회 설정")
    section = st.radio(
        "분석할 데이터",
        [
            "미세먼지 농도",
            "금속 성분 측정 결과",
            "화학 개념 알아보기",
        ],
    )

    st.divider()
    st.caption(
        "API 키는 코드에 직접 입력하지 말고 "
        "Streamlit Secrets에 저장해 줘."
    )


if section == "미세먼지 농도":
    st.subheader("미세먼지 농도 조회")

    if not air_key:
        st.warning(
            "AIRKOREA_API_KEY가 없어. "
            "Streamlit Cloud의 Secrets에 등록해 줘."
        )
    else:
        with st.form("air_form"):
            station = st.text_input(
                "측정소 이름", value="종로구"
            )

            period = st.selectbox(
                "조회 기간",
                ["일간", "월간", "3개월"],
            )

            term_map = {
                "일간": "DAILY",
                "월간": "MONTH",
                "3개월": "3MONTH",
            }

            air_submit = st.form_submit_button(
                "미세먼지 조회", type="primary"
            )

        if air_submit:
            try:
                with st.spinner("데이터 조회 중..."):
                    df = fetch_air_data(
                        air_key,
                        station.strip(),
                        term_map[period],
                    )

                st.session_state["air_df"] = df
                st.session_state["air_station"] = station

            except Exception as exc:
                st.error(f"미세먼지 조회 실패: {exc}")

        air_df = st.session_state.get("air_df")

        if air_df is not None:
            if air_df.empty:
                st.info("조회된 자료가 없어.")
            else:
                st.success(
                    f"조회 자료: {len(air_df)}건"
                )

                if "dataTime" in air_df.columns:
                    chart_df = air_df.sort_values(
                        "dataTime"
                    ).set_index("dataTime")

                    columns = [
                        c for c in ("pm10Value", "pm25Value")
                        if c in chart_df.columns
                    ]

                    if columns:
                        st.markdown("### 미세먼지 농도 변화")
                        st.line_chart(chart_df[columns])

                col1, col2 = st.columns(2)

                for container, column, label in [
                    (col1, "pm10Value", "PM10"),
                    (col2, "pm25Value", "PM2.5"),
                ]:
                    if column in air_df.columns:
                        values = air_df[column].dropna()
                        value = (
                            f"{values.iloc[0]:g} µg/m³"
                            if not values.empty
                            else "자료 없음"
                        )
                        container.metric(label, value)

                st.markdown("### 조회 자료")
                st.dataframe(
                    air_df,
                    use_container_width=True,
                    hide_index=True,
                )

                st.download_button(
                    "📥 미세먼지 CSV 다운로드",
                    data=csv_bytes(air_df),
                    file_name="air_quality_data.csv",
                    mime="text/csv",
                )

                st.caption(
                    "표시된 값은 API가 반환한 측정값이야. "
                    "측정 시각과 함께 확인해 줘."
                )


elif section == "금속 성분 측정 결과":
    st.subheader("대기 중 금속 성분 측정 결과")

    st.write(
        "날짜와 측정소·성분 코드를 입력해 측정 자료를 조회해."
    )

    if not metal_key:
        st.warning(
            "METAL_API_KEY가 없어. "
            "Streamlit Cloud의 Secrets에 등록해 줘."
        )
    else:
        with st.form("metal_form"):
            selected_date = st.date_input(
                "측정 날짜",
                value=date(2017, 12, 8),
                max_value=date.today(),
            )

            col1, col2 = st.columns(2)

            station_code = col1.text_input(
                "측정소 코드", value="1"
            )
            item_code = col2.text_input(
                "성분 코드", value="90303"
            )

            time_code = st.selectbox(
                "시간 구분",
                ["RH02", "RH24"],
                format_func=lambda x: (
                    "RH02 (2시간 평균)"
                    if x == "RH02"
                    else "RH24 (24시간 평균)"
                ),
            )

            metal_submit = st.form_submit_button(
                "금속 성분 조회", type="primary"
            )

        if metal_submit:
            try:
                with st.spinner("금속 성분 자료 조회 중..."):
                    df = fetch_metal_data(
                        metal_key,
                        selected_date,
                        station_code,
                        item_code,
                        time_code,
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
                f"조회 날짜: {info.get('date', '-')} / "
                f"측정소 코드: {info.get('station', '-')} / "
                f"성분 코드: {info.get('item', '-')} / "
                f"시간 구분: {info.get('time', '-')}"
            )

            if metal_df.empty:
                st.info(
                    "해당 조건의 자료가 없어. "
                    "날짜나 코드를 바꿔서 조회해 줘."
                )
            else:
                st.success(
                    f"금속 성분 측정 자료 "
                    f"{len(metal_df)}건을 불러왔어."
                )

                if (
                    "SDATE" in metal_df.columns
                    and "VALUE" in metal_df.columns
                ):
                    plot_df = metal_df.dropna(
                        subset=["SDATE", "VALUE"]
                    ).set_index("SDATE")

                    if not plot_df.empty:
                        st.markdown("### 측정 시각별 측정값")
                        st.line_chart(plot_df[["VALUE"]])

                    values = metal_df["VALUE"].dropna()

                    c1, c2, c3 = st.columns(3)
                    c1.metric("자료 수", f"{len(values)}건")
                    c2.metric(
                        "평균값",
                        f"{values.mean():.4g}"
                        if not values.empty else "자료 없음",
                    )
                    c3.metric(
                        "최댓값",
                        f"{values.max():.4g}"
                        if not values.empty else "자료 없음",
                    )

                st.markdown("### 원본 측정 자료")
                st.dataframe(
                    metal_df,
                    use_container_width=True,
                    hide_index=True,
                )

                st.download_button(
                    "📥 금속 성분 CSV 다운로드",
                    data=csv_bytes(metal_df),
                    file_name="metal_measurement_data.csv",
                    mime="text/csv",
                )

                st.caption(
                    "VALUE의 단위와 ITEMCODE의 금속 이름은 "
                    "공식 API 설명이나 코드표에서 확인해 줘."
                )


else:
    st.subheader("🧪 화학 개념 알아보기")

    st.markdown(
        """
### 1. 미세먼지와 초미세먼지

- **PM10**은 공기역학적 직경이 10 µm 이하인 입자상 물질을 뜻해.
- **PM2.5**는 공기역학적 직경이 2.5 µm 이하인 입자상 물질을 뜻해.
- 미세먼지는 여러 물질이 섞인 혼합물이야.

### 2. 금속 성분 측정이 필요한 이유

- 대기 입자에는 금속을 포함한 여러 성분이 존재할 수 있어.
- 금속 성분 자료를 미세먼지 농도와 함께 살펴보면 대기오염 특성을 더 구체적으로 탐구할 수 있어.
- 두 자료의 측정소, 날짜, 시간, 단위가 서로 맞는지 확인해야 해.

### 3. 자료를 해석할 때 주의할 점

- 값이 높다고 특정 오염원이 원인이라고 바로 결론 내릴 수는 없어.
- 성분 코드와 측정 단위는 공식 API 설명이나 코드표에서 확인해야 해.
- 자료가 없다는 것이 농도가 0이라는 뜻은 아니야.

### 탐구 질문

**미세먼지 농도 변화와 특정 금속 성분 측정값은 어떤 관계를 보일까?**

같은 날짜와 시간대의 자료를 모아 그래프로 비교하고,
관찰한 경향과 자료의 한계를 함께 정리해 볼 수 있어.
        """
    )


st.divider()
st.caption(
    "자료 출처: AirKorea 및 공공데이터포털 금속 성분 측정 API"
)
