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
    # Noto Sans JP を Google Fonts (GitHub) から取得
    font_url = "https://github.com/googlefonts/noto-cjk/raw/main/Sans/OTF/Japanese/NotoSansCJKjp-Bold.otf"
    font_path = "NotoSansCJKjp-Bold.otf"
    if not os.path.exists(font_path):
        with st.spinner("日本語フォントを準備中... (初回のみ10秒ほどかかります)"):
            try:
                urllib.request.urlretrieve(font_url, font_path)
            except Exception as e:
                st.error(f"フォントのダウンロードに失敗しました: {e}")
                return None
    return font_path

# ==========================================
# 2. 便利関数・デザイン設定
# ==========================================
def get_yoso_mark(val):
    marks = {6: "◎", 5: "○", 4: "▲", 3: "△", 2: "×", 1: "・", 0: "－"}
    return marks.get(val, "－")

boat_bg = {1: "#ffffff", 2: "#333333", 3: "#ff3b3b", 4: "#007bff", 5: "#ffc107", 6: "#28a745"}
boat_tx = {1: "#000000", 2: "#ffffff", 3: "#ffffff", 4: "#ffffff", 5: "#000000", 6: "#ffffff"}

@st.cache_resource
def get_gspread_client():
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scopes)
    return gspread.authorize(creds)

# ==========================================
# 3. サイドバー
# ==========================================
with st.sidebar:
    st.title("📝 専門紙設定")
    r_place = st.selectbox("📍 開催地", ["桐生", "戸田", "江戸川", "平和島", "多摩川", "浜名湖", "蒲郡", "常滑", "津", "三国", "びわこ", "住之江", "尼崎", "鳴門", "丸亀", "児島", "宮島", "徳山", "下関", "若松", "芦屋", "福岡", "佐賀", "大村"])
    r_num = st.number_input("🏁 レース番号", 1, 12, 1)
    race_type_val = st.radio("📊 解析対象", ["混合", "女子"], horizontal=True)
    
    st.divider()
    st.markdown("### ⚙️ 配点設定 (10単位)")
    w_m = st.slider("モーター", 0, 100, 30, step=10)
    w_t = st.slider("当地勝率", 0, 100, 20, step=10)
    w_w = st.slider("枠番勝率", 0, 100, 30, step=10)
    w_s = st.slider("スタート", 0, 100, 20, step=10)
    
    if (w_m + w_t + w_w + w_s) != 100:
        st.error("合計を100%に調整してください")

    if st.button("🔄 統計データ取得", use_container_width=True, type="primary"):
        with st.spinner("データ取得中..."):
            try:
                gc = get_gspread_client()
                sh = gc.open_by_key("1lN794iGtyGV2jNwlYzUA8wEbhRwhPM7FxDAkMaoJss4")
                ws = sh.worksheet(f"{r_place}_{race_type_val}統計")
                data = ws.get_all_records()
                st.session_state["base_df"] = pd.DataFrame(data)
                st.success("取得完了")
            except:
                st.error("データの読み込みに失敗しました")

# ==========================================
# 4. メイン画面
# ==========================================
st.title(f"📰 競艇専門紙 Analytica - {r_place}")

tab_analytica, tab_sns = st.tabs(["🔍 解析・予想入力", "📰 予想紙画像生成"])

with tab_analytica:
    col_l, col_r = st.columns([1, 1.5])
    with col_l:
        if "base_df" in st.session_state:
            st.subheader("🤖 統計分析結果")
            # 簡易表示用
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
                    st.markdown(f'<div style="background:{boat_bg[i]}; color:{boat_tx[i]}; padding:5px; border-radius:5px; text-align:center; font-weight:bold;">{i}号艇</div>', unsafe_allow_html=True)
                    m = st.select_slider(f"モーター評価_{i}", range(7), 3, get_yoso_mark)
                    t = st.select_slider(f"当地評価_{i}", range(7), 3, get_yoso_mark)
                    w = st.select_slider(f"枠番評価_{i}", range(7), 3, get_yoso_mark)
                    s = st.select_slider(f"ST評価_{i}", range(7), 3, get_yoso_mark)
                    score = (m * w_m/100 + t * w_t/100 + w * w_w/100 + s * w_s/100)
                    results.append({"boat_num": i, "score": score, "m": m, "t": t, "w": w, "s": s})
            submitted = st.form_submit_button("🔥 予想を確定して解析", use_container_width=True, type="primary")

        if submitted:
            df = pd.DataFrame(results)
            df["expected_pct"] = (df["score"] / df["score"].sum() * 100).round(1) if df["score"].sum() > 0 else 0
            st.session_state["analytica_result"] = df
            st.success("解析が完了しました！「予想紙画像生成」タブへ進んでください。")

