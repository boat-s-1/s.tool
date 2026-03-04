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
# 2. 画像生成エンジン
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
    r_place = st.selectbox("📍 開催地", ["桐生", "戸田", "江戸川", "平和島", "多摩川", "浜名湖", "蒲郡", "常滑", "津", "三国", "びわこ", "住之江", "尼崎", "鳴門", "丸亀", "児島",
