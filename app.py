import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px

# ==========================================
# 1. 基本設定
# ==========================================
st.set_page_config(page_title="競艇Pro Analytica - Simple", layout="wide", page_icon="🎯")

# デザイン用CSS
st.markdown("""
    <style>
    .stMetric { background-color: #ffffff; padding: 10px; border-radius: 10px; border: 1px solid #eee; }
    .boat-box { padding: 8px; border-radius: 5px; text-align: center; font-weight: bold; margin-bottom: 5px; }
    </style>
""", unsafe_allow_html=True)

# 24場リスト
ALL_PLACES = [
    "桐生", "戸田", "江戸川", "平和島", "多摩川", "浜名湖", "蒲郡", "常滑", "津", 
    "三国", "びわこ", "住之江", "尼崎", "鳴門", "丸亀", "児島", "宮島", "徳山", 
    "下関", "若松", "芦屋", "福岡", "佐賀", "大村"
]

# 艇の色設定
def get_boat_style(num):
    bg = {1: "#ffffff", 2: "#333333", 3: "#e03131", 4: "#1971c2", 5: "#fcc419", 6: "#2f9e44"}
    tx = {1: "#000000", 2: "#ffffff", 3: "#ffffff", 4: "#ffffff", 5: "#000000", 6: "#ffffff"}
    return f'background-color:{bg[num]}; color:{tx[num]};'

get_symbol = lambda val: {6: "◎", 5: "○", 4: "▲", 3: "△", 2: "×", 1: "・", 0: "無"}.get(val, "無")

# ==========================================
# 2. サイドバー
# ==========================================
with st.sidebar:
    st.title("🎯 Pro Analytica")
    r_place = st.selectbox("📍 開催地を選択", ALL_PLACES)
    r_num = st.number_input("🏁 レース番号", 1, 12, 1)
    
    st.divider()
    st.markdown("### ⚙️ 配点設定")
    st.caption("各項目の重要度を調整できます（合計100%）")
    w_ex = st.slider("展示気配の重み", 0, 100, 40)
    w_st = st.slider("直線の重み", 0, 100, 20)
    w_tu = st.slider("旋回の重み", 0, 100, 20)
    w_all = st.slider("総合の重み", 0, 100, 20)
    
    total_w = w_ex + w_st + w_tu + w_all
    if total_w != 100:
        st.error(f"合計が {total_w}% です。100%になるよう調整してください。")

# ==========================================
# 3. メインコンテンツ
# ==========================================
tab1, tab2 = st.tabs(["🔥 直前解析シミュレーター", "📊 メモ・記録"])

with tab1:
    st.subheader(f"🏟️ {r_place} {r_num}R 解析")
    
    # 円グラフ表示
    weights = {"展示": w_ex, "直線": w_st, "旋回": w_tu, "総合": w_all}
    fig = px.pie(values=list(weights.values()), names=list(weights.keys()), hole=0.5,
                 color_discrete_sequence=px.colors.qualitative.Pastel, height=300)
    fig.update_layout(margin=dict(t=30, b=0, l=0, r=0))
    st.plotly_chart(fig, use_container_width=True)

    # 入力フォーム
    with st.form("input_form"):
        st.markdown("### 📝 気配入力")
        input_cols = st.columns(3)
        live_data = []
        
        for i in range(1, 7):
            with input_cols[(i-1) % 3]:
                st.markdown(f'<div class="boat-box" style="{get_boat_style(i)}">{i}号艇</div>', unsafe_allow_html=True)
                f1 = st.select_slider(f"展示_{i}", range(7), 3, get_symbol, key=f"ex_{i}")
                f2 = st.select_slider(f"直線_{i}", range(7), 3, get_symbol, key=f"st_{i}")
                f3 = st.select_slider(f"旋回_{i}", range(7), 3, get_symbol, key=f"tu_{i}")
                f4 = st.select_slider(f"総合_{i}", range(7), 3, get_symbol, key=f"all_{i}")
                
                # スコア計算
                score = (f1 * (w_ex/100) + f2 * (w_st/100) + f3 * (w_tu/100) + f4 * (w_all/100))
                live_data.append({"艇番": i, "score": score, "展示": get_symbol(f1)})

        submit = st.form_submit_button("🔥 解析を実行", use_container_width=True, type="primary")

    if submit and total_w == 100:
        df_res = pd.DataFrame(live_data).sort_values("score", ascending=False)
        df_res["期待値"] = (df_res["score"] / df_res["score"].sum() * 100).round(1) if df_res["score"].sum() > 0 else 0
        
        st.markdown("---")
        res_col1, res_col2 = st.columns([1.5, 1])
        
        with res_col1:
            st.subheader("🏁 解析結果")
            st.dataframe(df_res[["艇番", "期待値", "展示"]], use_container_width=True, hide_index=True)

        with res_col2:
            st.subheader("💡 買い目")
            top_3 = df_res["艇番"].tolist()[:3]
            st.markdown(f"""
            <div style="background-color: #fff; padding: 20px; border-radius: 10px; border-left: 5px solid #ff4b4b; box-shadow: 2px 2px 10px rgba(0,0,0,0.1);">
                <h4 style="margin-top:0;">推奨組み合わせ</h4>
                <p style="font-size: 28px; font-weight: bold; color: #ff4b4b; text-align:center;">{top_3[0]} — {top_3[1]} — {top_3[2]}</p>
            </div>
            """, unsafe_allow_html=True)

with tab2:
    st.subheader("📋 レースメモ")
    st.text_area("気になった点やメモをここに記入してください", height=300, placeholder="例：展示タイム以上に1号艇の行き足が良い...")
    st.button("メモを保存（ブラウザを閉じると消えます）")