# ==========================================
# 5. SNS画像生成タブ (完全日本語版・レイアウト修正)
# ==========================================
# ==========================================
# 5. SNS画像生成タブ (完全日本語版・レイアウト修正)
# ==========================================
with tab_sns:
    st.subheader("🖼️ 予想紙（新聞）風デザイン")
    st.caption("右端の切れや買い目の重なりを修正しました。")
    
    if "analytica_result" in st.session_state:
        df = st.session_state["analytica_result"]
        
        def create_newspaper_image(place, race_num, result_df):
            # 1. キャンバス設定 (横幅を1200に拡張して切れを防止)
            w, h = 1200, 1100 
            paper_color = (245, 242, 230) # 新聞紙色
            img = Image.new('RGB', (w, h), paper_color)
            draw = ImageDraw.Draw(img)
            
            font_p = get_japanese_font()
            if not font_p: return None

            f_title = ImageFont.truetype(font_p, 80)
            f_mark = ImageFont.truetype(font_p, 100)
            f_text = ImageFont.truetype(font_p, 40)
            f_label = ImageFont.truetype(font_p, 35)
            f_boat = ImageFont.truetype(font_p, 60)
            f_footer = ImageFont.truetype(font_p, 45) # 買い目用を少し大きく

            # デザインの描画
            draw.rectangle([30, 30, w-30, h-30], outline=(50, 50, 50), width=5)
            draw.line([30, 160, w-30, 160], fill=(50, 50, 50), width=3)
            
            draw.text((60, 55), f"競艇専門紙 PRO ANALYTICA", fill=(0, 0, 0), font=f_text)
            draw.text((w-300, 55), f"{datetime.date.today().strftime('%Y/%m/%d')}", fill=(0, 0, 0), font=f_text)
            draw.text((60, 185), f"{place}ボート 最終結論 第{race_num}R", fill=(180, 0, 0), font=f_title)
            
            # --- レイアウト定数の見直し ---
            col_w = 170 # 艇ごとの幅を広げる
            start_x = 100 # 開始位置を少し右に
            header_y = 300 # 全体を下にずらす
            
            # 項目ラベル
            draw.text((start_x, header_y + 110), "本紙", fill=(100, 100, 100), font=f_label)
            draw.text((start_x, header_y + 155), "予想", fill=(100, 100, 100), font=f_label)
            draw.text((start_x, header_y + 360), "艇番", fill=(100, 100, 100), font=f_label)
            draw.text((start_x, header_y + 600), "指数", fill=(100, 100, 100), font=f_label)

            # 艇ごとの情報を描画
            for i in range(1, 7):
                curr_x = start_x + (i * col_w) - 20
                row = result_df[result_df["boat_num"] == i].iloc[0]
                # 縦の罫線
                draw.line([curr_x - 15, header_y, curr_x - 15, header_y + 680], fill=(150, 150, 150), width=1)
                
                # 印の自動決定
                rank = result_df["expected_pct"].rank(ascending=False, method='min')
                r_val = rank[i-1]
                mark = "◎" if r_val == 1 else "○" if r_val == 2 else "▲" if r_val == 3 else "△" if r_val == 4 else "・"
                
                # ◎の位置調整
                mark_y_adj = 80 if r_val == 1 else 90
                draw.text((curr_x + 15, header_y + mark_y_adj), mark, fill=(200, 0, 0), font=f_mark)
                
                # 艇番ボックス
                b_rgb = tuple(int(boat_bg[i].lstrip('#')[j:j+2], 16) for j in (0, 2, 4))
                draw.ellipse([curr_x + 10, header_y + 330, curr_x + 130, header_y + 450], fill=b_rgb, outline=(0,0,0), width=2)
                draw.text((curr_x + 50, header_y + 348), str(i), fill=boat_tx[i], font=f_boat)
                
                # 指数（期待％）
                draw.text((curr_x + 5, header_y + 600), f"{row.expected_pct}%", fill=(0, 0, 0), font=f_text)

            # --- フッター (推奨買い目) の位置修正 ---
            draw.rectangle([60, 950, w-60, 1060], outline=(0,0,0), width=2) # 枠を下へ
            top_3 = result_df.sort_values("expected_pct", ascending=False)["boat_num"].tolist()[:3]
            
            # 推奨買い目のテキスト生成
            recommend_text = f"推奨買い目: {top_3[0]} = {top_3[1]} - 全、 {top_3[0]} - {top_3[2]} - 流し (3連単)"
            draw.text((90, 985), recommend_text, fill=(0, 0, 0), font=f_footer) # y位置を下へ
            
            return img

        if st.button("✨ 予想紙画像を生成する", use_container_width=True):
            with st.spinner("画像を再デザイン中..."):
                img = create_newspaper_image(r_place, r_num, df)
                if img:
                    st.image(img, use_container_width=True)
                    buf = io.BytesIO()
                    img.save(buf, format="PNG")
                    st.download_button("📲 修正版画像を保存する", buf.getvalue(), f"Keitei_Yoso_{r_place}_fixed.png", "image/png", use_container_width=True)
    else:
        st.warning("「解析・予想入力」タブで解析を確定させてください")

