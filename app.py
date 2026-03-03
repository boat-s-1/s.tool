import streamlit as st
import pandas as pd

# ==========================================
# 1. 設定・定数エリア
# ==========================================
PLACE_NAME = "ボートレース予想ツール"
# スライダーの値を記号に変換するマップ
def get_symbol(val):
    if val >= 90: return "◎"
    if val >= 70: return "○"
    if val >= 50: return "▲"
    if val >= 30: return "△"
    if val >= 10: return "×"
    return "無"

# ==========================================
# 2. UI関数エリア
# ==========================================
def render_slider_eval_tool():
    st.header(f"🎯 {PLACE_NAME} - 事前簡易予想")
    
    # 指標の重み（固定または調整用）
    WEIGHTS = {"モーター": 0.25, "当地勝率": 0.2, "枠番勝率": 0.3, "枠番スタート": 0.25}

    # --- 入力フォーム ---
    with st.form("slider_input_form"):
        st.markdown("##### 🚤 各艇の評価をスライドバーで入力")
        
        boat_evals = {}
        
        # 2列×3行で6艇分を配置
        for row in range(3):
            cols = st.columns(2)
            for col in range(2):
                i = row * 2 + col + 1
                with cols[col]:
                    st.markdown(f"""
                        <div style="background:#f8f9fa; border-left:5px solid #007bff; padding:10px; border-radius:5px; margin-bottom:5px;">
                            <b style="font-size:18px;">{i}号艇</b>
                        </div>
                    """, unsafe_allow_html=True)
                    
                    # 各項目をスライダーで入力
                    m_val = st.slider("🚀 モーター", 0, 100, 0, 10, key=f"sld_m_{i}")
                    t_val = st.slider("🏟️ 当地勝率", 0, 100, 0, 10, key=f"sld_t_{i}")
                    w_val = st.slider("📈 枠番勝率", 0, 100, 0, 10, key=f"sld_w_{i}")
                    s_val = st.slider("⏱️ 枠番ST", 0, 100, 0, 10, key=f"sld_s_{i}")

                    # スコア計算（スライダーの値をそのまま使用）
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
            st.warning("⚠️ スライダーを動かして評価を入力してください。")
            return

        # ％正規化
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
            colors = {1: ("#fff1c1", "#f5b700", "🥇"), 2: ("#f0f0f0", "#b5b5b5", "🥈"), 3: ("#ffe4d6", "#e39a6f", "🥉")}
            bg, brd, icon = colors.get(rank, ("#ffffff", "#eeeeee", f"{rank}位"))

            with res_cols[i % 3]:
                st.markdown(f"""
                    <div style="background:{bg}; border:2px solid {brd}; border-radius:15px; padding:15px; text-align:center; box-shadow:0 4px 6px rgba(0,0,0,0.1); margin-bottom:10px;">
                        <div style="font-size:14px; color:#666;">{icon}</div>
                        <div style="font-size:28px; font-weight:bold; color:#111;">{boat}<span style="font-size:16px;">号艇</span></div>
                        <div style="font-size:22px; font-weight:bold; color:#d32f2f;">{pct:.1f}%</div>
                    </div>
                """, unsafe_allow_html=True)

# ==========================================
# 3. 実行エリア
# ==========================================
if __name__ == "__main__":
    st.set_page_config(page_title="Boat Race Slider Predictor", layout="wide")
    render_slider_eval_tool()
