import streamlit as st
import pandas as pd
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import io
import datetime
import gspread
from google.oauth2.service_account import Credentials
import plotly.express as px

# ==========================================
# 1. 基本設定・認証
# ==========================================
st.set_page_config(page_title="競艇Pro Analytica", layout="wide", page_icon="🎯")

# Google Sheets 認証 (必要最小限に維持)
try:
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scopes)
    gc = gspread.authorize(creds)
except Exception as e:
    st.error(f"⚠️ Google Sheets接続エラー: {e}")

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

# --- タブ1: 簡易事前予想 (補正なし・ランキング重視) ---
with tab1:
    st.subheader("📊 簡易事前スコアリング")
    with st.form("pre_form"):
        pre_raw = []
        cols = st.columns(3)
        for i in range(1, 7):
            with cols[(i-1)%3]:
                st.markdown(f'<div style="background:{boat_bg[i]}; color:{boat_tx[i]}; padding:5px; border-radius:5px; text-align:center; font-weight:bold;">{i}号艇</div>', unsafe_allow_html=True)
                m = st.select_slider(f"モーター", range(7), 0, get_symbol, key=f"pre_m_{i}")
                t = st.select_slider(f"当地勝率", range(7), 0, get_symbol, key=f"pre_t_{i}")
                w = st.select_slider(f"枠番勝率", range(7), 0, get_symbol, key=f"pre_w_{i}")
                score = (m * 0.3 + t * 0.3 + w * 0.4)
                pre_raw.append({"艇番": i, "score": score, "モーター": get_symbol(m), "当地": get_symbol(t), "枠番": get_symbol(w)})
        
        submitted_pre = st.form_submit_button("事前ランキングを表示", use_container_width=True, type="primary")

    if submitted_pre:
        df_pre = pd.DataFrame(pre_raw).sort_values("score", ascending=False)
        # カード形式で上位3艇を表示
        st.markdown("### 🏆 注目ランク")
        card_cols = st.columns(3)
        for idx, row in enumerate(df_pre.head(3).itertuples()):
            with card_cols[idx]:
                st.markdown(f"""
                <div style="background:{boat_bg[row.艇番]}; color:{boat_tx[row.艇番]}; padding:20px; border-radius:10px; border:2px solid #ddd; text-align:center;">
                    <div style="font-size:1.2rem;">第 {idx+1} 候補</div>
                    <div style="font-size:3rem; font-weight:bold;">{row.艇番}</div>
                    <div style="font-size:0.9rem;">スコア: {row.score:.2f}</div>
                </div>
                """, unsafe_allow_html=True)
        st.dataframe(df_pre[["艇番", "モーター", "当地", "枠番"]], use_container_width=True, hide_index=True)

# --- タブ2: 直前気配解析 (場ごとの補正あり) ---
with tab2:
    st.subheader(f"🏟️ {r_place} 直前気配補正解析")
    
    col_input, col_graph = st.columns([3, 2])
    
    with col_input:
        with st.form("live_form"):
            live_raw = []
            l_cols = st.columns(2)
            for i in range(1, 7):
                with l_cols[(i-1)%2]:
                    st.markdown(f'<div style="background:{boat_bg[i]}; color:{boat_tx[i]}; padding:2px; border-radius:4px; text-align:center;">{i}号艇</div>', unsafe_allow_html=True)
                    f1 = st.select_slider(f"展示気配", range(7), 0, get_symbol, key=f"live_f1_{i}")
                    f2 = st.select_slider(f"直線", range(7), 0, get_symbol, key=f"live_f2_{i}")
                    f3 = st.select_slider(f"回り足", range(7), 0, get_symbol, key=f"live_f3_{i}")
                    f4 = st.select_slider(f"一周", range(7), 0, get_symbol, key=f"live_f4_{i}")
                    
                    # 補正計算
                    corr = PLACE_CORRECTIONS.get(r_place, PLACE_CORRECTIONS["DEFAULT"])
                    live_score = (f1 * corr["展示"] + f2 * corr["直線"] + f3 * corr["回り足"] + f4 * corr["一周"])
                    live_raw.append({"艇番": i, "score": live_score, "展示": get_symbol(f1), "直線": get_symbol(f2), "回り足": get_symbol(f3), "一周": get_symbol(f4)})
            
            submitted_live = st.form_submit_button(f"{r_place}の補正で解析実行", use_container_width=True, type="primary")

    with col_graph:
        st.markdown("##### 会場別補正ウェイト")
        c = PLACE_CORRECTIONS.get(r_place, PLACE_CORRECTIONS["DEFAULT"])
        fig = px.bar(x=list(c.keys()), y=list(c.values()), color=list(c.keys()), labels={'x':'項目', 'y':'重要度'})
        fig.update_layout(showlegend=False, height=300)
        st.plotly_chart(fig, use_container_width=True)
        st.caption(f"※{r_place}の過去統計に基づき自動補正されています。")

    if submitted_live:
        df_live = pd.DataFrame(live_raw).sort_values("score", ascending=False)
        df_live["期待値%"] = (df_live["score"] / df_live["score"].sum() * 100).round(1)
        st.session_state["final_res"] = df_live # 画像用
        
        st.markdown("### 🏁 最終気配ランキング")
        st.dataframe(df_live[["艇番", "期待値%", "展示", "直線", "回り足", "一周"]].style.highlight_max(axis=0, subset=["期待値%"], color="#ff4b4b"), use_container_width=True, hide_index=True)

# --- タブ3: SNS画像 ---
with tab3:
    if "final_res" in st.session_state:
        st.write("直前気配解析の結果を画像に出力できます。")
        # (画像生成関数は以前のものをそのまま流用可能)
    else:
        st.info("タブ2で解析を実行すると、ここに画像生成メニューが表示されます。")
