import streamlit as st
import pandas as pd

# ==========================================
# 1. 設定・定数エリア
# ==========================================
PLACE_NAME = "ボートレース予想ツール"
OPTIONS = ["◎", "○", "▲", "△", "×", "無"]
SYMBOL_VALUES = {"◎": 100, "○": 80, "▲": 60, "△": 40, "×": 20, "無": 0}

# ==========================================
# 2. UI関数エリア
# ==========================================
def render_pre_eval_tool():
    st.header(f"🎯 {PLACE_NAME} - 事前簡易予想")
    
    # --- 重み付け設定 (スライドバー形式で調整可能) ---
    with st.expander("⚖️ 指標の重要度（重み付け）を調整", expanded=False):
        col_w1, col_w2, col_w3, col_w4 = st.columns(4)
        w_m = col_w1.slider("モーター", 0.0, 1.0, 0.25, 0.05)
        w_t = col_w2.slider("当地勝率", 0.0, 1.0, 0.20, 0.05)
        w_w = col_w3.slider("枠番勝率", 0.0, 1.0, 0.30, 0.05)
        w_s = col_w4.slider("枠番ST", 0.0, 1.0, 0.25, 0.05)
        weights = {"モーター": w_m, "当地勝率": w_t, "枠番勝率": w_w, "枠番スタート": w_s}

    # --- 入力フォーム ---
    with st.form("speed_input_form"):
        st.markdown("##### 🚤 艇番ごとの評価を一括入力 (1号艇 → 6号艇)")
        
        # 評価データを保持する辞書
        input_results = {i: {} for i in range(1, 7)}
        
        # 項目ごとに横一行のラジオボタンを作成
        items = [
            ("🚀 モーター評価", "m", "モーター"),
            ("🏟️ 当地勝率", "t", "当地勝率"),
            ("📈 枠番勝率", "w", "枠番勝率"),
            ("⏱️ 枠番スタート", "s", "枠番スタート")
        ]

        for label, key_p, data_key in items:
            st.write(f"**{label}**")
            cols = st.columns(6)
            for i in range(1, 7):
                with cols[i-1]:
                    # label_visibility="collapsed" で艇番表示を消し、横並びを強調
                    val = st.radio(
                        f"{i}号艇", OPTIONS, index=5, 
                        key=f"eval_{key_p}_{i}", 
                        label_visibility="collapsed"
                    )
                    input_results[i][data_key] = val
            st.divider()

        submitted = st.form_submit_button("📊 予想カードを生成", use_container_width=True, type="primary")

    # --- 計算・結果表示エリア ---
    if submitted:
        calculate_and_show_results(input_results, weights)

def calculate_and_show_results(input_results, weights):
    boat_scores = {}
    for i in range(1, 7):
        res = input_results[i]
        score = (
            SYMBOL_VALUES[res["モーター"]] * weights["モーター"]
            + SYMBOL_VALUES[res["当地勝率"]] * weights["当地勝率"]
            + SYMBOL_VALUES[res["枠番勝率"]] * weights["枠番勝率"]
            + SYMBOL_VALUES[res["枠番スタート"]] * weights["枠番スタート"]
        )
        boat_scores[i] = round(score, 3)

    # DataFrame化して％算出
    df = pd.DataFrame([{"艇番": k, "score": v} for k, v in boat_scores.items()])
    total = df["score"].sum()

    if total == 0:
        st.warning("⚠️ すべて『無』のため計算できません。評価を入力してください。")
        return

    # ％正規化と並び替え
    df["予想％"] = (df["score"] / total * 100).round(1)
    df = df.sort_values("予想％", ascending=False).reset_index(drop=True)
    
    # 合計100%への端数調整
    diff = 100.0 - df["予想％"].sum()
    df.loc[0, "予想％"] = round(df.loc[0, "予想％"] + diff, 1)

    # カード表示
    st.markdown("### 🏁 予想結果")
    res_cols = st.columns(3)
    for i, row in df.iterrows():
        rank = i + 1
        boat = int(row["艇番"])
        pct = float(row["予想％"])

        # 順位に応じたデザイン設定
        styles = {
            1: {"bg": "#fff1c1", "border": "#f5b700", "icon": "🥇"},
            2: {"bg": "#f0f0f0", "border": "#b5b5b5", "icon": "🥈"},
            3: {"bg": "#ffe4d6", "border": "#e39a6f", "icon": "🥉"}
        }
        s = styles.get(rank, {"bg": "#ffffff", "border": "#eeeeee", "icon": f"{rank}位"})

        with res_cols[i % 3]:
            st.markdown(f"""
                <div style="background:{s['bg']}; border:2px solid {s['border']}; border-radius:15px; padding:15px; text-align:center; box-shadow:0 4px 6px rgba(0,0,0,0.1); margin-bottom:10px;">
                    <div style="font-size:14px; color:#666;">{s['icon']}</div>
                    <div style="font-size:28px; font-weight:bold; color:#111;">{boat}<span style="font-size:16px;">号艇</span></div>
                    <div style="font-size:22px; font-weight:bold; color:#d32f2f;">{pct:.1f}%</div>
                </div>
            """, unsafe_allow_html=True)

    # 詳細テーブル
    with st.expander("詳細データを確認"):
        st.table(df)

# ==========================================
# 3. 実行エリア
# ==========================================
if __name__ == "__main__":
    st.set_page_config(page_title="Boat Race Predictor", layout="wide")
    render_pre_eval_tool()
