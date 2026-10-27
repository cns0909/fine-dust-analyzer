import streamlit as st
import requests
import pandas as pd
from datetime import date, timedelta
from urllib.parse import unquote

# --------------------------------------------------
# 기본 설정
# --------------------------------------------------
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
    """API 키를 URL 인코딩 문제 없이 전달하도록 정리."""
    if not key:
        return ""
    key = str(key).strip()
    # data.go.kr의 일반 인증키가 이미 URL 인코딩되어 Secrets에 저장된 경우 처리
    return unquote(key)


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
            f"미세먼지 API 오류: {header.get('resultMsg', '원인을 확인할 수 없음')}"
        )

    items = root.get("body", {}).get("items", [])
    if items is None:
        items = []
    if isinstance(items, dict):
        items = [items]
    df = pd.DataFrame(items)
    if df.empty:
        return df

    for col in ("pm10Value", "pm25Value", "pm10Value24", "pm25Value24"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    if "dataTime" in df.columns:
        df["dataTime"] = pd.to_datetime(df["dataTime"], errors="coerce")

    return df


def fetch_metal_data(api_key, selected_date, station_code, item_code, time_code):
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
