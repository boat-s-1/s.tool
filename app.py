import streamlit as st
import pandas as pd
import numpy as np
import requests
import plotly.express as px
import streamlit.components.v1 as components

# ==========================================
# 1. 基本設定とスタイル
# ==========================================
st.set_page_config(page_title="競艇Pro Analytica - Premium", layout="wide", page_icon="🎯")

# カスタムCSSでデザインを微調整
st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    .stMetric { background-color: #ffffff; padding: 15px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    .boat-box { padding: 10px; border-radius: 8px; text-align: center; font-weight: bold; margin-bottom: 10px; border: 1px solid #dee2e6; }
    </style>
""", unsafe_allow_html=True)

# あなたのGASのURL
GAS_URL = "https://script.google.com/macros/s/AKfycbwypoD8dV1DhXsX6C1wK893MAWKImWtKmbbQ9JwVOw0Rm13FZ8K9B4S97S8hGKeAvbQ/exec"

# ==========================================
# 2. データ読込エンジン
# ==========================================
@st.cache_data(ttl=3600)
def load_all_stats_from_gas():
    stats = {}
    try:
        response = requests.get(GAS_URL)
        all_data = response.json()
        for sheet_name, rows in all_data.items():
            if len(rows) < 2: continue
            place = sheet_name.replace("_混合統計", "").strip()
            df = pd.DataFrame(rows[1:], columns=rows[0])
            df.columns = df.columns.str.strip()
            df['着順_num'] = pd.to_numeric(df['着順'], errors='coerce')
            df['展示_num'] = pd.to_numeric(df['展示'], errors='coerce')
            df = df.dropna(subset=['着順_num', '展示_num'])
            if df.empty: continue
            df['展示順位'] = df.groupby(['日付', 'レース番号'])['展示_num'].rank(method='min')
            top_ex = df[df['展示順位'] == 1]
            win_rate = (top_ex['着順_num'] == 1).mean() * 100 if not top_ex.empty else 35.0
            show_rate = (top_ex['着順_num'] <= 3).mean() * 100 if not top_ex.empty else 65.0
            in_nige = (df[df['艇番'] == 1]['着順_num'] == 1).mean() * 100 if not df[df['艇番'] == 1].empty else 50.0
            stats[place] = {
                "展示信頼度": round(win_rate, 1),
                "展示貢献度": round(show_rate, 1),
                "イン逃げ率": round(in_nige, 1),
                "サンプル数": len(df)
            }
        return stats
    except Exception as e:
        st.error(f"データ連携エラー: {e}")
        return {}

ACTUAL_STATS = load_all_stats_from_gas()

# ==========================================
# 3. ユーティリティ
# ==========================================
def get_boat_style(num):
    bg = {1: "#ffffff", 2: "#333333", 3: "#e03131", 4: "#1971c2", 5: "#fcc419", 6: "#2f9e44"}
    tx = {1: "#000000", 2: "#ffffff", 3: "#ffffff", 4: "#ffffff", 5: "#000000", 6: "#ffffff"}
    return f'background-color:{bg[num]}; color:{tx[num]};'

get_symbol = lambda val: {6: "◎", 5: "○", 4: "▲", 3: "△", 2: "×", 1: "・", 0: "無"}.get(val, "無")

# ==========================================
# 4. サイドバー
# ==========================================
with st.sidebar:
    st.title("🎯 Pro Analytica")
    if ACTUAL_STATS:
        available_places = sorted(list(ACTUAL_STATS.keys()))
        r_place = st.selectbox("📍 開催地を選択", available_places)
        r_num = st.number_input("🏁 レース番号", 1, 12, 1)
        
        p_stat = ACTUAL_STATS[r_place]
        st.markdown("---")
        st.subheader(f"🏟️ {r_place} 統計")
        
        c1, c2 = st.columns(2)
        with c1:
            st.metric("イン逃げ率", f"{p_stat['イン逃げ率']}%")
        with c2:
            st.metric("展示1位1着", f"{p_stat['展示信頼度']}%")
        
        st.metric("展示1位3連対率", f"{p_stat['展示貢献度']}%")
        st.caption(f"分析対象: {p_stat['サンプル数']} レース")
    else:
        st.warning("データを読み込んでいます...")

# ==========================================
# 5. メインコンテンツ
# ==========================================
if ACTUAL_STATS:
    tab1, tab2 = st.tabs(["🔥 実績連動・直前解析", "📊 全国会場データ比較"])

    # --- タブ1: 直前解析 ---
    with tab1:
        # 重み計算
        ex_weight = min(0.5, p_stat['展示信頼度'] / 100 + 0.1)
        other_weight = (1.0 - ex_weight) / 3
        weights = {
            "展示気配": round(ex_weight, 2),
            "直線/伸び": round(other_weight, 2),
            "回り足": round(other_weight, 2),
            "一周/総合": round(other_weight, 2)
        }

        col_l, col_r = st.columns([1, 1.5])
        
        with col_l:
            st.markdown("### 📊 会場別・重要度バランス")
            st.caption(f"過去の{r_place}の実績から、重視すべき評価項目を自動算出しています。")
            fig = px.pie(values=list(weights.values()), names=list(weights.keys()), hole=0.5,
                         color_discrete_sequence=px.colors.qualitative.Pastel)
            fig.update_layout(margin=dict(t=0, b=0, l=0, r=0), showlegend=True)
            st.plotly_chart(fig, use_container_width=True)

        with col_r:
            st.markdown("### 💡 推奨の狙い目")
            if p_stat['イン逃げ率'] > 60:
                st.success(f"【イン信頼】{r_place}は全国的にもインが強い場です。1号艇を軸にした組み立てが基本です。")
            elif p_stat['展示信頼度'] > 40:
                st.info(f"【展示重視】展示1位の信頼度が非常に高い場です。展示タイムが良い艇を高く評価してください。")
            else:
                st.warning(f"【波乱含み】イン逃げ率が低めです。センター・外枠の逆転に注意が必要です。")

        # 気配入力フォーム
        with st.form("input_form"):
            st.markdown("### 📝 直前気配入力")
            input_cols = st.columns(3) # スマホ等で見やすいよう3列2行に配置
            live_data = []
            
            for i in range(1, 7):
                with input_cols[(i-1) % 3]:
                    st.markdown(f'<div class="boat-box" style="{get_boat_style(i)}">{i}号艇</div>', unsafe_allow_html=True)
                    f1 = st.select_slider(f"展示_{i}", range(7), 3, get_symbol, key=f"ex_{i}")
                    f2 = st.select_slider(f"直線_{i}", range(7), 3, get_symbol, key=f"st_{i}")
                    f3 = st.select_slider(f"旋回_{i}", range(7), 3, get_symbol, key=f"tu_{i}")
                    f4 = st.select_slider(f"総合_{i}", range(7), 3, get_symbol, key=f"all_{i}")
                    
                    score = (f1*weights["展示気配"] + f2*weights["直線/伸び"] + f3*weights["回り足"] + f4*weights["一周/総合"])
                    live_data.append({"艇番": i, "score": score, "展示": get_symbol(f1), "直線": get_symbol(f2), "旋回": get_symbol(f3)})

            submit = st.form_submit_button("🔥 最終解析を実行", use_container_width=True, type="primary")

        if submit:
            df_res = pd.DataFrame(live_data).sort_values("score", ascending=False)
            df_res["期待値"] = (df_res["score"] / df_res["score"].sum() * 100).round(1)
            
            st.markdown("---")
            res_col1, res_col2 = st.columns([1.5, 1])
            
            with res_col1:
                st.subheader("🏁 解析結果ランキング")
                # 艇番に色をつける処理
                def color_boat(val):
                    colors = {1: '#f8f9fa', 2: '#333', 3: '#e03131', 4: '#1971c2', 5: '#fcc419', 6: '#2f9e44'}
                    return f'background-color: {colors.get(val, "")}'

                st.dataframe(df_res[["艇番", "期待値", "展示", "直線", "旋回"]].style.applymap(color_boat, subset=['艇番']), 
                             use_container_width=True, hide_index=True)

            with res_col2:
                st.subheader("💡 買い目シミュレーション")
                top_3 = df_res["艇番"].tolist()[:3]
                st.markdown(f"""
                <div style="background-color: #fff; padding: 20px; border-radius: 10px; border-left: 5px solid #ff4b4b;">
                    <h4 style="margin-top:0;">本命予想</h4>
                    <p style="font-size: 24px; font-weight: bold; color: #ff4b4b;">{top_3[0]} — {top_3[1]} — {top_3[2]}</p>
                    <p style="font-size: 14px;">期待値ベースの3連単組み合わせです。</p>
                </div>
                """, unsafe_allow_html=True)
                st.caption(f"※{r_place}の展示1位3連対率は {p_stat['展示貢献度']}% です。")

    # --- タブ2: 全国会場比較 ---
    with tab2:
        st.subheader("📊 全国24場 実績比較")
        compare_df = pd.DataFrame.from_dict(ACTUAL_STATS, orient='index').reset_index()
        compare_df.columns = ["会場名", "展示信頼度(1着)", "展示貢献度(3着内)", "イン逃げ率", "分析数"]
        
        # グラフでの可視化
        sort_col = st.selectbox("並び替え指標", ["イン逃げ率", "展示信頼度(1着)", "展示貢献度(3着内)"])
        compare_df = compare_df.sort_values(sort_col, ascending=False)
        
        fig_compare = px.bar(compare_df, x="会場名", y=sort_col, color=sort_col,
                             color_continuous_scale="Blues", title=f"{sort_col} ランキング")
        st.plotly_chart(fig_compare, use_container_width=True)
        
        st.dataframe(compare_df, use_container_width=True, hide_index=True)

else:
    st.error("GASからのデータ取得に失敗しました。URLを確認してください。")
