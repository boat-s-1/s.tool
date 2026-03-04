import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import streamlit.components.v1 as components

# ==========================================
# 1. 基本設定とデータソース
# ==========================================
st.set_page_config(page_title="競艇Pro Analytica - 全国24場実績連動", layout="wide", page_icon="🎯")

# ご提示いただいた公開CSV URL
URL_1 = "https://docs.google.com/spreadsheets/d/e/2PACX-1vSt_AnojtOiUaKDfvsUntxnu8JIwYisFYaU7wwjsrjHq6Kv1cWPPZoqMyVM97hHgx6zWPxU02CZYBgP/pub?output=csv"
URL_2 = "https://docs.google.com/spreadsheets/d/e/2PACX-1vT5ljmK3YV1lspajPJCSM62VP2FM4w2WKjdgQ2rOrfS6XC96eF6skCo2MAyxbtWXyHJIFyajpsM-7yU/pub?output=csv"

# ==========================================
# 2. 高速統計解析エンジン
# ==========================================
@st.cache_data(ttl=3600)
def load_and_process_big_data():
    try:
        # 2つの巨大なCSVを読み込んで統合
        df1 = pd.read_csv(URL_1)
        df2 = pd.read_csv(URL_2)
        df = pd.concat([df1, df2], ignore_index=True)
        
        # クリーニング：列名の空白削除と会場名の整形
        df.columns = df.columns.str.strip()
        # 「〇〇_混合統計」から「〇〇」を取り出す
        df['会場名'] = df['会場'].astype(str).str.replace('_混合統計', '', regex=False).str.strip()
        
        # 数値変換（エラーはNaNにする）
        df['着順_num'] = pd.to_numeric(df['着順'], errors='coerce')
        df['展示_num'] = pd.to_numeric(df['展示'], errors='coerce')
        
        # 各レース内での展示タイム順位を計算
        df['展示順位'] = df.groupby(['日付', 'レース番号', '会場名'])['展示_num'].rank(method='min')
        
        # --- 会場ごとの集計処理 ---
        stats_map = {}
        for place in df['会場名'].unique():
            if place in ['nan', 'None', '']: continue
            
            p_df = df[df['会場名'] == place]
            # 展示1位の艇だけを抽出
            top_ex = p_df[p_df['展示順位'] == 1]
            
            # 統計指標の算出
            win_rate = (top_ex['着順_num'] == 1).mean() * 100 if not top_ex.empty else 35.0
            show_rate = (top_ex['着順_num'] <= 3).mean() * 100 if not top_ex.empty else 65.0
            in_nige = (p_df[p_df['艇番'] == 1]['着順_num'] == 1).mean() * 100 if not p_df[p_df['艇番'] == 1].empty else 50.0
            
            stats_map[place] = {
                "展示信頼度": round(win_rate, 1), # 展示1位が1着をとる確率
                "展示貢献度": round(show_rate, 1), # 展示1位が3着以内に入る確率
                "イン逃げ率": round(in_nige, 1),
                "サンプル数": len(p_df)
            }
        
        return stats_map
    except Exception as e:
        st.error(f"データ解析中にエラーが発生しました: {e}")
        return {"DEFAULT": {"展示信頼度": 35.0, "展示貢献度": 65.0, "イン逃げ率": 50.0, "サンプル数": 0}}

# 解析実行
ACTUAL_STATS = load_and_process_big_data()

# ==========================================
# 3. ユーティリティ・デザイン
# ==========================================
get_symbol = lambda val: {6: "◎", 5: "○", 4: "▲", 3: "△", 2: "×", 1: "・", 0: "無"}.get(val, "無")
boat_bg = {1: "#ffffff", 2: "#333333", 3: "#e03131", 4: "#1971c2", 5: "#fcc419", 6: "#2f9e44"}
boat_tx = {1: "#000000", 2: "#ffffff", 3: "#ffffff", 4: "#ffffff", 5: "#000000", 6: "#ffffff"}

