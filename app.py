import streamlit as st
import pandas as pd

# ==========================================
# 1. 設定・定数エリア
# ==========================================
def get_label(val):
    labels = {6: "◎", 5: "○", 4: "▲", 3: "△", 2: "×", 1: "・", 0: "無"}
    return labels.get(val, "無")

# ==========================================
# 2. UI関数エリア
# ==========================================
def render_7step_with_styled_table():
    st.header("🎯 ボートレース事前簡易予想ツール")
    
    # 指標の重み
    WEIGHTS = {"モーター": 0.25, "当地勝率": 0.2, "枠番勝率": 0.3, "枠番スタート": 0.25}

    # --- 入力フォーム ---
    with st.form("slider_7step_form"):
        st.markdown("##### 🚤 艇ごとの評価入力 (0:無 〜 6:極)")
        raw_data = []
        for row in range(3):
            cols = st.columns(2)
            for col in range(2):
                i = row * 2 + col + 1
                with cols[col]:
                    st.markdown(f"""<div style="background:#f1f3f5; border-left:5px solid #2d3436; padding:5px 10px; border-radius:4px; margin-bottom:5px;"><b>{i}号艇</b></div>""", unsafe_allow_html=True)
                    m = st.select_slider(f"🚀 モーター", options=range(7), value=0, format_func=lambda x: {6:"◎",5:"○",4:"▲",3:"△",2:"×",1:"・",0:"無"}[x], key=f"v_m_{i}")
                    t = st.select_slider(f"🏟️ 当地勝率", options=range(7), value=0, format_func=lambda x: {6:"◎",5:"○",4:"▲",3:"△",2:"×",1:"・",0:"無"}[x], key=f"v_t_{i}")
                    w = st.select_slider(f"📈 枠番勝率", options=range(7), value=0, format_func=lambda x: {6:"◎",5:"○",4:"▲",3:"△",2:"×",1:"・",0:"無"}[x], key=f"v_w_{i}")
                    s = st.select_slider(f"⏱️ 枠番ST", options=range(7), value=0, format_func=lambda x: {6:"◎",5:"○",4:"▲",3:"△",2:"×",1:"・",0:"無"}[x], key=f"v_s_{i}")

                    score = (m * WEIGHTS["モーター"] + t * WEIGHTS["当地勝率"] + w * WEIGHTS["枠番勝率"] + s * WEIGHTS["枠番スタート"])
                    raw_data.append({"艇番": i, "モーター": m, "当地勝率": t, "枠番勝率": w, "枠番スタート": s, "総合スコア": round(score, 3)})
            st.divider()
        submitted = st.form_submit_button("📊 予想解析を実行", use_container_width=True, type="primary")

    if submitted:
        df = pd.DataFrame(raw_data)
        if df["総合スコア"].sum() == 0:
            st.warning("⚠️ 評価を入力してください。")
            return

        # --- 1. 項目別ランキング表の作成 ---
        st.markdown("### 📋 項目別評価ランキング")
        items = [("🚀 モーター", "モーター"), ("🏟️ 当地勝率", "当地勝率"), ("📈 枠番勝率", "枠番勝率"), ("⏱️ 枠番スタート", "枠番スタート")]
        
        # 各項目の1位〜6位を算出
        rank_table = {}
        for display_name, col_name in items:
            # 評価が高い順、同じなら艇番が若い順
            sorted_df = df.sort_values(by=[col_name, "艇番"], ascending=[False, True]).reset_index()
            rank_list = []
            for r in range(6):
                boat = sorted_df.loc[r, '艇番']
                val_label = get_label(sorted_df.loc[r, col_name])
                rank_list.append(f"{boat} ({val_label})")
            rank_table[display_name] = rank_list

        rank_df = pd.DataFrame(rank_table, index=[f"{i}位" for i in range(1, 7)])

        # スタイル適用関数
        def style_ranking(styler):
            # 1位（0行目）を赤、2位（1行目）を黄色
            styler.applymap(lambda x: 'background-color: #ffcccc; color: #cc0000; font-weight: bold;', subset=pd.IndexSlice['1位', :])
            styler.applymap(lambda x: 'background-color: #ffffcc; color: #888800; font-weight: bold;', subset=pd.IndexSlice['2位', :])
            return styler

        st.table(style_ranking(rank_df.style))

        # --- 2. 総合％予想の計算 ---
        total_sum = df["総合スコア"].sum()
        df["予想％"] = (df["総合スコア"] / total_sum * 100).round(1)
        df_sorted = df.sort_values("予想％", ascending=False).reset_index(drop=True)
        diff = 100.0 - df_sorted["予想％"].sum()
        df_sorted.loc[0, "予想％"] = round(df_sorted.loc[0, "予想％"] + diff, 1)

        # --- 3. 予想カードの表示 ---
        st.markdown("### 🏁 総合予想％")
        res_cols = st.columns(3)
        for i, row in df_sorted.iterrows():
            rank = i + 1
            boat, pct = int(row["艇番"]), float(row["予想％"])
            colors = {1: ("#fff1c1", "#f39c12", "🥇"), 2: ("#f8f9fa", "#bdc3c7", "🥈"), 3: ("#ffede5", "#e67e22", "🥉")}
            bg, brd, icon = colors.get(rank, ("#ffffff", "#dfe6e9", f"{rank}位"))

            with res_cols[i % 3]:
                st.markdown(f"""
                    <div style="background:{bg}; border:2px solid {brd}; border-radius:12px; padding:15px; text-align:center; box-shadow:0 2px 4px rgba(0,0,0,0.05); margin-bottom:10px;">
                        <div style="font-size:12px; color:#636e72;">{icon}</div>
                        <div style="font-size:26px; font-weight:bold; color:#2d3436;">{boat}<span style="font-size:14px;">号艇</span></div>
                        <div style="font-size:22px; font-weight:bold; color:#e74c3c;">{pct:.1f}%</div>
                    </div>
                """, unsafe_allow_html=True)

# ==========================================
# 3. 実行エリア
# ==========================================
if __name__ == "__main__":
    st.set_page_config(page_title="Boat Race Ranking Tool", layout="wide")
    render_7step_with_styled_table()
