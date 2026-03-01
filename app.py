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
            peaks_idx, _ = find_peaks(df['High'].values, distance=wave_sensitivity)
            troughs_idx, _ = find_peaks(-df['Low'].values, distance=wave_sensitivity)
            
            pivots = []
            for idx in peaks_idx:
                pivots.append((df.index[idx], df['High'].iloc[idx], 'Peak'))
            for idx in troughs_idx:
                pivots.append((df.index[idx], df['Low'].iloc[idx], 'Trough'))
                
            pivots.sort(key=lambda x: x[0])
            
            filtered_pivots = []
            if len(pivots) > 0:
                filtered_pivots.append(pivots[0])
                for i in range(1, len(pivots)):
                    if pivots[i][2] != filtered_pivots[-1][2]: 
                        filtered_pivots.append(pivots[i])
                    else:
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
                
                fib_levels = [0.0, 0.236, 0.382, 0.5, 0.618, 0.786, 1.0]
                fib_prices = {}
                
                diff = wave_end_price - wave_start_price
                
                for level in fib_levels:
                    fib_prices[level] = wave_end_price - (diff * level)
                    
                is_uptrend_wave = wave_end_price > wave_start_price
                wave_direction = "상승 파동 (Impulse Up)" if is_uptrend_wave else "하락 파동 (Impulse Down)"
                
            # 4. Plotly 차트 그리기
            fig = go.Figure()

            fig.add_trace(go.Candlestick(
                x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'],
                name="Price", increasing_line_color='#2ecc71', decreasing_line_color='#e74c3c'
            ))

            fig.add_trace(go.Scatter(
                x=pivot_dates, y=pivot_prices, mode='lines+markers+text',
                name='엘리어트 파동 (스윙)',
                line=dict(color='#f1c40f', width=2, dash='dot'),
                marker=dict(size=8, color='#f1c40f'),
                text=[f"W{i+1}" for i in range(len(pivot_dates))],
                textposition="top center" if pivot_types[0] == 'Peak' else "bottom center"
            ))

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

            st.plotly_chart(fig, use_container_width=True)
            
            # --- 결과 대시보드 및 AI 코멘트 출력 ---
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
                
                # --- 🔥 핵심 추가: AI 시사점 도출 로직 ---
                st.divider()
                st.subheader("🤖 AI 트레이딩 코멘트 및 시사점")
                
                # 현재 가격이 전체 파동 대비 몇 % 되돌림 위치인지 수학적으로 역산
                ret_ratio = (wave_end_price - curr_price) / diff
                
                if is_uptrend_wave:
                    if ret_ratio < 0:
                        comment = "🔥 **추세 연장 (Extension):** 최근 고점을 돌파하며 새로운 상승 파동을 써내려가고 있습니다. 상승 모멘텀이 매우 강한 상태로, 기존 보유자는 수익을 극대화(Trailing Stop)하는 전략이 유효합니다."
                    elif ret_ratio <= 0.382:
                        comment = "📈 **건전한 조정 (Healthy Pullback):** 상승장 속의 가벼운 눌림목 구간입니다. 0.236 ~ 0.382 라인에서 지지를 받는다면 훌륭한 단기 매수(롱) 타점이 될 수 있습니다."
                    elif ret_ratio <= 0.618:
                        comment = "⭐ **핵심 지지 구간 (Golden Zone):** 엘리어트 파동 이론상 2파 또는 4파의 저점이 형성될 확률이 가장 높은 **0.5 ~ 0.618 황금 비율 구간**입니다. 이 구간에서 하락이 멈추고 반등 캔들(도지, 망치형 등)이 뜬다면 최적의 스윙 매수 기회입니다."
                    elif ret_ratio <= 1.0:
                        comment = "⚠️ **깊은 조정 (Deep Retracement):** 상승분의 61.8% 이상을 반납했습니다. 매수세가 상당히 약해졌으며, 이전 저점(100% 되돌림 선)이 깨지는지 주의 깊게 관찰해야 하는 리스크 관리 구간입니다."
                    else:
                        comment = "🚨 **상승 추세 붕괴 (Trend Reversal):** 이전 파동의 시작점을 하향 이탈했습니다. 기존의 상승 파동 관점은 폐기되며, 본격적인 하락 추세(A-B-C 파동) 전환을 대비해야 합니다."
                else: # 하락 파동일 경우
                    if ret_ratio < 0:
                        comment = "🧊 **하락 추세 연장 (Extension):** 최근 저점을 깨고 지하로 파고드는 중입니다. 완벽한 역배열 상태이며 섣부른 물타기(바닥 잡기)는 매우 위험합니다."
                    elif ret_ratio <= 0.382:
                        comment = "📉 **약한 기술적 반등 (Dead Cat Bounce):** 하락장 속의 가벼운 되돌림입니다. 여전히 매도 압력이 강해 다시 맞고 떨어질(추가 하락) 위험이 높습니다."
                    elif ret_ratio <= 0.618:
                        comment = "🧱 **핵심 저항 구간 (Golden Zone):** 하락 파동에 대한 기술적 반등의 최대 목표치(0.5 ~ 0.618 황금 비율) 부근입니다. 엘리어트 하락 파동 이론상 여기서 저항을 맞고 다시 더 큰 하락(3파 또는 C파)이 나올 확률이 높으므로, 비중 축소나 숏(매도) 포지션을 고려할 수 있는 핵심 저항대입니다."
                    elif ret_ratio <= 1.0:
                        comment = "☀️ **강한 반등 (Strong Recovery):** 하락분의 61.8% 이상을 회복했습니다. 매도세가 소진되고 매수세가 강하게 유입되며 추세 반전(상승)의 에너지가 모이고 있습니다."
                    else:
                        comment = "🚀 **하락 추세 종료 (Trend Reversal):** 이전 고점을 완벽히 뚫고 올라왔습니다. 기존의 하락 파동 관점은 폐기되며, 새로운 상승 1파가 시작되었을 가능성이 큽니다."
                
                # 코멘트를 눈에 띄는 박스로 출력
                if ret_ratio < 0 or ret_ratio > 1:
                    st.error(comment)
                elif ret_ratio <= 0.618 and ret_ratio > 0.382:
                    st.success(comment) # 골든존은 초록색(기회)으로 표시
                else:
                    st.warning(comment)
                    
            else:
                st.warning("분석할 만큼의 명확한 파동(고점/저점)이 1년 내에 형성되지 않았습니다. 좌측 메뉴에서 '파동 민감도'를 낮춰보세요.")

else:
    st.info("👈 좌측 사이드바에서 티커를 입력하고 '차트 분석 실행'을 눌러주세요.")
