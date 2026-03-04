import streamlit as st
import pandas as pd
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import io
import datetime
import gspread
from google.oauth2.service_account import Credentials
import plotly.express as px

# ==========================================
# 1. 基本設定・認証
# ==========================================
st.set_page_config(page_title="競艇専門紙 Pro Analytica", layout="wide", page_icon="📝")

# 日本語表示のためのCSS
st.markdown("""
    <style>
    .stApp { background-color: #f0f2f6; }
    .boat-box { padding: 10px; border-radius: 5px; text-align: center; font-weight: bold; margin-bottom: 5px; border: 1px solid #ccc; }
    .stTabs [data-baseweb="tab-list"] { gap: 24px; }
    .stTabs [data-baseweb="tab"] { height: 50px; background-color: #e0e0e0; border-radius: 5px 5px 0 0; }
    .stTabs [aria-selected="true"] { background-color: #333; color: white; }
    </style>
""", unsafe_allow_html=True)

@st.cache_resource
def get_gspread_client():
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scopes)
    return gspread.authorize(creds)

try:
    gc = get_gspread_client()
except Exception as e:
    st.error(f"⚠️ Google Sheets接続エラー: {e}")
    st.stop()

# 印の変換関数
def get_yoso_mark(val):
    marks = {6: "◎", 5: "○", 4: "▲", 3: "△", 2: "×", 1: "・", 0: "－"}
    return marks.get(val, "－")

boat_bg = {1: "#ffffff", 2: "#333333", 3: "#ff3b3b", 4: "#007bff", 5: "#ffc107", 6: "#28a745"}
boat_tx = {1: "#000000", 2: "#ffffff", 3: "#ffffff", 4: "#ffffff", 5: "#000000", 6: "#ffffff"}

# ==========================================
# 3. サイドバー
# ==========================================
with st.sidebar:
    st.title("📝 専門紙設定")
    r_place = st.selectbox("📍 開催地", ["桐生", "戸田", "江戸川", "平和島", "多摩川", "浜名湖", "蒲郡", "常滑", "津", "三国", "びわこ", "住之江", "尼崎", "鳴門", "丸亀", "児島", "宮島", "徳山", "下関", "若松", "芦屋", "福岡", "佐賀", "大村"])
    r_num = st.number_input("🏁 レース番号", 1, 12, 1)
    race_type_val = st.radio("📊 解析対象", ["混合", "女子"], horizontal=True)
    
    st.divider()
    st.markdown("### ⚙️ 配点設定")
    w_m = st.slider("モーター", 0, 100, 30, step=10)
    w_t = st.slider("当地勝率", 0, 100, 20, step=10)
    w_w = st.slider("枠番勝率", 0, 100, 30, step=10)
    w_s = st.slider("スタート", 0, 100, 20, step=10)
    
    if (w_m + w_t + w_w + w_s) != 100:
        st.error("合計を100%にしてください")

    if st.button("🔄 統計データ取得", use_container_width=True, type="primary"):
        with st.spinner("データ取得中..."):
            try:
                sh = gc.open_by_key("1lN794iGtyGV2jNwlYzUA8wEbhRwhPM7FxDAkMaoJss4")
                ws = sh.worksheet(f"{r_place}_{race_type_val}統計")
                data = ws.get_all_records()
                st.session_state["base_df"] = pd.DataFrame(data)
                st.success("読込成功")
            except:
                st.error("読込失敗")

# ==========================================
# 4. メイン画面
# ==========================================
st.title(f"📰 競艇専門紙 Pro Analytica - {r_place}")

tab_analytica, tab_sns = st.tabs(["🔍 解析・予想入力", "📰 予想紙画像生成"])

with tab_analytica:
    col_l, col_r = st.columns([1, 1.5])

    with col_l:
        if "base_df" in st.session_state:
            st.subheader("🤖 統計的な重み")
            # 統計ロジック（簡易版）
            st.session_state["auto_weights"] = {"展示": 0.3, "直線": 0.2, "回り足": 0.2, "一周": 0.2, "ST": 0.1}
            aw = st.session_state["auto_weights"]
            st.plotly_chart(px.pie(names=list(aw.keys()), values=list(aw.values()), hole=0.4), use_container_width=True)

    with col_r:
        st.subheader("📝 本日の気配入力")
        with st.form("input_form"):
            results = []
            grid = st.columns(2)
            for i in range(1, 7):
                with grid[(i-1)%2]:
                    st.markdown(f'<div class="boat-box" style="background:{boat_bg[i]}; color:{boat_tx[i]};">{i}号艇</div>', unsafe_allow_html=True)
                    with st.expander("気配評価", expanded=False):
                        m = st.select_slider(f"モーター_{i}", range(7), 3, get_yoso_mark)
                        t = st.select_slider(f"当地_{i}", range(7), 3, get_yoso_mark)
                        w = st.select_slider(f"枠番_{i}", range(7), 3, get_yoso_mark)
                        s = st.select_slider(f"ST_{i}", range(7), 3, get_yoso_mark)
                        score = (m * w_m/100 + t * w_t/100 + w * w_w/100 + s * w_s/100)
                        # 最も高い評価の印を決定
                        max_val = max(m, t, w, s)
                        main_mark = get_yoso_mark(max_val)
                        results.append({"boat_num": i, "score": score, "mark": main_mark, "m": m, "t": t, "w": w, "s": s})
            submitted = st.form_submit_button("🔥 予想を確定する", use_container_width=True, type="primary")

        if submitted:
            df = pd.DataFrame(results)
            df["pct"] = (df["score"] / df["score"].sum() * 100).round(1) if df["score"].sum() > 0 else 0
            st.session_state["analytica_result"] = df
            st.dataframe(df, hide_index=True)

# ==========================================
# 5. SNS画像生成タブ (予想紙デザイン版)
# ==========================================
with tab_sns:
    st.subheader("🖼️ 予想紙風画像の生成")
    
    if "analytica_result" in st.session_state:
        df = st.session_state["analytica_result"]
        
        def create_newspaper_image(place, race_num, result_df):
            # 1. キャンバス設定 (新聞紙のような薄いベージュ)
            w, h = 1000, 1000
            paper_color = (245, 242, 230) # 藁半紙風
            img = Image.new('RGB', (w, h), paper_color)
            draw = ImageDraw.Draw(img)
            
            # 2. 日本語フォント探索と設定
            # Linux環境(Streamlit Cloud)で一般的な日本語フォントパス
            font_paths = [
                "/usr/share/fonts/truetype/fonts-japanese-gothic.ttf",
                "/usr/share/fonts/fonts-japanese-gothic.ttf",
                "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
                "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf" # Fallback
            ]
            
            def load_font(size):
                for path in font_paths:
                    try: return ImageFont.truetype(path, size)
                    except: continue
                return ImageFont.load_default()

            f_title = load_font(80)
            f_mark = load_font(120)
            f_text = load_font(40)
            f_label = load_font(30)
            f_boat = load_font(60)

            # 3. 外枠とデザイン罫線
            draw.rectangle([20, 20, 980, 980], outline=(50, 50, 50), width=5)
            draw.line([20, 150, 980, 150], fill=(50, 50, 50), width=3) # タイトル下
            
            # 4. ヘッダー (新聞名風)
            draw.text((50, 45), f"競艇専門紙 PRO ANALYTICA", fill=(0, 0, 0), font=f_text)
            draw.text((650, 45), f"{datetime.date.today().strftime('%Y/%m/%d')}", fill=(0, 0, 0), font=f_text)
            draw.text((50, 170), f"{place}ボート 最終結論 第{race_num}R", fill=(200, 0, 0), font=f_title)
            
            # 5. メイングリッド (縦割り)
            col_w = 150
            start_x = 50
            header_y = 280
            
            # 項目ラベル
            draw.text((start_x, header_y + 150), "印", fill=(50, 50, 50), font=f_label)
            draw.text((start_x, header_y + 350), "艇", fill=(50, 50, 50), font=f_label)
            draw.text((start_x, header_y + 550), "期待", fill=(50, 50, 50), font=f_label)

            # 6. 艇ごとの情報を描画 (ランキング順ではなく艇番順が予想紙らしい)
            for i in range(1, 7):
                curr_x = start_x + (i * col_w) - 30
                row = result_df[result_df["boat_num"] == i].iloc[0]
                
                # 縦の罫線
                draw.line([curr_x - 10, header_y, curr_x - 10, header_y + 650], fill=(100, 100, 100), width=1)
                
                # (1) 印 ◎○▲△
                mark = get_yoso_mark(int(max(row.m, row.t, row.w, row.s)))
                draw.text((curr_x + 10, header_y + 110), mark, fill=(200, 0, 0), font=f_mark)
                
                # (2) 艇番 (色付き丸)
                b_col = boat_bg[i]
                b_rgb = tuple(int(b_col.lstrip('#')[j:j+2], 16) for j in (0, 2, 4))
                draw.ellipse([curr_x + 10, header_y + 330, curr_x + 110, header_y + 430], fill=b_rgb, outline=(0,0,0), width=2)
                draw.text((curr_x + 42, header_y + 340), str(i), fill=boat_tx[i], font=f_boat)
                
                # (3) 期待値%
                draw.text((curr_x + 5, header_y + 550), f"{row.pct}%", fill=(0, 0, 0), font=f_text)

            # 7. フッター (注釈)
            draw.rectangle([50, 850, 950, 950], outline=(0,0,0), width=2)
            top_3 = result_df.sort_values("pct", ascending=False)["boat_num"].tolist()[:3]
            draw.text((80, 875), f"推奨買い目:  {top_3[0]} － {top_3[1]} － {top_3[2]} (3連単)", fill=(0, 0, 0), font=f_text)
            
            return img

        # 表示
        if st.button("✨ 予想紙を印刷（画像生成）", use_container_width=True):
            img = create_newspaper_image(r_place, r_num, df)
            st.image(img, use_container_width=True)
            
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            st.download_button("📲 画像を保存", buf.getvalue(), f"yoso_{r_place}.png", "image/png", use_container_width=True)

    else:
        st.warning("先に解析を確定させてください")
