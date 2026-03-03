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

# Google Sheets 認証
scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
try:
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scopes)
    gc = gspread.authorize(creds)
except Exception as e:
    st.error(f"⚠️ Google Sheets接続エラー: {e}")
    st.stop()

# --- 【重要】全24会場の特性補正値（ここを書き換えるとグラフが変わります） ---
PLACE_CORRECTIONS = {
    "桐生": {"展示": 0.2, "直線": 0.2, "回り足": 0.3, "一周": 0.3},
    "戸田": {"展示": 0.1, "直線": 0.5, "回り足": 0.2, "一周": 0.2},
    "江戸川": {"展示": 0.1, "直線": 0.2, "回り足": 0.5, "一周": 0.2},
    "平和島": {"展示": 0.2, "直線": 0.3, "回り足": 0.3, "一周": 0.2},
    "多摩川": {"展示": 0.3, "直線": 0.2, "回り足": 0.2, "一周": 0.3},
    "浜名湖": {"展示": 0.25, "直線": 0.25, "回り足": 0.25, "一周": 0.25},
    "蒲郡": {"展示": 0.3, "直線": 0.2, "回り足": 0.3, "一周": 0.2},
    "常滑": {"展示": 0.2, "直線": 0.3, "回り足": 0.3, "一周": 0.2},
    "津": {"展示": 0.25, "直線": 0.25, "回り足": 0.25, "一周": 0.25},
    "三国": {"展示": 0.2, "直線": 0.3, "回り足": 0.2, "一周": 0.3},
    "びわこ": {"展示": 0.2, "直線": 0.2, "回り足": 0.4, "一周": 0.2},
    "住之江": {"展示": 0.4, "直線": 0.1, "回り足": 0.3, "一周": 0.2},
    "尼崎": {"展示": 0.2, "直線": 0.3, "回り足": 0.3, "一周": 0.2},
    "鳴門": {"展示": 0.1, "直線": 0.4, "回り足": 0.3, "一周": 0.2},
    "丸亀": {"展示": 0.3, "直線": 0.2, "回り足": 0.3, "一周": 0.2},
    "児島": {"展示": 0.25, "直線": 0.25, "回り足": 0.25, "一周": 0.25},
    "宮島": {"展示": 0.2, "直線": 0.2, "回り足": 0.4, "一周": 0.2},
    "徳山": {"展示": 0.4, "直線": 0.2, "回り足": 0.2, "一周": 0.2},
    "下関": {"展示": 0.3, "直線": 0.2, "回り足": 0.3, "一周": 0.2},
    "若松": {"展示": 0.3, "直線": 0.2, "回り足": 0.3, "一周": 0.2},
    "芦屋": {"展示": 0.4, "直線": 0.2, "回り足": 0.2, "一周": 0.2},
    "福岡": {"展示": 0.1, "直線": 0.2, "回り足": 0.5, "一周": 0.2},
    "佐賀": {"展示": 0.3, "直線": 0.2, "回り足": 0.3, "一周": 0.2}, # 唐津
    "大村": {"展示": 0.5, "直線": 0.1, "回り足": 0.2, "一周": 0.2},
    "DEFAULT": {"展示": 0.25, "直線": 0.25, "回り足": 0.25, "一周": 0.25}
}

# ==========================================
# 2. 共通関数
# ==========================================
get_symbol = lambda val: {6: "◎", 5: "○", 4: "▲", 3: "△", 2: "×", 1: "・", 0: "無"}.get(val, "無")
boat_bg = {1: "#ffffff", 2: "#333333", 3: "#e03131", 4: "#1971c2", 5: "#fcc419", 6: "#2f9e44"}
boat_tx = {1: "#000000", 2: "#ffffff", 3: "#ffffff", 4: "#ffffff", 5: "#000000", 6: "#ffffff"}

def style_by_rank(col):
    if col.name == "艇番": return [''] * 6
    ranks = col.rank(ascending=False, method='min')
    return ['background-color: #ff4b4b; color: white;' if r==1 else 'background-color: #ffff00; color: black;' if r==2 else '' for r in ranks]

# ==========================================
# 3. サイドバー
# ==========================================
with st.sidebar:
    st.header("📋 データ設定")
    r_date = st.date_input("レース日", datetime.date.today())
    r_place = st.selectbox("開催地を選択", list(PLACE_CORRECTIONS.keys())[:-1])
    r_num = st.number_input("レース番号", 1, 12, 12)
    race_type_val = st.radio("解析データ対象", ["混合", "女子"], horizontal=True)
    
    SS_ID_1 = "1lN794iGtyGV2jNwlYzUA8wEbhRwhPM7FxDAkMaoJss4"
    SS_ID_2 = "1rSzJuk5Hyv60nMwX67pCufXz45HLykyIXuqVE6wtNII"
    
    if st.button("🔄 2つのファイルを読み込み", use_container_width=True, type="primary"):
        with st.spinner("ファイルを検索・読み込み中..."):
            try:
                target_name = f"{r_place}_{race_type_val}統計"
                df_list = []
                # ファイル1
                try:
                    sh1 = gc.open_by_key(SS_ID_1)
                    for ws in sh1.worksheets():
                        if ws.title.strip().replace("＿", "_") == target_name:
                            df1 = pd.DataFrame(ws.get_all_records())
                            if not df1.empty: df_list.append(df1); st.info(f"📍 1:「{ws.title}」読込")
                            break
                except: pass
                # ファイル2
                try:
                    sh2 = gc.open_by_key(SS_ID_2)
                    for ws in sh2.worksheets():
                        if ws.title.strip().replace("＿", "_") == target_name:
                            df2 = pd.DataFrame(ws.get_all_records())
                            if not df2.empty: df_list.append(df2); st.info(f"📁 2:「{ws.title}」読込")
                            break
                except: pass

                if df_list:
                    st.session_state["base_df"] = pd.concat(df_list, ignore_index=True)
                    # 会場が変わったら前回の解析結果を一度クリア
                    if "auto_weights" in st.session_state: del st.session_state["auto_weights"]
                    st.success(f"✅ 合計 {len(st.session_state['base_df'])} 件 読込完了")
                else:
                    st.error(f"❌ {target_name} が見つかりません。")
            except Exception as e:
                st.error(f"失敗: {e}")

