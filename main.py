                    "표시된 값은 API가 반환한 측정값이야. 최신값의 의미는 API 응답의 정렬 순서와 측정 시각을 함께 확인해 줘."
                )

elif section == "금속 성분 측정 결과":
    st.subheader("대기 중 금속 성분 측정 결과")
    st.write(
        "날짜와 코드 값을 입력해 금속 성분 측정 자료를 조회해. "
        "성분 코드와 측정소 코드의 정확한 의미는 해당 API의 코드표에서 확인해야 해."
    )

    if not metal_key:
        st.warning(
            "METAL_API_KEY가 설정되지 않았어. "
            "Streamlit Cloud → 앱 설정(Manage app) → Secrets에 금속 API 키를 추가해 줘."
        )
    else:
        with st.form("metal_form"):
            selected_date = st.date_input(
                "측정 날짜",
                value=date(2017, 12, 8),
                min_value=date(1900, 1, 1),
                max_value=date.today(),
                help="최근 날짜에 자료가 없을 수 있어. 먼저 자료가 확인된 날짜로 테스트할 수 있어.",
            )
            col1, col2 = st.columns(2)
            station_code = col1.text_input("측정소 코드", value="1")
            item_code = col2.text_input("성분 코드", value="90303")
            time_code = st.selectbox(
                "시간 구분 코드",
                ["RH02", "RH24"],
                format_func=lambda x: (
                    "RH02 (2시간 평균)" if x == "RH02" else "RH24 (24시간 평균)"
                ),
            )
            metal_submitted = st.form_submit_button("금속 성분 조회", type="primary")

        if metal_submitted:
            if not station_code.strip() or not item_code.strip():
                st.error("측정소 코드와 성분 코드를 입력해 줘.")
            else:
                try:
                    with st.spinner("금속 성분 자료를 불러오는 중..."):
                        metal_df = fetch_metal_data(
                            metal_key,
                            selected_date,
                            station_code,
                            item_code,
                            time_code,
                        )
                    st.session_state["metal_df"] = metal_df
                    st.session_state["metal_query"] = {
                        "date": selected_date.isoformat(),
                        "station": station_code,
                        "item": item_code,
                        "time": time_code,
                    }
                except Exception as exc:
                    st.error(f"금속 성분 자료를 불러오지 못했어: {exc}")

        metal_df = st.session_state.get("metal_df")
        if metal_df is not None:
            query_info = st.session_state.get("metal_query", {})
            st.caption(
                f"조회 조건: 날짜 {query_info.get('date', '-')}, "
                f"측정소 코드 {query_info.get('station', '-')}, "
                f"성분 코드 {query_info.get('item', '-')}, "
                f"시간 구분 {query_info.get('time', '-')}"
            )
            if metal_df.empty:
                st.info("해당 조건의 자료가 없어. 날짜나 코드를 바꿔서 다시 조회해 줘.")
            else:
                st.success(f"금속 성분 측정 자료 {len(metal_df)}건을 불러왔어.")
                if "SDATE" in metal_df.columns and "VALUE" in metal_df.columns:
                    plot_df = metal_df.dropna(subset=["SDATE", "VALUE"]).set_index("SDATE")
                    if not plot_df.empty:
                        st.markdown("#### 측정 시각별 측정값")
                        st.line_chart(plot_df[["VALUE"]])
                if "VALUE" in metal_df.columns:
                    vals = metal_df["VALUE"].dropna()
                    c1, c2, c3 = st.columns(3)
                    c1.metric("자료 수", f"{len(vals)}건")
                    c2.metric("평균값", f"{vals.mean():.4g}" if len(vals) else "자료 없음")
                    c3.metric("최댓값", f"{vals.max():.4g}" if len(vals) else "자료 없음")
                st.markdown("#### 원본 측정 자료")
                st.dataframe(metal_df, use_container_width=True, hide_index=True)
                st.download_button(
                    "📥 금속 성분 CSV 다운로드",
                    data=csv_bytes(metal_df),
                    file_name="metal_measurement_data.csv",
                    mime="text/csv",
                )
                st.caption(
                    "VALUE의 단위와 ITEMCODE의 금속 이름은 코드표·API 설명에서 확인한 뒤 보고서에 적어 줘. "
                    "코드만으로 금속 종류나 단위를 추정하면 안 돼."
                )

else:
    st.subheader("🧪 화학 개념 알아보기")
    st.markdown(
        """
        ### 1. 미세먼지와 초미세먼지
        - **PM10**은 일반적으로 공기역학적 직경이 10 µm 이하인 입자상 물질을 뜻해.
        - **PM2.5**는 공기역학적 직경이 2.5 µm 이하인 더 작은 입자상 물질을 뜻해.
        - 미세먼지는 여러 물질이 섞인 혼합물이라서, 농도만으로 모든 성분을 알아낼 수는 없어.

        ### 2. 금속 성분 측정이 필요한 이유
        - 대기 입자에는 금속을 포함한 여러 성분이 존재할 수 있어.
        - 금속 성분 자료를 미세먼지 농도와 함께 살펴보면 대기오염의 특성을 더 구체적으로 탐구할 수 있어.
        - 다만 두 자료의 측정소, 날짜, 측정 시간, 단위가 서로 맞는지 먼저 확인해야 해.

        ### 3. 자료를 해석할 때 주의할 점
        - 값이 높다고 해서 특정 오염원이 원인이라고 바로 결론 내릴 수는 없어.
        - 금속 성분 코드, 측정소 코드, 시간 구분 코드, 측정 단위는 API의 공식 설명이나 코드표를 확인해야 해.
        - 날짜가 최근이어도 자료가 아직 공개되지 않았을 수 있어. 자료가 없다는 것이 농도가 0이라는 뜻은 아니야.

        ### 탐구 질문 예시
        **“미세먼지 농도 변화와 특정 금속 성분 측정값은 어떤 관계를 보일까?”**

        같은 날짜와 시간대의 자료를 모아 그래프로 비교하고, 관찰된 경향과 자료의 한계를 함께 정리해 볼 수 있어.
        """
    )

st.divider()
st.caption("자료 출처: AirKorea 및 공공데이터포털의 금속 성분 측정 API. 결과는 API의 실제 응답에 따라 달라질 수 있어.")
