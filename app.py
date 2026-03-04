import streamlit as st
import pandas as pd
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import io
import datetime
import os
import urllib.request
import gspread
from google.oauth2.service_account import Credentials
import plotly.express as px

# ==========================================
# 1. 基本設定・認証
# ==========================================
st.set_page_config(page_title="競艇専門紙 Pro Analytica", layout="wide", page_icon="📝")

# 日本語フォントを自動ダウンロードする関数
@st.cache_resource
def get_japanese_font():
    font_url = "https://github.com/googlefonts/noto-cjk/raw/main/Sans/OTF/Japanese/NotoSansCJKjp-Bold.otf"
    font_path = "NotoSansCJKjp-Bold.otf"
    if not os.path.exists(font_path):
        with st.spinner("日本語フォントを準備中..."):
            try:
                urllib.request.urlretrieve(font_url, font_path)
            except Exception as e:
                st.error(f"フォントのダウンロードに失敗しました: {e}")
                return None
    return font_path

# ==========================================
# 2. 画像生成エンジン（ズレ修正版）
# ==========================================
def create_perfect_newspaper(place, race_num, result_df):
    w, h = 1300, 1100 
    paper_color = (245, 242, 230) 
    img = Image.new('RGB', (w, h), paper_color)
    draw = ImageDraw.Draw(img)
    
    font_p = get_japanese_font()
    if not font_p: return None

    f_header = ImageFont.truetype(font_p, 45)
    f_title = ImageFont.truetype(font_p, 90)
    f_mark = ImageFont.truetype(font_p, 110)
    f_label = ImageFont.truetype(font_p, 38)
    f_boat = ImageFont.truetype(font_p, 65)
    f_index = ImageFont.truetype(font_p, 42)
    f_footer = ImageFont.truetype(font_p, 48)

    draw.rectangle([30, 30, w-30, h-30], outline=(0, 0, 0), width=6)
    draw.line([30, 160, w-30, 160], fill=(0, 0, 0), width=4)
    
    draw.text((60, 65), "競艇専門紙 PRO ANALYTICA", fill=(0, 0, 0), font=f_header)
    draw.text((w-320, 65), f"{datetime.date.today().strftime('%Y/%m/%d')}", fill=(0, 0, 0), font=f_header)
    draw.text((60, 190), f"{place}ボート 最終結論 第{race_num}R", fill=(180, 0, 0), font=f_title)
    
    start_x, first_col_x, col_w, row_y_base = 80, 240, 170, 320
    draw.text((start_x, row_y_base + 60), "本 紙\n予 想", fill=(50, 50, 50), font=f_label, spacing=10)
    draw.text((start_x, row_y_base + 290), "艇 番", fill=(50, 50, 50), font=f_label)
    draw.text((start_x, row_y_base + 515), "指 数", fill=(50, 50, 50), font=f_label)
    draw.line([30, row_y_base, w-30, row_y_base], fill=(0,0,0), width=3)

    temp_df = result_df.copy()
    temp_df["rank"] = temp_df["expected_pct"].rank(ascending=False, method='min')

    boat_bg = {1: "#ffffff", 2: "#333333", 3: "#ff3b3b", 4: "#007bff", 5: "#ffc107", 6: "#28a745"}
    boat_tx = {1: "#000000", 2: "#ffffff", 3: "#ffffff", 4: "#ffffff", 5: "#000000", 6: "#ffffff"}

    for i in range(1, 7):
        curr_x_center = first_col_x + (i-1) * col_w + (col_w // 2)
        row = temp_df[temp_df["boat_num"] == i].iloc[0]
        line_x = first_col_x + (i-1) * col_w
        draw.line([line_x, row_y_base, line_x, row_y_base + 630], fill=(0,0,0), width=2)
        
        rank = row["rank"]
        mark = "◎" if rank == 1 else "○" if rank == 2 else "▲" if rank == 3 else "△" if rank == 4 else "・"
        m_w = f_mark.getlength(mark)
        draw.text((curr_x_center - m_w//2, row_y_base + 40), mark, fill=(200, 0, 0), font=f_mark)
        
        b_rgb = tuple(int(boat_bg[i].lstrip('#')[j:j+2], 16) for j in (0, 2, 4))
        draw.ellipse([curr_x_center - 65, row_y_base + 260, curr_x_center + 65, row_y_base + 390], fill=b_rgb, outline=(0,0,0), width=3)
        n_w = f_boat.getlength(str(i))
        draw.text((curr_x_center - n_w//2, row_y_base + 278), str(i), fill=boat_tx[i], font=f_boat)
        
        idx_str = f"{row.expected_pct}%"
        idx_w = f_index.getlength(idx_str)
        draw.text((curr_x_center - idx_w//2, row_y_base + 515), idx_str, fill=(0, 0, 0), font=f_index)

    draw.rectangle([60, 960, w-60, 1070], fill=(255, 255, 255), outline=(0,0,0), width=3)
    top_3 = result_df.sort_values("expected_pct", ascending=False)["boat_num"].tolist()[:3]
    recommend_text = f"推奨買い目: {top_3[0]} = {top_3[1]} - 全、 {top_3[0]} - {top_3[2]} - 流し (3連単)"
    draw.text((100, 990), recommend_text, fill=(0, 0, 0), font=f_footer)
    
    return img

def get_yoso_mark(val):
    marks = {6: "◎", 5: "○", 4: "▲", 3: "△", 2: "×", 1: "・", 0: "－"}
    return marks.get(val, "－")

# ==========================================
# 3. メインアプリ
# ==========================================
with st.sidebar:
    st.title("📝 専門紙設定")
    r_place = st.selectbox("📍 開催地", ["桐生", "戸田", "江戸川", "平和島", "多摩川", "浜名湖", "蒲郡", "常滑", "津", "三国", "びわこ", "住之江", "尼崎", "鳴門", "丸亀", "児島", "宮島", "徳山", "下関", "若松", "芦屋", "福岡", "佐賀", "大村"])
    r_num = st.number_input("🏁 レース番号", 1, 12, 1)
    race_type_val = st.radio("📊 解析対象", ["混合", "女子"], horizontal=True)
    st.divider()
    w_m = st.slider("モーター", 0, 100, 30, step=10)
    w_t = st.slider("当地勝率", 0, 100, 20, step=10)
    w_w = st.slider("枠番勝率", 0, 100, 30, step=10)
    w_s = st.slider("スタート", 0, 100, 20, step=10)
    
    if st.button("🔄 統計データ取得", use_container_width=True):
        try:
            creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"])
            gc = gspread.authorize(creds)
            sh = gc.open_by_key("1lN794iGtyGV2jNwlYzUA8wEbhRwhPM7FxDAkMaoJss4")
            ws = sh.worksheet(f"{r_place}_{race_type_val}統計")
            st.session_state["base_df"] = pd.DataFrame(ws.get_all_records())
            st.success("取得完了")
        except Exception as e:
            st.error(f"エラー: {e}")

st.title(f"📰 競艇専門紙 Analytica - {r_place}")
tab_analytica, tab_sns = st.tabs(["🔍 解析・予想入力", "📰 予想紙画像生成"])

with tab_analytica:
    col_l, col_r = st.columns([1, 1.5])
    with col_l:
        if "base_df" in st.session_state:
            st.subheader("🤖 統計分析結果")
            st.plotly_chart(px.pie(names=["モーター", "当地", "枠番", "ST"], values=[w_m, w_t, w_w, w_s], hole=0.4), use_container_width=True)
        else:
            st.info("サイドバーからデータを取得してください")

    with col_r:
        st.subheader("📝 本日の気配評価")
        with st.form("input_form"):
            results = []
            grid = st.columns(2)
            for i in range(1, 7):
                with grid[(i-1)%2]:
                    bg = {1: "#ffffff", 2: "#333333", 3: "#ff3b3b", 4: "#007bff", 5: "#ffc107", 6: "#28a745"}[i]
                    tx = {1: "#000000", 2: "#ffffff", 3: "#ffffff", 4: "#ffffff", 5: "#000000", 6: "#ffffff"}[i]
                    st.markdown(f'<div style="background:{bg}; color:{tx}; padding:5px; border-radius:5px; text-align:center; font-weight:bold;">{i}号艇</div>', unsafe_allow_html=True)
                    m = st.select_slider(f"モーター_{i}", range(7), 3, get_yoso_mark)
                    t = st.select_slider(f"当地_{i}", range(7), 3, get_yoso_mark)
                    w = st.select_slider(f"枠番_{i}", range(7), 3, get_yoso_mark)
                    s = st.select_slider(f"ST_{i}", range(7), 3, get_yoso_mark)
                    score = (m * w_m/100 + t * w_t/100 + w * w_w/100 + s * w_s/100)
                    results.append({"boat_num": i, "score": score, "m": m, "t": t, "w": w, "s": s})
            submitted = st.form_submit_button("🔥 予想を確定", use_container_width=True, type="primary")

        if submitted:
            df = pd.DataFrame(results)
            df["expected_pct"] = (df["score"] / df["score"].sum() * 100).round(1) if df["score"].sum() > 0 else 0
            st.session_state["analytica_result"] = df
            st.success("解析完了！「予想紙画像生成」タブへ。")

with tab_sns:
    if "analytica_result" in st.session_state:
        if st.button("✨ 専門紙画像を生成", use_container_width=True):
            img = create_perfect_newspaper(r_place, r_num, st.session_state["analytica_result"])
            if img:
                st.image(img, use_container_width=True)
                buf = io.BytesIO()
                img.save(buf, format="PNG")
                st.download_button("📲 保存", buf.getvalue(), f"yoso_{r_place}.png", "image/png", use_container_width=True)
    else:
        st.warning("予想入力タブで確定させてください")