# ==========================================
# 4. メインエリア
# ==========================================
st.title(f"📊 {r_place} Pro Analytica")
tab1, tab2, tab3 = st.tabs(["🔍 統計解析予想", "🎯 直感気配解析", "🖼️ SNS画像生成"])

# --- タブ1: 統計解析予想 ---
with tab1:
    col_left, col_right = st.columns([2, 3])
    with col_left:
        st.subheader("🤖 統計データ重み算出")
        if "base_df" in st.session_state:
            # 解析実行ボタン
            if st.button("📈 過去データから重みを抽出", use_container_width=True, type="primary"):
                with st.spinner("膨大なデータを解析中..."):
                    df = st.session_state["base_df"].copy()
                    target = ["展示", "直線", "回り足", "一周", "ST"]
                    # 数値変換とクリーニング
                    for c in target + ["着順"]: 
                        df[c] = pd.to_numeric(df[c].astype(str).str.replace('S','').replace('NULL',''), errors='coerce')
                    df = df.dropna(subset=["着順"])
                    clean = df[df["着順"] > 0]
                    
                    if len(clean) >= 10: # ある程度のデータ数がある場合のみ解析
                        corrs = {c: abs(clean[c].corr(clean["着順"])) or 0.01 for c in target}
                        total = sum(corrs.values())
                        st.session_state["auto_weights"] = {k: v/total for k, v in corrs.items()}
                        st.success(f"✅ {len(clean)}件のデータから解析完了！")
                    else:
                        st.warning("⚠️ 有効な確定データが不足しています（10件以上必要）")

            # --- グラフ表示エリア（ボタンの外に出すことで保持される） ---
            if "auto_weights" in st.session_state:
                aw = st.session_state["auto_weights"]
                fig_pie = px.pie(
                    names=list(aw.keys()), 
                    values=list(aw.values()), 
                    hole=0.4, 
                    title=f"📊 {r_place} 統計的な重要度",
                    color_discrete_sequence=px.colors.qualitative.Pastel
                )
                fig_pie.update_traces(textposition='inside', textinfo='percent+label')
                st.plotly_chart(fig_pie, use_container_width=True)
                
                with st.expander("📝 解析値の生データ"):
                    st.json(aw)
            else:
                # 解析前のガイド表示
                st.info("上のボタンを押すと、読み込んだ過去データから「どの項目が着順に影響しているか」を自動計算し、グラフを表示します。")
        else:
            st.warning("👈 まずはサイドバーからデータを読み込んでください")

# --- タブ2: 直感気配解析（ここが会場ごとに変わるようになります） ---
with tab2:
    col_l, col_r = st.columns([2, 3])
    with col_l:
        st.subheader(f"⚖️ {r_place} 特性補正")
        # 選択中の会場の補正値を取得
        current_corr = PLACE_CORRECTIONS.get(r_place, PLACE_CORRECTIONS["DEFAULT"])
        
        # グラフ作成
        fig_bar = px.bar(
            x=list(current_corr.keys()), 
            y=list(current_corr.values()), 
            color=list(current_corr.keys()),
            labels={'x':'項目', 'y':'重み'},
            title=f"【{r_place}】自動補正バランス"
        )
        st.plotly_chart(fig_bar, use_container_width=True)
        st.info(f"💡 {r_place}では「{max(current_corr, key=current_corr.get)}」を重視して計算します。")

    with col_r:
        with st.form("form2"):
            raw_feel = []
            c_f = st.columns(2)
            for i in range(1, 7):
                with c_f[(i-1)%2]:
                    st.markdown(f'<div style="background:{boat_bg[i]}; color:{boat_tx[i]}; padding:2px; border-radius:4px; text-align:center;">{i}号艇</div>', unsafe_allow_html=True)
                    f1 = st.select_slider(f"展示気配", range(7), 0, get_symbol, key=f"f2_f1_{i}")
                    f2 = st.select_slider(f"直線(伸び)", range(7), 0, get_symbol, key=f"f2_f2_{i}")
                    f3 = st.select_slider(f"回り足", range(7), 0, get_symbol, key=f"f2_f3_{i}")
                    f4 = st.select_slider(f"一周タイム", range(7), 0, get_symbol, key=f"f2_f4_{i}")
                    # 会場ごとの重みを適用
                    f_score = (f1 * current_corr["展示"] + f2 * current_corr["直線"] + f3 * current_corr["回り足"] + f4 * current_corr["一周"])
                    raw_feel.append({"艇番": i, "score": f_score, "展示": f1, "直線": f2, "回り足": f3, "一周": f4})
            if st.form_submit_button("🚀 直感で確定"):
                df_f = pd.DataFrame(raw_feel)
                df_f["予想％"] = (df_f["score"]/df_f["score"].sum()*100).round(1)
                st.session_state["res"] = df_f; st.dataframe(df_f.style.apply(style_by_rank, axis=0))

# --- タブ3: SNS画像生成 ---
with tab3:
    if "res" in st.session_state:
        st.success("解析データが準備できています。画像を生成してください。")

