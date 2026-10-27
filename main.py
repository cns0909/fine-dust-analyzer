
import streamlit as st
import requests
import pandas as pd
from urllib.parse import unquote

st.set_page_config(
    page_title="미세먼지 분석 도우미",
    page_icon="🌿",
    layout="wide"
)

API_URL = (
    "https://apis.data.go.kr/B552584/"
    "ArpltnInforInqireSvc/getMsrstnAcctoRltmMesureDnsty"
)


def get_grade(value, pollutant):
    """농도를 기준으로 대기질 등급을 구분한다."""
    if pd.isna(value):
        return "측정값 없음"

    if pollutant == "PM10":
        limits = [30, 80, 150]
    else:
        limits = [15, 35, 75]

    if value <= limits[0]:
        return "좋음"
    elif value <= limits[1]:
        return "보통"
    elif value <= limits[2]:
        return "나쁨"
    return "매우 나쁨"


def get_advice(pm10, pm25):
    """측정값에 따른 일반적인 대기질 안내."""
    grades = [
        get_grade(pm10, "PM10"),
        get_grade(pm25, "PM25")
    ]

    if "매우 나쁨" in grades:
        return "미세먼지 농도가 매우 높아요. 외부 활동을 줄이고 공식 대기질 안내를 확인하세요."
    elif "나쁨" in grades:
        return "미세먼지 농도가 높아요. 장시간 야외 활동을 줄이고 대기질 정보를 확인하세요."
    elif "보통" in grades:
        return "현재 측정값은 보통 수준이에요. 대기질 변화를 확인하세요."
    elif "좋음" in grades:
        return "측정된 미세먼지 농도가 낮은 편이에요."
    return "측정값이 부족해 상태를 판단하기 어려워요."


def fetch_data(api_key, station, period):
    # URL Encode 키를 입력받았어도 정상적으로 요청하도록 처리
    api_key = unquote(api_key.strip())

    params = {
        "serviceKey": api_key,
        "returnType": "json",
        "numOfRows": 100,
        "pageNo": 1,
        "stationName": station.strip(),
        "dataTerm": period,
        "ver": "1.0"
    }

    response = requests.get(
        API_URL,
        params=params,
        timeout=20
    )
    response.raise_for_status()

    result = response.json()
    body = result.get("response", {}).get("body", {})
    header = result.get("response", {}).get("header", {})

    result_code = str(header.get("resultCode", ""))

    if result_code and result_code != "00":
        message = header.get("resultMsg", "API 요청 오류")
        raise ValueError(f"{result_code}: {message}")

    items = body.get("items", [])

    if isinstance(items, dict):
        items = [items]

    if not items:
        return pd.DataFrame()

    df = pd.DataFrame(items)

    for column in ["pm10Value", "pm25Value"]:
        if column not in df.columns:
            df[column] = None

        df[column] = pd.to_numeric(
            df[column].replace("-", None),
            errors="coerce"
        )

    if "dataTime" in df.columns:
        df["dataTime"] = pd.to_datetime(
            df["dataTime"],
            errors="coerce"
        )

    df = df.dropna(subset=["dataTime"])
    df = df.sort_values("dataTime")

    return df


st.title("🌿 미세먼지 분석 도우미")
st.write(
    "에어코리아 API의 측정 자료를 이용해 "
    "미세먼지와 초미세먼지의 농도를 분석합니다."
)
st.caption("자료 출처: 한국환경공단 에어코리아 OpenAPI")

st.divider()

with st.sidebar:
    st.header("🔎 검색 설정")

    station = st.text_input(
        "측정소 이름",
        value="종로구",
        help="예: 종로구. 실제 측정소 이름을 입력하세요."
    )

    period_label = st.selectbox(
        "조회 기간",
        ["최근 1일", "최근 1개월", "최근 3개월"]
    )

    period_map = {
        "최근 1일": "DAILY",
        "최근 1개월": "MONTH",
        "최근 3개월": "3MONTH"
    }

    st.caption(
        "조회 가능한 기간과 자료 수는 API 제공 조건에 따라 달라질 수 있어요."
    )

    search_button = st.button(
        "미세먼지 조회",
        type="primary",
        use_container_width=True
    )

