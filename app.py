import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from scipy.signal import find_peaks
import warnings
from datetime import datetime, timedelta

warnings.filterwarnings('ignore')

# --- 페이지 설정 ---
st.set_page_config(page_title="자동 파동 & 피보나치 분석기", layout="wide")

st.title("🌊 자동 스윙 파동 & 피보나치 되돌림 스캐너")
st.markdown("수학적 알고리즘(SciPy Signal)을 이용해 1년간의 주요 파동(Swing)을 인식하고, 현재 주가가 위치한 파동의 **피보나치(Fibonacci) 지지/저항선**을 자동으로 그려줍니다.")

# --- 사이드바 설정 ---
st.sidebar.header("⚙️ 분석 설정")
ticker = st.sidebar.text_input("🔍 티커 입력 (예: AAPL, TSLA, NVDA, SPY)", value="TSLA").upper()
wave_sensitivity = st.sidebar.slider("🌊 파동 민감도 (작을수록 자잘한 파동까지 잡음)", min_value=5, max_value=40, value=15, step=1, help="며칠 동안의 고점/저점을 하나의 파동으로 인식할지 결정합니다.")

if st.sidebar.button("🚀 차트 분석 실행", type="primary"):
    with st.spinner(f"[{ticker}] 데이터를 불러오고 파동을 계산 중입니다..."):
        # 1. 1년치 데이터 수집
        end_date = datetime.today()
        start_date = end_date - timedelta(days=365)
        
        df = yf.download(ticker, start=start_date.strftime('%Y-%m-%d'), end=end_date.strftime('%Y-%m-%d'), progress=False)
        
        if df.empty:
            st.error("데이터를 불러올 수 없습니다. 티커명을 확인해 주세요. (한국 주식은 005930.KS 형식)")
        else:
            # MultiIndex 컬럼 제거 (yfinance 최신 버전 대응)
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            
            # 2. 고점/저점(스윙 파동) 탐지 알고리즘
            # 고점 찾기 (High 기준)
            peaks_idx, _ = find_peaks(df['High'].values, distance=wave_sensitivity)
            # 저점 찾기 (Low를 음수로 뒤집어서 고점 찾기 함수 적용)
            troughs_idx, _ = find_peaks(-df['Low'].values, distance=wave_sensitivity)
            
            # 고점과 저점을 하나의 리스트로 합치고 시간순으로 정렬
            pivots = []
            for idx in peaks_idx:
                pivots.append((df.index[idx], df['High'].iloc[idx], 'Peak'))
            for idx in troughs_idx:
                pivots.append((df.index[idx], df['Low'].iloc[idx], 'Trough'))
                
            pivots.sort(key=lambda x: x[0])
            
            # 연속된 Peak나 Trough가 나올 경우 필터링 (완벽한 지그재그를 위해)
            filtered_pivots = []
            if len(pivots) > 0:
                filtered_pivots.append(pivots[0])
                for i in range(1, len(pivots)):
                    if pivots[i][2] != filtered_pivots[-1][2]: # 이전과 타입이 다를 때만 추가
                        filtered_pivots.append(pivots[i])
                    else:
                        # 타입이 같으면 더 높은 고점이나 더 낮은 저점으로 갱신
                        if pivots[i][2] == 'Peak' and pivots[i][1] > filtered_pivots[-1][1]:
                            filtered_pivots[-1] = pivots[i]
                        elif pivots[i][2] == 'Trough' and pivots[i][1] < filtered_pivots[-1][1]:
                            filtered_pivots[-1] = pivots[i]

            pivot_dates = [p[0] for p in filtered_pivots]
            pivot_prices = [p[1] for p in filtered_pivots]
            pivot_types = [p[2] for p in filtered_pivots]

            # 3. 마지막 파동을 기준으로 피보나치 계산
            if len(filtered_pivots) >= 2:
                last_pivot = filtered_pivots[-1]
                prev_pivot = filtered_pivots[-2]
                
                wave_start_price = prev_pivot[1]
                wave_end_price = last_pivot[1]
                
                # 피보나치 비율 (실전에서 가장 많이 쓰이는 주요 레벨)
                fib_levels = [0.0, 0.236, 0.382, 0.5, 0.618, 0.786, 1.0]
                fib_prices = {}
                
                diff = wave_end_price - wave_start_price
                
                for level in fib_levels:
                    # 시작점에서 끝점 방향으로 되돌림 계산
                    fib_prices[level] = wave_end_price - (diff * level)
                    
                is_uptrend_wave = wave_end_price > wave_start_price
                wave_direction = "상승 파동 (Impulse Up)" if is_uptrend_wave else "하락 파동 (Impulse Down)"
                
            # 4. Plotly 차트 그리기
            fig = go.Figure()

            # 캔들스틱 추가
            fig.add_trace(go.Candlestick(
                x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'],
                name="Price", increasing_line_color='#2ecc71', decreasing_line_color='#e74c3c'
            ))

            # 파동(ZigZag) 라인 추가
            fig.add_trace(go.Scatter(
                x=pivot_dates, y=pivot_prices, mode='lines+markers+text',
                name='엘리어트 파동 (스윙)',
                line=dict(color='#f1c40f', width=2, dash='dot'),
                marker=dict(size=8, color='#f1c40f'),
                text=[f"W{i+1}" for i in range(len(pivot_dates))],
                textposition="top center" if pivot_types[0] == 'Peak' else "bottom center"
            ))

            # 피보나치 되돌림 라인 그리기 (최근 스윙 기준)
            if len(filtered_pivots) >= 2:
                colors = {0.0: '#95a5a6', 0.236: '#e74c3c', 0.382: '#e67e22', 0.5: '#f1c40f', 0.618: '#2ecc71', 0.786: '#3498db', 1.0: '#95a5a6'}
                
                for level, price in fib_prices.items():
                    fig.add_hline(
                        y=price, line_dash="dash", line_color=colors.get(level, 'white'), line_width=1,
                        annotation_text=f"Fib {level*100:.1f}% (${price:.2f})",
                        annotation_position="right",
                        annotation_font_color=colors.get(level, 'white')
                    )
                    
            fig.update_layout(
                height=700, margin=dict(l=0, r=0, t=40, b=0),
                title=f"{ticker} 1년 차트 및 피보나치 분석",
                xaxis_rangeslider_visible=False,
                template='plotly_dark',
                hovermode='x unified'
            )

            # --- 결과 대시보드 출력 ---
            st.plotly_chart(fig, use_container_width=True)
            
            if len(filtered_pivots) >= 2:
                st.subheader("📊 현재 진행 중인 파동 브리핑")
                st.info(f"현재 주가는 최근 발생한 **{wave_direction}**에 대한 **되돌림(Retracement) 또는 확장** 구간에 있습니다.")
                
                col1, col2, col3 = st.columns(3)
                curr_price = df['Close'].iloc[-1]
                col1.metric("현재가 종가", f"${curr_price:.2f}")
                col2.metric("파동 시작점 (W-1)", f"${wave_start_price:.2f}")
                col3.metric("파동 끝점 (최근 고/저점)", f"${wave_end_price:.2f}")
                
                st.markdown("##### 🎯 피보나치 주요 지지/저항 레벨")
                fib_df = pd.DataFrame({
                    "피보나치 레벨": [f"{lvl*100:.1f}%" for lvl in fib_levels],
                    "가격 ($)": [f"${price:.2f}" for price in fib_prices.values()],
                    "상태": ["현재가 위 (저항)" if price > curr_price else "현재가 아래 (지지)" for price in fib_prices.values()]
                })
                st.dataframe(fib_df, hide_index=True, use_container_width=True)
                
            else:
                st.warning("분석할 만큼의 명확한 파동(고점/저점)이 1년 내에 형성되지 않았습니다. 좌측 메뉴에서 '파동 민감도'를 낮춰보세요.")

else:
    st.info("👈 좌측 사이드바에서 티커를 입력하고 '차트 분석 실행'을 눌러주세요.")
