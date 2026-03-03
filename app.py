import streamlit as st
import pandas as pd

# ==========================================
# 1. 設定・定数エリア
# ==========================================
PLACE_NAME = "ボートレース予想ツール"

def get_label(val):
    labels = {6: "◎ (極)", 5: "○ (良)", 4: "▲ (中)", 3: "△ (可)", 2: "× (薄)", 1: "・ (微)", 0: "無"}
    return labels.get(val, "無")

# ==========================================
# 2. UI関数エリア
# ==========================================
def render_7step_with_ranking():
    st.header(f"🎯 {PLACE_NAME} - 事前簡易予想")
    
    # 指標の重み
    WEIGHTS = {"モーター": 0.25, "当地勝率": 0.2, "枠番勝率": 0.3, "枠番スタート": 0.25}

    # --- 入力フォーム ---
    with st.form("slider_7step_form"):
        st.markdown("##### 🚤 艇ごとの評価入力 (0:無 〜 6:極)")
        
        # データを保持するためのリスト
        raw_data = []
        
        for row in range(3):
            cols = st.columns(2)
            for col in range(2):
                i = row * 2 + col + 1
                with cols[col]:
                    st.markdown(f"""<div style="background:#f1f3f5; border-left:5px solid #2d3436; padding:5px 10px; border-radius:4px; margin-bottom:5px;"><b>{i}号艇</b></div>""", unsafe_allow_html=True)
                    
                    m = st.select_slider(f"🚀 モーター", options=range(7), value=0, format_func=get_label, key=f"v_m_{i}")
                    t = st.select_slider(f"🏟️ 当地勝率", options=range(7), value=0, format_func=get_label, key=f"v_t_{i}")
                    w = st.select_slider(f"📈 枠番勝率", options=range(7), value=0, format_func=get_label, key=f"v_w_{i}")
                    s = st.select_slider(f"⏱️ 枠番ST", options=range(7), value=0, format_func=get_label, key=f"v_s_{i}")

                    # スコア計算
                    total_score = (m * WEIGHTS["モーター"] + t * WEIGHTS["当地勝率"] + w * WEIGHTS["枠番勝率"] + s * WEIGHTS["枠番スタート"])
                    
                    raw_data.append({
                        "艇番": i,
                        "モーター": m,
                        "当地勝率": t,
                        "枠番勝率": w,
                        "枠番スタート": s,
                        "総合スコア": round(total_score, 3)
                    })
            st.divider()

        submitted = st.form_submit_button("📊 予想解析を実行", use_container_width=True, type="primary")

    if submitted:
        df = pd.DataFrame(raw_data)
        if df["総合スコア"].sum() == 0:
            st.warning("⚠️ 評価を入力してください。")
            return

        # --- 1. 項目別順位の表示 ---
        st.markdown("### 📋 項目別評価ランキング")
        rank_cols = st.columns(4)
        items = ["モーター", "当地勝率", "枠番勝率", "枠番スタート"]
        icons = ["🚀", "🏟️", "📈", "⏱️"]

        for idx, item in enumerate(items):
            with rank_cols[idx]:
                st.markdown(f"**{icons[idx]} {item}**")
                # 項目ごとにソート
                df_rank = df[["艇番", item]].sort_values(by=[item, "艇番"], ascending=[False, True])
                for rank_num, (_, r) in enumerate(df_rank.iterrows(), 1):
                    label = get_label(r[item]).split()[0] # 「◎」だけ抽出
                    color = "#d32f2f" if rank_num == 1 else "#333"
                    st.markdown(f"{rank_num}位: **{int(r['艇番'])}号艇** <small>({label})</small>", unsafe_allow_html=True)

        st.divider()

        # --- 2. 総合％予想の計算 ---
        total_sum = df["総合スコア"].sum()
        df["予想％"] = (df["総合スコア"] / total_sum * 100).round(1)
        df_sorted = df.sort_values("予想％", ascending=False).reset_index(drop=True)
        
        # 100%補正
        diff = 100.0 - df_sorted["予想％"].sum()
        df_sorted.loc[0, "予想％"] = round(df_sorted.loc[0, "予想％"] + diff, 1)

        # --- 3. 予想カードの表示 ---
        st.markdown("### 🏁 総合予想％")
        res_cols = st.columns(3)
        for i, row in df_sorted.iterrows():
            rank = i + 1
            boat = int(row["艇番"])
            pct = float(row["予想％"])

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

        # 詳細データ
        with st.expander("詳細スコアリングデータ"):
            st.dataframe(df_sorted, use_container_width=True, hide_index=True)

# ==========================================
# 3. 実行エリア
# ==========================================
if __name__ == "__main__":
    st.set_page_config(page_title="Boat Race Analysis Tool", layout="wide")
    render_7step_with_ranking()
