import streamlit as st
import pandas as pd
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import io
import datetime
import plotly.express as px

# ==========================================
# 1. 基本設定
# ==========================================
st.set_page_config(page_title="競艇Pro Analytica", layout="wide", page_icon="🎯")

PLACE_CORRECTIONS = {
    "桐生": {"展示": 0.2, "直線": 0.2, "回り足": 0.3, "一周": 0.3},
    "戸田": {"展示": 0.1, "直線": 0.5, "回り足": 0.2, "一周": 0.2},
    "江戸川": {"展示": 0.1, "直線": 0.2, "回り足": 0.5, "一周": 0.2},
    "福岡": {"展示": 0.1, "直線": 0.2, "回り足": 0.5, "一周": 0.2},
    "住之江": {"展示": 0.4, "直線": 0.1, "回り足": 0.3, "一周": 0.2},
    "大村": {"展示": 0.5, "直線": 0.1, "回り足": 0.2, "一周": 0.2},
    "DEFAULT": {"展示": 0.25, "直線": 0.25, "回り足": 0.25, "一周": 0.25}
}

get_symbol = lambda val: {6: "◎", 5: "○", 4: "▲", 3: "△", 2: "×", 1: "・", 0: "無"}.get(val, "無")
boat_bg = {1: "#ffffff", 2: "#333333", 3: "#e03131", 4: "#1971c2", 5: "#fcc419", 6: "#2f9e44"}
boat_tx = {1: "#000000", 2: "#ffffff", 3: "#ffffff", 4: "#ffffff", 5: "#000000", 6: "#ffffff"}
boat_colors_rgb = {1: (255,255,255), 2: (51,51,51), 3: (224,49,49), 4: (25,113,194), 5: (252,196,25), 6: (47,158,68)}

# --- 画像生成関数（エラー箇所修正済み） ---
def create_final_image(place, num, df_live):
    width, height = 1200, 800
    img = Image.new('RGB', (width, height), color=(245, 245, 245))
    draw = ImageDraw.Draw(img)
    
    try:
        f_title = ImageFont.load_default(); f_large = ImageFont.load_default(); f_mid = ImageFont.load_default()
    except:
        f_title = f_large = f_mid = ImageFont.load_default()

    # ヘッダー
    draw.rectangle([0, 0, width, 150], fill=(30, 40, 60))
    draw.text((40, 40), f"{place} {num}R FINAL YOSO", fill=(255, 255, 255))

    # ランキング描画
    top3 = df_live.head(3)
    for i, row in enumerate(top3.itertuples()):
        y_off = 180 + (i * 180)
        b_no = int(row.艇番)
        # 期待値の取得（カラム名に%が含まれる場合の安全なアクセス）
        exp_val = getattr(row, "_2") # 2番目のデータカラム(期待値%)にアクセス
        
        draw.rounded_rectangle([50, y_off, 1150, y_off + 150], radius=15, fill=boat_colors_rgb[b_no], outline=(0,0,0), width=2)
        txt_color = (0,0,0) if b_no in [1, 5] else (255,255,255)
        draw.text((80, y_off + 30), f"RANK {i+1}", fill=txt_color)
        draw.text((250, y_off + 15), f"BOAT: {b_no}", fill=txt_color)
        draw.text((500, y_off + 45), f"EXPECTED: {exp_val}%", fill=txt_color)

    return img

# ==========================================
# 2. メイン
# ==========================================
with st.sidebar:
    st.header("📋 レース情報")
    r_place = st.selectbox("開催地", ["桐生", "戸田", "江戸川", "平和島", "多摩川", "浜名湖", "蒲郡", "常滑", "津", "三国", "びわこ", "住之江", "尼崎", "鳴門", "丸亀", "児島", "宮島", "徳山", "下関", "若松", "芦屋", "福岡", "佐賀", "大村"])
    r_num = st.number_input("レース番号", 1, 12, 12)

tab1, tab2, tab3 = st.tabs(["📝 簡易事前予想", "🔥 直前気配解析", "📸 SNS画像生成"])

with tab1:
    st.subheader("📊 事前データスコアリング")
    with st.form("pre_form"):
        pre_raw = []
        cols = st.columns(3)
        for i in range(1, 7):
            with cols[(i-1)%3]:
                st.markdown(f'<div style="background:{boat_bg[i]}; color:{boat_tx[i]}; padding:5px; border-radius:5px; text-align:center; font-weight:bold;">{i}号艇</div>', unsafe_allow_html=True)
                m = st.select_slider(f"モーター", range(7), 0, get_symbol, key=f"pre_m_{i}")
                t = st.select_slider(f"当地勝率", range(7), 0, get_symbol, key=f"pre_t_{i}")
                w = st.select_slider(f"枠番勝率", range(7), 0, get_symbol, key=f"pre_w_{i}")
                s = st.select_slider(f"枠番ST", range(7), 0, get_symbol, key=f"pre_s_{i}")
                score = (m * 0.25 + t * 0.20 + w * 0.35 + s * 0.20)
                pre_raw.append({"艇番": i, "score": score})
        st.form_submit_button("事前ランク確定")

with tab2:
    st.subheader(f"🏟️ {r_place} 直前気配補正解析")
    with st.form("live_form"):
        live_raw = []
        l_cols = st.columns(2)
        for i in range(1, 7):
            with l_cols[(i-1)%2]:
                st.markdown(f'<div style="background:{boat_bg[i]}; color:{boat_tx[i]}; padding:2px; border-radius:4px; text-align:center; font-weight:bold;">{i}号艇</div>', unsafe_allow_html=True)
                f1 = st.select_slider(f"展示気配", range(7), 0, get_symbol, key=f"live_f1_{i}")
                f2 = st.select_slider(f"直線", range(7), 0, get_symbol, key=f"live_f2_{i}")
                f3 = st.select_slider(f"回り足", range(7), 0, get_symbol, key=f"live_f3_{i}")
                f4 = st.select_slider(f"一周", range(7), 0, get_symbol, key=f"live_f4_{i}")
                corr = PLACE_CORRECTIONS.get(r_place, PLACE_CORRECTIONS["DEFAULT"])
                live_score = (f1 * corr["展示"] + f2 * corr["直線"] + f3 * corr["回り足"] + f4 * corr["一周"])
                live_raw.append({"艇番": i, "score": live_score})
        
        if st.form_submit_button(f"解析実行"):
            df_live = pd.DataFrame(live_raw).sort_values("score", ascending=False)
            df_live["期待値％"] = (df_live["score"] / df_live["score"].sum() * 100).round(1)
            st.session_state["final_res"] = df_live
            st.success("解析完了！タブ3で画像を確認してください。")
            st.dataframe(df_live, hide_index=True)

with tab3:
    if "final_res" in st.session_state:
        if st.button("✨ 予想画像を生成"):
            img = create_final_image(r_place, r_num, st.session_state["final_res"])
            st.image(img, use_container_width=True)
            
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            st.download_button("💾 画像保存", buf.getvalue(), f"{r_place}_{r_num}R.png", "image/png")
    else:
        st.info("タブ2で「解析実行」を行ってください。")