# ==========================================
# 4. メイン画面レイアウト
# ==========================================
with st.sidebar:
    st.header("📋 解析設定")
    available_places = sorted(list(ACTUAL_STATS.keys()))
    r_place = st.selectbox("開催地を選択", available_places if available_places else ["戸田"])
    r_num = st.number_input("レース番号", 1, 12, 1)
    
    # 選択した会場の実績を表示
    p_stat = ACTUAL_STATS.get(r_place, ACTUAL_STATS.get("DEFAULT"))
    st.divider()
    st.metric("📊 実績イン逃げ率", f"{p_stat['イン逃げ率']}%")
    st.metric("⏱️ 展示1位の1着率", f"{p_stat['展示信頼度']}%")
    st.caption(f"分析レース数: {p_stat['サンプル数']} 件")
    
    st.write("")
    ad_code = '<div style="display:flex; justify-content:center;"><script src="https://adm.shinobi.jp/s/00848ad75df65c15ca7f98de1efcf942"></script></div>'
    components.html(ad_code, height=260)

tab1, tab2 = st.tabs(["📝 事前予想", "🔥 実績連動解析"])

with tab2:
    st.subheader(f"🏟️ {r_place} 実績反映シミュレーター")
    
    # 【ロジック】展示信頼度が高い場ほど「展示」のウェイトを重くする
    ex_weight = min(0.5, p_stat['展示信頼度'] / 100 + 0.1)
    other_weight = (1.0 - ex_weight) / 3
    
    weights = {
        "展示": round(ex_weight, 2),
        "直線": round(other_weight, 2),
        "回り足": round(other_weight, 2),
        "一周": round(other_weight, 2)
    }

    # 重要度の可視化
    st.plotly_chart(px.pie(values=list(weights.values()), names=list(weights.keys()), 
                         hole=0.4, title=f"{r_place}の配点バランス（過去実績より）",
                         color_discrete_sequence=px.colors.qualitative.Pastel), use_container_width=True)

    with st.form("live_analysis"):
        live_results = []
        cols = st.columns(2)
        for i in range(1, 7):
            with cols[(i-1)%2]:
                with st.expander(f"{i}号艇の気配入力", expanded=(i==1)):
                    st.markdown(f'<div style="background:{boat_bg[i]}; color:{boat_tx[i]}; padding:5px; border-radius:4px; text-align:center; font-weight:bold;">{i}号艇</div>', unsafe_allow_html=True)
                    f1 = st.select_slider(f"展示評価_{i}", range(7), 0, get_symbol, key=f"ex_{i}")
                    f2 = st.select_slider(f"直線評価_{i}", range(7), 0, get_symbol, key=f"st_{i}")
                    f3 = st.select_slider(f"回り足評価_{i}", range(7), 0, get_symbol, key=f"tu_{i}")
                    f4 = st.select_slider(f"一周評価_{i}", range(7), 0, get_symbol, key=f"lp_{i}")
                    
                    # 実績ウェイトを用いたスコア計算
                    score = (f1 * weights["展示"] + f2 * weights["直線"] + f3 * weights["回り足"] + f4 * weights["一周"])
                    live_results.append({"艇番": i, "score": score, "展示": get_symbol(f1)})

        if st.form_submit_button("🔥 実績に基づいた最終解析", use_container_width=True, type="primary"):
            df_res = pd.DataFrame(live_results).sort_values("score", ascending=False)
            df_res["期待値"] = (df_res["score"] / df_res["score"].sum() * 100).round(1) if df_res["score"].sum() > 0 else 0
            
            st.success(f"🥇 推奨：{df_res.iloc[0]['艇番']}号艇（この会場の展示1位3連対率は {p_stat['展示貢献度']}% です）")
            st.dataframe(df_res[["艇番", "期待値", "展示"]], use_container_width=True, hide_index=True)
            
            # 買い目提案
            top_3 = df_res["艇番"].tolist()[:3]
            st.info(f"💡 推奨買い目（3連単目安）: {top_3[0]} - {top_3[1]} - {top_3[2]}")
