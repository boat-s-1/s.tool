import streamlit as st
import pandas as pd
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import io
import datetime
import plotly.express as px
import streamlit.components.v1 as components

# ==========================================
# 1. 基本設定とデータ読み込み
# ==========================================
st.set_page_config(page_title="競艇Pro Analytica - 実績解析版", layout="wide", page_icon="🎯")

# スプレッドシートのURL（CSV出力用）
# ※ご自身のスプレッドシートの「ウェブに公開」URLに差し替えてください
SHEET_URL = "https://docs.google.com/spreadsheets/d/1rSzJuk5Hyv60nMwX67pCufXz45HLykyIXuqVE6wtNII/pub?output=csv"

@st.cache_data(ttl=3600) # 1時間キャッシュ
def load_and_analyze_stats():
    try:
        # スプレッドシートを読み込み
        df = pd.read_csv(SHEET_URL)
        
        # 着順を数値化（1, 2, 3... 以外は欠損値として扱う）
        df['着順_num'] = pd.to_numeric(df['着順'], errors='coerce')
        
        # 各レース内での展示タイム順位を計算
        # 同じタイムの場合は最小順位を割り当て
        df['展示順位'] = df.groupby(['日付', 'レース番号', '会場'])['展示'].rank(method='min')
        
        # --- 会場ごとの統計分析 ---
        stats = {}
        for place in df['会場'].unique():
            p_df = df[df['会場'] == place]
            
            # 1. 展示1位の1着率
            top_ex = p_df[p_df['展示順位'] == 1]
            win_rate = (top_ex['着順_num'] == 1).mean() * 100
            
            # 2. 展示1位の3連対率（舟券貢献度）
            show_rate = (top_ex['着順_num'] <= 3).mean() * 100
            
            # 3. イン逃げ率（1号艇の1着率）
            in_nige = (p_df[p_df['艇番'] == 1]['着順_num'] == 1).mean() * 100
            
            stats[place] = {
                "展示信頼度": round(win_rate, 1), # 展示1位が勝つ確率
                "展示貢献度": round(show_rate, 1), # 展示1位が3着内に入る確率
                "イン逃げ率": round(in_nige, 1),
                "サンプル数": len(p_df)
            }
        return stats
    except Exception as e:
        st.error(f"データ読み込みエラー: {e}")
        # エラー時のダミーデータ
        return {"DEFAULT": {"展示信頼度": 35.0, "展示貢献度": 65.0, "イン逃げ率": 50.0, "サンプル数": 5000}}

# 統計データの取得
ACTUAL_STATS = load_and_analyze_stats()

# デザイン用
get_symbol = lambda val: {6: "◎", 5: "○", 4: "▲", 3: "△", 2: "×", 1: "・", 0: "無"}.get(val, "無")
boat_bg = {1: "#ffffff", 2: "#333333", 3: "#e03131", 4: "#1971c2", 5: "#fcc419", 6: "#2f9e44"}
boat_tx = {1: "#000000", 2: "#ffffff", 3: "#ffffff", 4: "#ffffff", 5: "#000000", 6: "#ffffff"}

# ==========================================
# 2. メインロジック
# ==========================================
with st.sidebar:
    st.header("📋 レース情報")
    r_place = st.selectbox("開催地", list(ACTUAL_STATS.keys()) if ACTUAL_STATS else ["桐生"])
    r_num = st.number_input("レース番号", 1, 12, 1)
    
    # 選択した場の実績データを表示
    p_stat = ACTUAL_STATS.get(r_place, ACTUAL_STATS.get("DEFAULT"))
    st.divider()
    st.metric("実績イン逃げ率", f"{p_stat['イン逃げ率']}%")
    st.metric("展示1位の1着率", f"{p_stat['展示信頼度']}%")
    st.caption(f"分析対象: {p_stat['サンプル数']} レース")

tab1, tab2, tab3 = st.tabs(["📝 簡易事前予想", "🔥 実績連動解析", "📸 SNS画像生成"])

with tab2:
    st.subheader(f"🏟️ {r_place} 実績ベース解析")
    
    # 展示信頼度に基づいた動的ウェイト設定
    # 展示1位の1着率が高い場ほど「展示」の配分を自動で増やすロジック
    base_weight = p_stat['展示信頼度'] / 100
    weights = {
        "展示": round(base_weight, 2),
        "直線": round((1 - base_weight) * 0.3, 2),
        "回り足": round((1 - base_weight) * 0.4, 2),
        "一周": round((1 - base_weight) * 0.3, 2)
    }

    # グラフ表示
    fig = px.pie(values=list(weights.values()), names=list(weights.keys()), 
                 title=f"実績から算出した『{r_place}』の重要度配分",
                 color_discrete_sequence=px.colors.qualitative.Pastel)
    st.plotly_chart(fig, use_container_width=True)

    with st.form("live_form"):
        live_raw = []
        # スマホ配慮の2カラム形式
        for row_idx in range(3):
            l_cols = st.columns(2)
            for col_idx in range(2):
                i = row_idx * 2 + col_idx + 1
                with l_cols[col_idx]:
                    with st.expander(f"{i}号艇の気配入力", expanded=(i==1)):
                        st.markdown(f'<div style="background:{boat_bg[i]}; color:{boat_tx[i]}; padding:5px; border-radius:4px; text-align:center; font-weight:bold; border:1px solid #ccc;">{i}号艇</div>', unsafe_allow_html=True)
                        f1 = st.select_slider(f"展示(実績信頼度:{p_stat['展示信頼度']}%)", range(7), 0, get_symbol, key=f"live_f1_{i}")
                        f2 = st.select_slider(f"直線", range(7), 0, get_symbol, key=f"live_f2_{i}")
                        f3 = st.select_slider(f"回り足", range(7), 0, get_symbol, key=f"live_f3_{i}")
                        f4 = st.select_slider(f"一周", range(7), 0, get_symbol, key=f"live_f4_{i}")
                        
                        score = (f1 * weights["展示"] + f2 * weights["直線"] + f3 * weights["回り足"] + f4 * weights["一周"])
                        live_raw.append({"艇番": i, "score": score, "展示": get_symbol(f1), "直線": get_symbol(f2), "回り足": get_symbol(f3), "一周": get_symbol(f4)})
        
        submitted_live = st.form_submit_button("実績データを反映して解析実行", use_container_width=True, type="primary")

    if submitted_live:
        df_live = pd.DataFrame(live_raw).sort_values("score", ascending=False)
        total_s = df_live["score"].sum()
        df_live["期待値"] = (df_live["score"] / total_s * 100).round(1) if total_s > 0 else 0
        st.session_state["final_res"] = df_live
        
        st.markdown("### 🏁 最終解析結果")
        # 1位の艇に「展示信頼度」に基づいたコメントを表示
        top_boat = df_live.iloc[0]['艇番']
        st.success(f"推奨：{top_boat}号艇。この会場は展示1位の3連対率が {p_stat['展示貢献度']}% あり、信頼度は高いです。")
        st.dataframe(df_live[["艇番", "期待値", "展示", "直線", "回り足", "一周"]], use_container_width=True, hide_index=True)