if search_button:
    if not station.strip():
        st.warning("측정소 이름을 입력해 주세요.")
    elif "AIRKOREA_API_KEY" not in st.secrets:
        st.error(
            "API 인증키가 설정되지 않았어요. "
            "Streamlit Cloud의 Settings → Secrets에 인증키를 등록해 주세요."
        )
    else:
        try:
            with st.spinner("측정 자료를 불러오는 중이에요..."):
                df = fetch_data(
                    st.secrets["AIRKOREA_API_KEY"],
                    station,
                    period_map[period_label]
                )

            if df.empty:
                st.warning(
                    "조회된 자료가 없어요. "
                    "측정소 이름이나 조회 기간을 확인해 주세요."
                )
            else:
                st.session_state["air_data"] = df
                st.session_state["air_station"] = station.strip()

        except requests.exceptions.Timeout:
            st.error("서버 응답 시간이 초과되었어요. 잠시 후 다시 시도해 주세요.")
        except requests.exceptions.HTTPError as e:
            st.error(f"HTTP 오류가 발생했어요: {e}")
        except requests.exceptions.RequestException:
            st.error("인터넷 연결이나 API 서버를 확인해 주세요.")
        except (ValueError, KeyError) as e:
            st.error(f"자료를 처리하지 못했어요: {e}")
        except Exception:
            st.error(
                "예상하지 못한 오류가 발생했어요. "
                "인증키와 API 신청 상태를 확인해 주세요."
            )

if "air_data" in st.session_state:
    df = st.session_state["air_data"].copy()
    station_name = st.session_state["air_station"]

    latest = df.iloc[-1]
    pm10 = latest["pm10Value"]
    pm25 = latest["pm25Value"]

    st.subheader(f"📍 {station_name} 측정 결과")
    st.caption(
        "최근 측정 시각: "
        + latest["dataTime"].strftime("%Y-%m-%d %H:%M")
    )

    col1, col2 = st.columns(2)

    with col1:
        st.metric(
            "미세먼지 PM10",
            f"{pm10:.0f} µg/m³" if pd.notna(pm10) else "측정값 없음"
        )
        st.write(
            f"등급: **{get_grade(pm10, 'PM10')}**"
        )

    with col2:
        st.metric(
            "초미세먼지 PM2.5",
            f"{pm25:.0f} µg/m³" if pd.notna(pm25) else "측정값 없음"
        )
        st.write(
            f"등급: **{get_grade(pm25, 'PM25')}**"
        )

    st.info(get_advice(pm10, pm25))

    st.divider()
    st.subheader("📈 시간별 농도 변화")

    chart_df = df.set_index("dataTime")[
        ["pm10Value", "pm25Value"]
    ].rename(
        columns={
            "pm10Value": "PM10 미세먼지",
            "pm25Value": "PM2.5 초미세먼지"
        }
    )

    st.line_chart(chart_df, height=350)
    st.caption("※ 두 측정값은 모두 µg/m³ 단위이며, 세로축은 농도를 나타냅니다.")

    st.subheader("📋 측정 자료")

    table_df = df[["dataTime", "pm10Value", "pm25Value"]].copy()
    table_df.columns = ["측정 시각", "PM10 (µg/m³)", "PM2.5 (µg/m³)"]
    table_df = table_df.sort_values("측정 시각", ascending=False)

    st.dataframe(table_df, use_container_width=True)

    csv_data = table_df.to_csv(
        index=False
    ).encode("utf-8-sig")

    st.download_button(
        "📥 측정 자료 CSV 다운로드",
        data=csv_data,
        file_name="airkorea_measurements.csv",
        mime="text/csv"
    )

    st.caption(
        "참고: 이 프로그램은 측정 농도를 보여 줍니다. "
        "화학적 성분의 종류나 함량은 이 자료만으로 알 수 없습니다."
    )

else:
    st.info(
        "왼쪽에서 측정소 이름과 조회 기간을 선택한 다음 "
        "'미세먼지 조회'를 눌러 주세요."
    )

st.divider()
st.caption(
    "본 프로그램은 교육용이며, 측정값은 측정소와 시간에 따라 달라질 수 있습니다."
)
