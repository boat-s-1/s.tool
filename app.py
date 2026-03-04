import streamlit as st
import pandas as pd
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import io
import datetime
import plotly.express as px
import streamlit.components.v1 as components

# ==========================================
# 1. 基本設定
# ==========================================
st.set_page_config(page_title="競艇Pro Analytica - 24場統合版", layout="wide", page_icon="🎯")

# 「統合データ」シートをCSV公開したURLをここに
SHEET_URL_1 = "https://docs.google.com/spreadsheets/d/e/2PACX-1vSt_AnojtOiUaKDfvsUntxnu8JIwYisFYaU7wwjsrjHq6Kv1cWPPZoqMyVM97hHgx6zWPxU02CZYBgP/pub?output=csv"
SHEET_URL_2 = "https://docs.google.com/spreadsheets/d/e/2PACX-1vT5ljmK3YV1lspajPJCSM62VP2FM4w2WKjdgQ2rOrfS6XC96eF6skCo2MAyxbtWXyHJIFyajpsM-7yU/pub?output=csv"

# ==========================================
# 2. 統計データ解析エンジン（会場名クリーニング強化）
# ==========================================
@st.cache_data(ttl=3600)
def load_and_analyze_combined_stats():
    try:
        # シート読み込み
        df1 = pd.read_csv(SHEET_URL_1)
        df2 = pd.read_csv(SHEET_URL_2)
        combined_df = pd.concat([df1, df2], ignore_index=True)
        
        # --- データクリーニング ---
        combined_df.columns = combined_df.columns.str.strip()
        
        # 「会場」という列がない場合、「会場名」や「場名」など似た名前を探す
        target_col = '会場'
        if target_col not in combined_df.columns:
            for col in combined_df.columns:
                if '場' in col or '会' in col:
                    target_col = col
                    break
        
        # 会場名の整形（「桐生_混合統計」→「桐生」）
        combined_df['clean_place'] = combined_df[target_col].astype(str).str.replace('_混合統計', '', regex=False).str.strip()
        
        # 数値化
        combined_df['着順_num'] = pd.to_numeric(combined_df['着順'], errors='coerce')
        combined_df['展示'] = pd.to_numeric(combined_df['展示'], errors='coerce')
        
        # 展示順位の計算
        combined_df['展示順位'] = combined_df.groupby(['日付', 'レース番号', 'clean_place'])['展示'].rank(method='min')
        
        stats = {}
        for place in combined_df['clean_place'].unique():
            if place in ['nan', '', 'None'] or pd.isna(place): continue
            
            p_df = combined_df[combined_df['clean_place'] == place]
            top_ex = p_df[p_df['展示順位'] == 1]
            
            win_rate = (top_ex['着順_num'] == 1).mean() * 100 if not top_ex.empty else 35.0
            show_rate = (top_ex['着順_num'] <= 3).mean() * 100 if not top_ex.empty else 65.0
            in_nige = (p_df[p_df['艇番'] == 1]['着順_num'] == 1).mean() * 100 if not p_df[p_df['艇番'] == 1].empty else 50.0
            
            stats[place] = {
                "展示信頼度": round(win_rate, 1),
                "展示貢献度": round(show_rate, 1),
                "イン逃げ率": round(in_nige, 1),
                "サンプル数": len(p_df)
            }
        return stats
    except Exception as e:
        return {"DEFAULT": {"展示信頼度": 35.0, "展示貢献度": 65.0, "イン逃げ率": 50.0, "サンプル数": 0}}

ACTUAL_STATS = load_and_analyze_combined_stats()

# --- デザイン用の辞書 ---
boat_bg = {1: "#ffffff", 2: "#333333", 3: "#e03131", 4: "#1971c2", 5: "#fcc419", 6: "#2f9e44"}
boat_tx = {1: "#000000", 2: "#ffffff", 3: "#ffffff", 4: "#ffffff", 5: "#000000", 6: "#ffffff"}
get_symbol = lambda val: {6: "◎", 5: "○", 4: "▲", 3: "△", 2: "×", 1: "・", 0: "無"}.get(val, "無")

# ==========================================
# 3. メインレイアウト
# ==========================================
with st.sidebar:
    st.header("📋 設定")
    available_places = sorted(list(ACTUAL_STATS.keys()))
    r_place = st.selectbox("開催地を選択", available_places if available_places else ["戸田"])
    r_num = st.number_input("レース番号", 1, 12, 1)
    
    p_stat = ACTUAL_STATS.get(r_place, ACTUAL_STATS.get("DEFAULT"))
    st.divider()
    st.metric("実績イン逃げ率", f"{p_stat['イン逃げ率']}%")
    st.metric("展示1位の1着率", f"{p_stat['展示信頼度']}%")
    st.caption(f"分析レース数: {p_stat['サンプル数']}")

tab1, tab2 = st.tabs(["📝 事前予想", "🔥 実績連動解析"])

with tab2:
    st.subheader(f"🏟️ {r_place} 実績反映モデル")
    
    # 重みの自動計算
    ex_w = min(0.5, p_stat['展示信頼度'] / 100 + 0.1)
    other_w = (1.0 - ex_w) / 3
    weights = {"展示": round(ex_w, 2), "直線": round(other_w, 2), "回り足": round(other_w, 2), "一周": round(other_w, 2)}

    st.plotly_chart(px.pie(values=list(weights.values()), names=list(weights.keys()), hole=0.4, title="この会場の重要度配分"), use_container_width=True)

    with st.form("live_form"):
        live_raw = []
        cols = st.columns(2)
        for i in range(1, 7):
            with cols[(i-1)%2]:
                with st.expander(f"{i}号艇の気配入力", expanded=(i==1)):
                    st.markdown(f'<div style="background:{boat_bg[i]}; color:{boat_tx[i]}; padding:5px; border-radius:4px; text-align:center;">{i}号艇</div>', unsafe_allow_html=True)
                    f1 = st.select_slider(f"展示_{i}", range(7), 0, get_symbol)
                    f2 = st.select_slider(f"直線_{i}", range(7), 0, get_symbol)
                    f3 = st.select_slider(f"回り足_{i}", range(7), 0, get_symbol)
                    f4 = st.select_slider(f"一周_{i}", range(7), 0, get_symbol)
                    score = (f1*weights["展示"] + f2*weights["直線"] + f3*weights["回り足"] + f4*weights["一周"])
                    live_raw.append({"艇番": i, "score": score, "展示": get_symbol(f1), "直線": get_symbol(f2), "回り足": get_symbol(f3), "一周": get_symbol(f4)})
        
        if st.form_submit_button("解析実行", use_container_width=True, type="primary"):
            df_live = pd.DataFrame(live_raw).sort_values("score", ascending=False)
            df_live["期待値"] = (df_live["score"] / df_live["score"].sum() * 100).round(1)
            st.session_state["final_res"] = df_live
            st.success(f"推奨：{df_live.iloc[0]['艇番']}号艇")
            st.dataframe(df_live[["艇番", "期待値", "展示", "直線", "回り足", "一周"]], use_container_width=True, hide_index=True)
