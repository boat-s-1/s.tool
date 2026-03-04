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

# カスタムCSS
st.markdown("""
    <style>
    .stMetric { background-color: #ffffff; padding: 15px; border-radius: 10px; border: 1px solid #eee; }
    .boat-box { padding: 10px; border-radius: 8px; text-align: center; font-weight: bold; margin-bottom: 10px; border: 1px solid #dee2e6; }
    .stTabs [data-baseweb="tab-list"] { gap: 24px; }
    .stTabs [data-baseweb="tab"] { height: 50px; white-space: pre-wrap; background-color: #f0f2f6; border-radius: 5px 5px 0 0; padding: 10px 20px; }
    .stTabs [aria-selected="true"] { background-color: #ff4b4b; color: white; }
    </style>
""", unsafe_allow_html=True)

# Google Sheets 認証
@st.cache_resource
def get_gspread_client():
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scopes)
    return gspread.authorize(creds)

try:
    gc = get_gspread_client()
except Exception as e:
    st.error(f"⚠️ Google Sheets接続エラー: {e}")
    st.stop()

# ==========================================
# 2. 便利関数
# ==========================================
get_symbol = lambda val: {6: "◎", 5: "○", 4: "▲", 3: "△", 2: "×", 1: "・", 0: "無"}.get(val, "無")
boat_bg = {1: "#ffffff", 2: "#333333", 3: "#e03131", 4: "#1971c2", 5: "#fcc419", 6: "#2f9e44"}
boat_tx = {1: "#000000", 2: "#ffffff", 3: "#ffffff", 4: "#ffffff", 5: "#000000", 6: "#ffffff"}

# ==========================================
# 3. サイドバー
# ==========================================
with st.sidebar:
    st.title("🎯 設定パネル")
    r_place = st.selectbox("📍 開催地", ["桐生", "戸田", "江戸川", "平和島", "多摩川", "浜名湖", "蒲郡", "常滑", "津", "三国", "びわこ", "住之江", "尼崎", "鳴門", "丸亀", "児島", "宮島", "徳山", "下関", "若松", "芦屋", "福岡", "佐賀", "大村"])
    r_num = st.number_input("🏁 レース番号", 1, 12, 1)
    race_type_val = st.radio("📊 解析対象", ["混合", "女子"], horizontal=True)
    
    st.divider()
    target_sheet = f"{r_place}_{race_type_val}統計"
    if st.button("🔄 スプレッドシートを取得", use_container_width=True, type="primary"):
        with st.spinner("通信中..."):
            try:
                sh = gc.open_by_key("1lN794iGtyGV2jNwlYzUA8wEbhRwhPM7FxDAkMaoJss4")
                ws = sh.worksheet(target_sheet)
                data = ws.get_all_records()
                st.session_state["base_df"] = pd.DataFrame(data)
                st.success(f"✅ {len(data)}件 取得完了")
            except:
                st.error(f"「{target_sheet}」が見つかりません。")

# ==========================================
# 4. メイン画面
# ==========================================
st.title(f"📊 {r_place} {r_num}R Pro Analytica")

tab_analytica, tab_sns = st.tabs(["🔍 統計解析 & 当日予想", "🖼️ SNS画像生成"])

with tab_analytica:
    col_l, col_r = st.columns([1, 1.5])

    # --- 左側：統計解析エリア ---
    with col_l:
        st.subheader("🤖 最適配点の算出")
        if "base_df" in st.session_state:
            if st.button("📈 過去の実績から重みを計算", use_container_width=True):
                df_base = st.session_state["base_df"]
                df_base.columns = [c.strip() for c in df_base.columns]
                target_cols = ["展示", "直線", "回り足", "一周", "ST"]
                avail = [c for c in target_cols + ["着順"] if c in df_base.columns]
                work_df = df_base[avail].copy()
                if "着順" in work_df.columns:
                    work_df["着順"] = work_df["着順"].astype(str).str.replace('S', '').replace('NULL', '')
                for col in work_df.columns:
                    work_df[col] = pd.to_numeric(work_df[col], errors='coerce')
                work_df = work_df.fillna(work_df.mean())
                clean_df = work_df[work_df["着順"] > 0]
                
                if len(clean_df) >= 2:
                    corrs = {}
                    for col in target_cols:
                        if col in clean_df.columns:
                            val = abs(clean_df[col].corr(clean_df["着順"]))
                            corrs[col] = val if pd.notna(val) and val != 0 else 0.01
                        else:
                            corrs[col] = 0.01
                    total = sum(corrs.values())
                    st.session_state["auto_weights"] = {k: v/total for k, v in corrs.items()}
                    st.success(f"✅ 解析完了")
            
            if "auto_weights" in st.session_state:
                aw = st.session_state["auto_weights"]
                fig = px.pie(names=list(aw.keys()), values=list(aw.values()), hole=0.4)
                st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("サイドバーからデータを読み込んでください")

    # --- 右側：当日予想入力エリア ---
    with col_r:
        st.subheader("📝 直前気配入力")
        with st.form("input_form"):
            results = []
            # 1-2, 3-4, 5-6の順で表示されるよう2列構成を3回繰り返す
            for row_idx in range(3):
                row_cols = st.columns(2)
                for col_idx in range(2):
                    boat_num = row_idx * 2 + col_idx + 1
                    with row_cols[col_idx]:
                        st.markdown(f'<div class="boat-box" style="background:{boat_bg[boat_num]}; color:{boat_tx[boat_num]};">{boat_num}号艇</div>', unsafe_allow_html=True)
                        m = st.select_slider(f"モーター_{boat_num}", range(7), 3, get_symbol, key=f"m_{boat_num}")
                        t = st.select_slider(f"当地勝率_{boat_num}", range(7), 3, get_symbol, key=f"t_{boat_num}")
                        w = st.select_slider(f"枠番勝率_{boat_num}", range(7), 3, get_symbol, key=f"w_{boat_num}")
                        s = st.select_slider(f"枠スタート_{boat_num}", range(7), 3, get_symbol, key=f"s_{boat_num}")
                        
                        score = (m*0.25 + t*0.2 + w*0.3 + s*0.25)
                        results.append({"艇番": boat_num, "score": score, "モーター": m, "当地勝率": t, "枠番勝率": w, "枠番スタート": s})

            submitted = st.form_submit_button("🔥 解析確定", use_container_width=True, type="primary")

        if submitted:
            df = pd.DataFrame(results)
            if df["score"].sum() > 0:
                df["予想％"] = (df["score"] / df["score"].sum() * 100).round(1)
                st.session_state["analytica_result"] = df
                st.success("解析完了！")
                
                disp = df.copy()
                for c in ["モーター", "当地勝率", "枠番勝率", "枠番スタート"]:
                    disp[c] = disp[c].apply(get_symbol)
                disp["艇番"] = disp["艇番"].apply(lambda x: f"{int(x)}号艇")
                st.dataframe(disp[["艇番", "予想％", "モーター", "当地勝率", "枠番勝率", "枠番スタート"]], use_container_width=True, hide_index=True)

with tab_sns:
    st.subheader("🖼️ 画像生成")
    if "analytica_result" in st.session_state:
        st.info("SNS用の画像を準備します。")
    else:
        st.warning("先に「当日予想」を確定させてください。")
