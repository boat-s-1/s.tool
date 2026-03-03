import streamlit as st
import pandas as pd
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import io
import datetime
import plotly.express as px

# ==========================================
# 1. 基本設定
# ==========================================
st.set_page_config(page_title="競艇Pro Analytica", layout="wide", page_icon="🎯")

# 会場別特性補正値（タブ2用）
PLACE_CORRECTIONS = {
    "桐生": {"展示": 0.2, "直線": 0.2, "回り足": 0.3, "一周": 0.3},
    "戸田": {"展示": 0.1, "直線": 0.5, "回り足": 0.2, "一周": 0.2},
    "江戸川": {"展示": 0.1, "直線": 0.2, "回り足": 0.5, "一周": 0.2},
    "福岡": {"展示": 0.1, "直線": 0.2, "回り足": 0.5, "一周": 0.2},
    "住之江": {"展示": 0.4, "直線": 0.1, "回り足": 0.3, "一周": 0.2},
    "大村": {"展示": 0.5, "直線": 0.1, "回り足": 0.2, "一周": 0.2},
    "DEFAULT": {"展示": 0.25, "直線": 0.25, "回り足": 0.25, "一周": 0.25}
}

# 共通デザイン設定
get_symbol = lambda val: {6: "◎", 5: "○", 4: "▲", 3: "△", 2: "×", 1: "・", 0: "無"}.get(val, "無")
boat_bg = {1: "#ffffff", 2: "#333333", 3: "#e03131", 4: "#1971c2", 5: "#fcc419", 6: "#2f9e44"}
boat_tx = {1: "#000000", 2: "#ffffff", 3: "#ffffff", 4: "#ffffff", 5: "#000000", 6: "#ffffff"}

# ==========================================
# 2. サイドバー
# ==========================================
with st.sidebar:
    st.header("📋 レース情報")
    r_place = st.selectbox("開催地", ["桐生", "戸田", "江戸川", "平和島", "多摩川", "浜名湖", "蒲郡", "常滑", "津", "三国", "びわこ", "住之江", "尼崎", "鳴門", "丸亀", "児島", "宮島", "徳山", "下関", "若松", "芦屋", "福岡", "佐賀", "大村"])
    r_num = st.number_input("レース番号", 1, 12, 12)
    st.divider()
    st.info(f"現在の設定: {r_place} {r_num}R")

# ==========================================
# 3. メインレイアウト
# ==========================================
tab1, tab2, tab3 = st.tabs(["📝 簡易事前予想", "🔥 直前気配解析", "🖼️ SNS画像"])

# --- タブ1: 簡易事前予想 (4項目構成) ---
with tab1:
    st.subheader("📊 事前データスコアリング")
    st.caption("モーター、勝率、スタートタイミングから総合的な実力を算出します。")
    
    with st.form("pre_form"):
        pre_raw = []
        # 3列2行で6艇分を表示
        cols = st.columns(3)
        for i in range(1, 7):
            with cols[(i-1)%3]:
                # 艇番ヘッダー
                st.markdown(f'''
                    <div style="background:{boat_bg[i]}; color:{boat_tx[i]}; padding:8px; border-radius:5px 5px 0 0; text-align:center; font-weight:bold; border:1px solid #ddd;">
                        {i}号艇
                    </div>
                ''', unsafe_allow_html=True)
                
                # 入力エリア（枠囲み）
                with st.container():
                    m = st.select_slider(f"🚀 モーター", range(7), 0, get_symbol, key=f"pre_m_{i}")
                    t = st.select_slider(f"🏝️ 当地勝率", range(7), 0, get_symbol, key=f"pre_t_{i}")
                    w = st.select_slider(f"📈 枠番勝率", range(7), 0, get_symbol, key=f"pre_w_{i}")
                    s = st.select_slider(f"⏱️ 枠番ST", range(7), 0, get_symbol, key=f"pre_s_{i}")
                    
                    # 事前予想の配分比率: モーター25%, 当地20%, 枠番勝率35%, 枠番ST20%
                    score = (m * 0.25 + t * 0.20 + w * 0.35 + s * 0.20)
                    pre_raw.append({
                        "艇番": i, 
                        "score": score, 
                        "モーター": get_symbol(m), 
                        "当地": get_symbol(t), 
                        "枠番勝率": get_symbol(w),
                        "枠番ST": get_symbol(s)
                    })
                st.markdown('<div style="margin-bottom:20px;"></div>', unsafe_allow_html=True)
        
        submitted_pre = st.form_submit_button("事前ランキングを確定", use_container_width=True, type="primary")

    if submitted_pre:
        df_pre = pd.DataFrame(pre_raw).sort_values("score", ascending=False)
        
        # 🏆 上位3艇を強調表示
        st.markdown("### 🏆 事前注目ランク")
        card_cols = st.columns(3)
        for idx, row in enumerate(df_pre.head(3).itertuples()):
            with card_cols[idx]:
                st.markdown(f"""
                <div style="background:{boat_bg[row.艇番]}; color:{boat_tx[row.艇番]}; padding:15px; border-radius:10px; border:2px solid #ddd; text-align:center; box-shadow: 2px 2px 5px rgba(0,0,0,0.1);">
                    <div style="font-size:1rem; opacity:0.8;">Rank {idx+1}</div>
                    <div style="font-size:3.5rem; font-weight:bold; line-height:1;">{row.艇番}</div>
                    <div style="font-size:1rem; margin-top:5px;">Score: {row.score:.2f}</div>
                </div>
                """, unsafe_allow_html=True)
        
        st.markdown("---")
        st.dataframe(
            df_pre[["艇番", "score", "モーター", "当地", "枠番勝率", "枠番ST"]].rename(columns={"score": "点数"}),
            use_container_width=True, 
            hide_index=True
        )

# --- タブ2: 直前気配解析 (会場補正あり) ---
with tab2:
    st.subheader(f"🏟️ {r_place} 直前気配補正解析")
    
    col_input, col_graph = st.columns([3, 2])
    
    with col_input:
        with st.form("live_form"):
            live_raw = []
            l_cols = st.columns(2)
            for i in range(1, 7):
                with l_cols[(i-1)%2]:
                    st.markdown(f'<div style="background:{boat_bg[i]}; color:{boat_tx[i]}; padding:2px; border-radius:4px; text-align:center; font-weight:
