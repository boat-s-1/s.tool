import streamlit as st
import pandas as pd
import io
import datetime
import os
import urllib.request
from PIL import Image, ImageDraw, ImageFont

# --- フォントを自動ダウンロードする関数 ---
@st.cache_resource
def get_japanese_font():
    # Noto Sans JP を Google Fonts から取得
    font_url = "https://github.com/googlefonts/noto-cjk/raw/main/Sans/OTF/Japanese/NotoSansCJKjp-Bold.otf"
    font_path = "NotoSansCJKjp-Bold.otf"
    if not os.path.exists(font_path):
        with st.spinner("日本語フォントを準備中..."):
            urllib.request.urlretrieve(font_url, font_path)
    return font_path

# --- デザイン用の設定 ---
boat_bg = {1: "#ffffff", 2: "#333333", 3: "#ff3b3b", 4: "#007bff", 5: "#ffc107", 6: "#28a745"}
boat_tx = {1: "#000000", 2: "#ffffff", 3: "#ffffff", 4: "#ffffff", 5: "#000000", 6: "#ffffff"}

def get_yoso_mark(val):
    marks = {6: "◎", 5: "○", 4: "▲", 3: "△", 2: "×", 1: "・", 0: "－"}
    return marks.get(val, "－")

def create_newspaper_image(place, race_num, result_df):
    w, h = 1000, 1000
    paper_color = (245, 242, 230) 
    img = Image.new('RGB', (w, h), paper_color)
    draw = ImageDraw.Draw(img)
    
    # フォントの読み込み（ここでダウンロードしたフォントを使用）
    font_p = get_japanese_font()
    f_title = ImageFont.truetype(font_p, 70)
    f_mark = ImageFont.truetype(font_p, 100)
    f_text = ImageFont.truetype(font_p, 35)
    f_label = ImageFont.truetype(font_p, 30)
    f_boat = ImageFont.truetype(font_p, 60)

    # 外枠
    draw.rectangle([20, 20, 980, 980], outline=(50, 50, 50), width=5)
    draw.line([20, 150, 980, 150], fill=(50, 50, 50), width=3)
    
    # ヘッダー
    draw.text((50, 50), f"競艇専門紙 PRO ANALYTICA", fill=(0, 0, 0), font=f_text)
    draw.text((700, 50), f"{datetime.date.today().strftime('%Y/%m/%d')}", fill=(0, 0, 0), font=f_text)
    draw.text((50, 170), f"{place}ボート 最終予想 第{race_num}R", fill=(180, 0, 0), font=f_title)
    
    col_w = 145
    start_x = 70
    header_y = 280
    
    # 項目ラベル
    draw.text((start_x, header_y + 120), "印", fill=(100, 100, 100), font=f_label)
    draw.text((start_x, header_y + 350), "艇", fill=(100, 100, 100), font=f_label)
    draw.text((start_x, header_y + 580), "期待", fill=(100, 100, 100), font=f_label)

    # 艇ごとの情報を描画
    for i in range(1, 7):
        curr_x = start_x + (i * col_w) - 20
        row = result_df[result_df["boat_num"] == i].iloc[0]
        
        # 縦の罫線
        draw.line([curr_x - 15, header_y, curr_x - 15, header_y + 650], fill=(150, 150, 150), width=1)
        
        # 印 ◎○▲△
        mark = get_yoso_mark(int(max(row.m, row.t, row.w, row.s)))
        draw.text((curr_x + 15, header_y + 80), mark, fill=(200, 0, 0), font=f_mark)
        
        # 艇番
        b_col = boat_bg[i]
        b_rgb = tuple(int(b_col.lstrip('#')[j:j+2], 16) for j in (0, 2, 4))
        draw.ellipse([curr_x + 10, header_y + 320, curr_x + 120, header_y + 430], fill=b_rgb, outline=(0,0,0), width=2)
        draw.text((curr_x + 48, header_y + 335), str(i), fill=boat_tx[i], font=f_boat)
        
        # 期待値%
        draw.text((curr_x + 5, header_y + 580), f"{row.expected_pct}%", fill=(0, 0, 0), font=f_text)

    # フッター (推奨買い目)
    draw.rectangle([50, 850, 950, 950], outline=(0,0,0), width=2)
    top_3 = result_df.sort_values("expected_pct", ascending=False)["boat_num"].tolist()[:3]
    draw.text((80, 880), f"推奨: {top_3[0]}－{top_3[1]}－{top_3[2]}、{top_3[0]}－{top_3[1]}－全", fill=(0, 0, 0), font=f_text)
    
    return img

# --- Streamlitでの表示部分 (tab_sns内) ---
# ※既存の tab_sns の if "analytica_result" in st.session_state: 以降を以下に差し替え
# img = create_newspaper_image(r_place, r_num, df)
# st.image(img, use_container_width=True)
