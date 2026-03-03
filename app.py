import streamlit as st
import pandas as pd

# ==========================================
# 1. 設定・定数エリア
# ==========================================
PLACE_NAME = "ボートレース予想ツール"

# 数値をラベルに変換する関数
def get_label(val):
    labels = {6: "◎ (極)", 5: "○ (良)", 4: "▲ (中)", 3: "△ (可)", 2: "× (薄)", 1: "・ (微)", 0: "無"}
    return labels.get(val, "無")

# ==========================================
# 2. UI関数エリア
# ==========================================
def render_7step_slider_tool():
    st.header(f"🎯 {PLACE_NAME} - 事前簡易予想")
    
    # 指標の重み（合計で 1.0 になるよう設定）
    WEIGHTS = {"モーター": 0.25, "当地勝率": 0.2, "枠番勝率": 0.3, "枠番スタート": 0.25}

    # --- 入力フォーム ---
    with st.form("slider_7step_form"):
        st.markdown("##### 🚤 艇ごとの評価 (0:無 〜 6:極)")
        
        boat_evals = {}
        
        # 2列×3行で6艇分を配置
        for row in range(3):
            cols = st.columns(2)
            for col in range(2):
                i = row * 2 + col + 1
                with cols[col]:
                    st.markdown(f"""
                        <div style="background:#f1f3f5; border-left:5px solid #2d3436; padding:8px 12px; border-radius:4px; margin-bottom:10px;">
                            <b style="font-size:18px;">{i}号艇</b>
                        </div>
                    """, unsafe_allow_html=True)
                    
                    # 7段階スライダー (0, 1, 2, 3, 4, 5, 6)
                    # format_func を使って、スライダー上に ◎ などのラベルを表示
                    m_val = st.select_slider(f"🚀 モーター", options=range(7), value=0, format_func=get_label, key=f"s7_m_{i}")
                    t_val = st.select_slider(f"🏟️ 当地勝率", options=range(7), value=0, format_func=get_label, key=f"s7_t_{i}")
                    w_val = st.select_slider(f"📈 枠番勝率", options=range(7), value=0, format_func=get_label, key=f"s7_w_{i}")
                    s_val = st.select_slider(f"⏱️ 枠番ST", options=range(7), value=0, format_func=get_label, key=f"s7_s_{i}")

                    # スコア計算
                    score = (
                        m_val * WEIGHTS["モーター"]
                        + t_val * WEIGHTS["当地勝率"]
                        + w_val * WEIGHTS["枠番勝率"]
                        + s_val * WEIGHTS["枠番スタート"]
                    )
                    boat_evals[i] = round(score, 3)
            st.divider()

        submitted = st.form_submit_button("📊 予想カードを生成", use_container_width=True, type="primary")

    # --- 結果表示エリア ---
    if submitted:
        df = pd.DataFrame([{"艇番": k, "score": v} for k, v in boat_evals.items()])
        total = df["score"].sum()

        if total == 0:
            st.warning("⚠️ 評価がすべて「無」です。スライダーを動かしてください。")
            return

        # ％算出
        df["予想％"] = (df["score"] / total * 100).round(1)
        df = df.sort_values("予想％", ascending=False).reset_index(drop=True)
        
        # 100%補正
        diff = 100.0 - df["予想％"].sum()
        df.loc[0, "予想％"] = round(df.loc[0, "予想％"] + diff, 1)

        st.markdown("### 🏁 予想結果")
        res_cols = st.columns(3)
        for i, row in df.iterrows():
            rank = i + 1
            boat = int(row["艇番"])
            pct = float(row["予想％"])

            # デザイン設定
            colors = {1: ("#fff1c1", "#f39c12", "🥇"), 2: ("#f8f9fa", "#bdc3c7", "🥈"), 3: ("#ffede5", "#e67e22", "🥉")}
            bg, brd, icon = colors.get(rank, ("#ffffff", "#dfe6e9", f"{rank}位"))

            with res_cols[i % 3]:
                st.markdown(f"""
                    <div style="background:{bg}; border:2px solid {brd}; border-radius:12px; padding:15px; text-align:center; box-shadow:0 2px 4px rgba(0,0,0,0.05); margin-bottom:10px;">
                        <div style="font-size:12px; color:#636e72;">{icon}</div>
                        <div style="font-size:26px; font-weight:bold; color:#2d3436;">{boat}<span style="font-size:14px;">号艇</span></div>
                        <div style="font-size:20px; font-weight:bold; color:#e74c3c;">{pct:.1f}%</div>
                    </div>
                """, unsafe_allow_html=True)

# ==========================================
# 3. 実行エリア
# ==========================================
if __name__ == "__main__":
    st.set_page_config(page_title="Boat 7-Step Slider", layout="wide")
    render_7step_slider_tool()
