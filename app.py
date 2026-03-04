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

# ==========================================
# 1. 基本設定・フォント準備
# ==========================================
st.set_page_config(page_title="競艇専門紙 Pro Analytica", layout="wide")

@st.cache_resource
def get_japanese_font():
    font_url = "https://github.com/googlefonts/noto-cjk/raw/main/Sans/OTF/Japanese/NotoSansCJKjp-Bold.otf"
    font_path = "NotoSansCJKjp-Bold.otf"
    if not os.path.exists(font_path):
        try:
            urllib.request.urlretrieve(font_url, font_path)
        except:
            return None
    return font_path

# ==========================================
# 2. 画像生成コアエンジン (究極レイアウト版)
# ==========================================
def create_perfect_newspaper(place, race_num, result_df):
    # キャンバスサイズ (横を広げてゆとりを持たせる)
    w, h = 1300, 1100 
    paper_color = (245, 242, 230) 
    img = Image.new('RGB', (w, h), paper_color)
    draw = ImageDraw.Draw(img)
    
    font_p = get_japanese_font()
    if not font_p: return None

    # 各種フォントサイズ
    f_header = ImageFont.truetype(font_p, 45)  # ヘッダー用
    f_title = ImageFont.truetype(font_p, 90)   # 桐生ボート...
    f_mark = ImageFont.truetype(font_p, 110)  # ◎○
    f_label = ImageFont.truetype(font_p, 38)   # 本紙予想などの見出し
    f_boat = ImageFont.truetype(font_p, 65)   # 艇番
    f_index = ImageFont.truetype(font_p, 42)  # 16.7%
    f_footer = ImageFont.truetype(font_p, 48) # 推奨買い目

    # --- デザインのベース（枠線） ---
    draw.rectangle([30, 30, w-30, h-30], outline=(0, 0, 0), width=6) # 外枠
    draw.line([30, 160, w-30, 160], fill=(0, 0, 0), width=4)        # ヘッダー下
    
    # ヘッダーテキスト
    draw.text((60, 65), "競艇専門紙 PRO ANALYTICA", fill=(0, 0, 0), font=f_header)
    draw.text((w-320, 65), f"{datetime.date.today().strftime('%Y/%m/%d')}", fill=(0, 0, 0), font=f_header)
    
    # タイトル（中央寄せ気味）
    title_text = f"{place}ボート 最終結論 第{race_num}R"
    draw.text((60, 190), title_text, fill=(180, 0, 0), font=f_title)
    
    # --- 表のレイアウト設定 ---
    start_x = 80       # ラベルの開始位置
    first_col_x = 240  # 1号艇の開始位置
    col_w = 170        # 1艇あたりの幅
    row_y_base = 320   # 表の開始高さ
    
    # 行の高さ
    h_yoso = 150
    h_teiban = 220
    h_shisu = 150

    # 表の項目ラベル（左側）
    draw.text((start_x, row_y_base + 60), "本 紙\n予 想", fill=(50, 50, 50), font=f_label, spacing=10)
    draw.text((start_x, row_y_base + 290), "艇 番", fill=(50, 50, 50), font=f_label)
    draw.text((start_x, row_y_base + 515), "指 数", fill=(50, 50, 50), font=f_label)

    # 横の仕切り線
    draw.line([30, row_y_base, w-30, row_y_base], fill=(0,0,0), width=3) # 表のトップ
    draw.line([190, row_y_base + h_yoso + 50, w-30, row_y_base + h_yoso + 50], fill=(150,150,150), width=1)
    draw.line([190, row_y_base + h_yoso + h_teiban + 30, w-30, row_y_base + h_yoso + h_teiban + 30], fill=(150,150,150), width=1)

    # 艇ごとのデータ描画
    boat_colors = {1: "#ffffff", 2: "#333333", 3: "#ff3b3b", 4: "#007bff", 5: "#ffc107", 6: "#28a745"}
    text_colors = {1: "#000000", 2: "#ffffff", 3: "#ffffff", 4: "#ffffff", 5: "#000000", 6: "#ffffff"}

    for i in range(1, 7):
        curr_x_center = first_col_x + (i-1) * col_w + (col_w // 2)
        row = result_df[result_df["boat_num"] == i].iloc[0]
        
        # 縦の仕切り線（各艇の間）
        line_x = first_col_x + (i-1) * col_w
        draw.line([line_x, row_y_base, line_x, row_y_base + 630], fill=(0,0,0), width=2)
        
        # (1) 印 ◎○▲△
        # 期待％が高い順にランク付け
        rank = result_df["expected_pct"].rank(ascending=False, method='min').iloc[i-1]
        mark = "◎" if rank == 1 else "○" if rank == 2 else "▲" if rank == 3 else "△" if rank == 4 else "・"
        
        # 印の中央寄せ
        m_w = f_mark.getlength(mark)
        draw.text((curr_x_center - m_w//2, row_y_base + 40), mark, fill=(200, 0, 0), font=f_mark)
        
        # (2) 艇番（丸付き）
        b_rgb = tuple(int(boat_colors[i].lstrip('#')[j:j+2], 16) for j in (0, 2, 4))
        r = 65 # 半径
        draw.ellipse([curr_x_center - r, row_y_base + 260, curr_x_center + r, row_y_base + 390], fill=b_rgb, outline=(0,0,0), width=3)
        num_str = str(i)
        n_w = f_boat.getlength(num_str)
        draw.text((curr_x_center - n_w//2 - 2, row_y_base + 278), num_str, fill=text_colors[i], font=f_boat)
        
        # (3) 指数（期待％）
        idx_str = f"{row.expected_pct}%"
        idx_w = f_index.getlength(idx_str)
        draw.text((curr_x_center - idx_w//2, row_y_base + 515), idx_str, fill=(0, 0, 0), font=f_index)

    # --- フッター（買い目） ---
    draw.rectangle([60, 960, w-60, 1070], fill=(255, 255, 255), outline=(0,0,0), width=3)
    top_3 = result_df.sort_values("expected_pct", ascending=False)["boat_num"].tolist()[:3]
    recommend_text = f"推奨買い目: {top_3[0]} = {top_3[1]} - 全、 {top_3[0]} - {top_3[2]} - 流し (3連単)"
    draw.text((100, 990), recommend_text, fill=(0, 0, 0), font=f_footer)
    
    return img

# ==========================================
# ※ Streamlitのメイン処理（このcreate_perfect_newspaper関数を使うように修正）
# ==========================================
