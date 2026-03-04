import streamlit as st
import pandas as pd
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import io
import datetime
import plotly.express as px
import streamlit.components.v1 as components

# ==========================================
# 1. 基本設定とスプレッドシートURL
# ==========================================
st.set_page_config(page_title="競艇Pro Analytica - 実績連動型", layout="wide", page_icon="🎯")

# ここに「ウェブに公開」で取得したCSV用URLを貼り付けてください
SHEET_URL = "https://docs.google.com/spreadsheets/d/1rSzJuk5Hyv60nMwX67pCufXz45HLykyIXuqVE6wtNII/pub?output=csv"

# ==========================================
# 2. 統計データ解析エンジン
# ==========================================
@st.cache_data(ttl=3600) # 1時間キャッシュ
def load_and_analyze_stats():
    # 万が一読み込めなかった時のためのバックアップデータ（全国平均値など）
    DEFAULT_STATS = {
        "大村": {"展示信頼度": 45.0, "展示貢献度": 75.0, "イン逃げ率": 68.5, "サンプル数": 1800},
        "戸田": {"展示信頼度": 28.0, "展示貢献度": 55.0, "イン逃げ率": 43.8, "サンプル数": 1200},
        "DEFAULT": {"展示信頼度": 35.0, "展示貢献度": 65.0, "イン逃げ率": 50.0, "サンプル数": 5000}
    }

    try:
        # スプレッドシートをCSVとして読み込み
        df = pd.read_csv(SHEET_URL)
        
        # 列名の空白削除
        df.columns = df.columns.str.strip()
        
        # 着順の数値化
        df['着順_num'] = pd.to_numeric(df['着順'], errors='coerce')
        
        # 展示タイムに基づくレース内順位
        # 日付、レース番号、会場が同じものを1つのレースとしてグループ化
        df['展示順位'] = df.groupby(['日付', 'レース番号', '会場'])['展示'].rank(method='min')
        
        stats = {}
        unique_places = df['会場'].unique()
        
        for place in unique_places:
            p_df = df[df['会場'] == place]
            # 展示1位のデータ
            top_ex = p_df[p_df['展示順位'] == 1]
            
            # 統計計算
            win_rate = (top_ex['着順_num'] == 1).mean() * 100 if not top_ex.empty else 35.0
            show_rate = (top_ex['着順_num'] <= 3).mean() * 100 if not top_ex.empty else 65.0
            in_nige = (p_df[p_df['艇番'] == 1]['着順_num'] == 1).mean() * 100 if not p_df[p_df['艇番'] == 1].empty else 50.0
            
            stats[place] = {
                "展示信頼度": round(win_rate, 1),
                "展示貢献度": round(show_rate, 1),
                "イン逃げ率": round(in_nige, 1),
                "サンプル数": len(p_df)
            }
        
        # 取得した場が少ない場合はDEFAULTを追加
        if "DEFAULT" not in stats:
            stats["DEFAULT"] = DEFAULT_STATS["DEFAULT"]
            
        return stats

    except Exception as e:
        # 401エラーなどが発生した場合は警告を出してバックアップを表示
        st.sidebar.error(f"⚠️ スプレッドシート連携エラー: 権限を確認してください。")
        st.sidebar.caption(f"詳細: {e}")
        return DEFAULT_STATS

# データの実行
ACTUAL_STATS = load_and_analyze_stats()

# ==========================================
# 3. ユーティリティ
# ==========================================
get_symbol = lambda val: {6: "◎", 5: "○", 4: "▲", 3: "△", 2: "×", 1: "・", 0: "無"}.get(val, "無")
boat_bg = {1: "#ffffff", 2: "#333333", 3: "#e03131", 4: "#1971c2", 5: "#fcc419", 6: "#2f9e44"}
boat_tx = {1: "#000000", 2: "#ffffff", 3: "#ffffff", 4: "#ffffff", 5: "#000000", 6: "#ffffff"}

# ==========================================
# 4. 画面レイアウト
# ==========================================
with st.sidebar:
    st.header("📋 レース設定")
    # スプレッドシートから取得した会場リストを表示（なければ基本リスト）
    place_list = sorted(list(ACTUAL_STATS.keys()))
    r_place = st.selectbox("開催地", place_list)
    r_num = st.number_input("レース番号", 1, 12, 1)
    
    # 選択中の会場の実績を表示
    p_stat = ACTUAL_STATS.get(r_place, ACTUAL_STATS.get("DEFAULT"))
    st.divider()
    st.metric("実績イン逃げ率", f"{p_stat['イン逃げ率']}%")
    st.metric("展示1位の1着率", f"{p_stat['展示信頼度']}%")
    st.caption(f"分析レース数: {p_stat['サンプル数']}")
    
    st.write("")
    st.caption("スポンサーリンク")
    ad_code = '<div style="display:flex; justify-content:center;"><script src="https://adm.shinobi.jp/s/00848ad75df65c15ca7f98de1efcf942"></script></div>'
    components.html(ad_code, height=260)

tab1, tab2, tab3 = st.tabs(["📝 事前予想", "🔥 実績連動解析", "📸 画像生成"])

# --- タブ2: 実績連動解析 ---
with tab2:
    st.subheader(f"🏟️ {r_place} 実績反映モデル")
    
    # 展示1位の1着率(展示信頼度)に基づいて重みを自動分配
    # 信頼度が高い場ほど展示のウェイトを上げる(Max 0.5)
    ex_weight = min(0.5, p_stat['展示信頼度'] / 100 + 0.1)
    other_weight = (1.0 - ex_weight) / 3
    
    weights = {
        "展示": round(ex_weight, 2),
        "直線": round(other_weight, 2),
        "回り足": round(other_weight, 2),
        "一周": round(other_weight, 2)
    }

    # 重み可視化グラフ
    fig = px.pie(values=list(weights.values()), names=list(weights.keys()), 
                 title=f"実績に基づく『{r_place}』重要度配分",
                 hole=0.4, color_discrete_sequence=px.colors.qualitative.Bold)
    st.plotly_chart(fig, use_container_width=True)

    with st.form("live_form"):
        live_raw = []
        # スマホ配慮の2カラム × 3行
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
        
        submitted_live = st.form_submit_button("最終解析を実行", use_container_width=True, type="primary")

    if submitted_live:
        df_live = pd.DataFrame(live_raw).sort_values("score", ascending=False)
        total_s = df_live["score"].sum()
        df_live["期待値"] = (df_live["score"] / total_s * 100).round(1) if total_s > 0 else 0
        st.session_state["final_res"] = df_live
        
        st.markdown("### 🏁 解析結果")
        top_boat = df_live.iloc[0]['艇番']
        st.success(f"推奨：{top_boat}号艇。この会場は展示1位の3連対率が {p_stat['展示貢献度']}% あります。")
        st.dataframe(df_live[["艇番", "期待値", "展示", "直線", "回り足", "一周"]], use_container_width=True, hide_index=True)
