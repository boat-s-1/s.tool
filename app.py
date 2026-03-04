import streamlit as st
import pandas as pd
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import io
import datetime
import gspread
from google.oauth2.service_account import Credentials
import plotly.express as px

# ==========================================
# 1. 基本設定・認証 (変更なし)
# ==========================================
st.set_page_config(page_title="競艇Pro Analytica", layout="wide", page_icon="🎯")

st.markdown("""
    <style>
    .stMetric { background-color: #ffffff; padding: 15px; border-radius: 10px; border: 1px solid #eee; }
    .boat-box { padding: 10px; border-radius: 8px; text-align: center; font-weight: bold; margin-bottom: 5px; border: 1px solid #dee2e6; }
    .stTabs [data-baseweb="tab-list"] { gap: 24px; }
    .stTabs [data-baseweb="tab"] { height: 50px; white-space: pre-wrap; background-color: #f0f2f6; border-radius: 5px 5px 0 0; padding: 10px 20px; }
    .stTabs [aria-selected="true"] { background-color: #ff4b4b; color: white; }
    .stExpander { border: none !important; box-shadow: none !important; margin-bottom: 10px !important; }
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

get_symbol = lambda val: {6: "◎", 5: "○", 4: "▲", 3: "△", 2: "×", 1: "・", 0: "無"}.get(val, "無")

# 艇の色設定 (デザイン用に少し鮮やかに変更)
boat_bg = {1: "#ffffff", 2: "#111111", 3: "#ff3b3b", 4: "#007bff", 5: "#ffc107", 6: "#28a745"}
boat_tx = {1: "#000000", 2: "#ffffff", 3: "#ffffff", 4: "#ffffff", 5: "#000000", 6: "#ffffff"}

# ==========================================
# 3. サイドバー (変更なし)
# ==========================================
with st.sidebar:
    st.title("🎯 設定パネル")
    r_place = st.selectbox("📍 開催地を選択", ["桐生", "戸田", "江戸川", "平和島", "多摩川", "浜名湖", "蒲郡", "常滑", "津", "三国", "びわこ", "住之江", "尼崎", "鳴門", "丸亀", "児島", "宮島", "徳山", "下関", "若松", "芦屋", "福岡", "佐賀", "大村"])
    race_type_val = st.radio("📊 解析対象", ["混合", "女子"], horizontal=True)
    
    st.markdown("### 📊 統計データ連携")
    target_sheet = f"{r_place}_{race_type_val}統計"
    if st.button("🔄 スプレッドシートを取得", use_container_width=True, type="primary"):
        with st.spinner("通信中..."):
            try:
                sh = gc.open_by_key("1lN794iGtyGV2jNwlYzUA8wEbhRwhPM7FxDAkMaoJss4")
                ws = sh.worksheet(target_sheet)
                data = ws.get_all_records()
                st.session_state["base_df"] = pd.DataFrame(data)
                st.success(f"✅ {len(data)}件 取得完了")
            except:
                st.error(f"「{target_sheet}」が見つかりません。")

    st.divider()

    st.markdown("### ⚙️ 配点設定")
    w_m = st.slider("モーターの重み", 0, 100, 30, step=10)
    w_t = st.slider("当地勝率の重み", 0, 100, 20, step=10)
    w_w = st.slider("枠番勝率の重み", 0, 100, 30, step=10)
    w_s = st.slider("スタートの重み", 0, 100, 20, step=10)
    
    total_w = w_m + w_t + w_w + w_s
    if total_w != 100:
        st.error(f"合計が {total_w}% です。100%に調整してください。")

# ==========================================
# 4. メイン画面 (当日予想タブまでは変更なし)
# ==========================================
st.title(f"📊 {r_place} Pro Analytica")

tab_analytica, tab_sns = st.tabs(["🔍 統計解析 & 当日予想", "🖼️ SNS画像生成"])

with tab_analytica:
    col_l, col_r = st.columns([1, 1.5])

    with col_l:
        st.subheader("🤖 最適配点の算出（参考）")
        if "base_df" in st.session_state:
            if st.button("📈 過去の実績から重みを計算", use_container_width=True):
                df_base = st.session_state["base_df"]
                df_base.columns = [c.strip() for c in df_base.columns]
                target_cols = ["展示", "直線", "回り足", "一周", "ST"]
                avail = [c for c in target_cols + ["着順"] if c in df_base.columns]
                work_df = df_base[avail].copy()
                if "着順" in work_df.columns:
                    work_df["着順"] = work_df["着順"].astype(str).str.replace('S', '').replace('NULL', '')
                for col in work_df.columns:
                    work_df[col] = pd.to_numeric(work_df[col], errors='coerce')
                work_df = work_df.fillna(work_df.mean())
                clean_df = work_df[work_df["着順"] > 0]
                
                if len(clean_df) >= 2:
                    corrs = {}
                    for col in target_cols:
                        if col in clean_df.columns:
                            val = abs(clean_df[col].corr(clean_df["着順"]))
                            corrs[col] = val if pd.notna(val) and val != 0 else 0.01
                        else:
                            corrs[col] = 0.01
                    total = sum(corrs.values())
                    st.session_state["auto_weights"] = {k: v/total for k, v in corrs.items()}
                    st.success(f"✅ 解析完了")
            
            if "auto_weights" in st.session_state:
                aw = st.session_state["auto_weights"]
                fig = px.pie(names=list(aw.keys()), values=list(aw.values()), hole=0.4)
                st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("サイドバーからデータを読み込んでください")

    with col_r:
        st.subheader("📝 直前気配入力")
        with st.form("input_form"):
            results = []
            for row_idx in range(3):
                row_cols = st.columns(2)
                for col_idx in range(2):
                    boat_num = row_idx * 2 + col_idx + 1
                    with row_cols[col_idx]:
                        st.markdown(f'<div class="boat-box" style="background:{boat_bg[boat_num]}; color:{boat_tx[boat_num]};">{boat_num}号艇</div>', unsafe_allow_html=True)
                        with st.expander(f"詳細入力", expanded=False):
                            m = st.select_slider(f"モーター_{boat_num}", range(7), 3, get_symbol, key=f"m_{boat_num}")
                            t = st.select_slider(f"当地勝率_{boat_num}", range(7), 3, get_symbol, key=f"t_{boat_num}")
                            w = st.select_slider(f"枠番勝率_{boat_num}", range(7), 3, get_symbol, key=f"w_{boat_num}")
                            s = st.select_slider(f"枠スタート_{boat_num}", range(7), 3, get_symbol, key=f"s_{boat_num}")
                            score = (m * (w_m/100) + t * (w_t/100) + w * (w_w/100) + s * (w_s/100))
                            results.append({"boat_num": boat_num, "score": score, "m": m, "t": t, "w": w, "s": s})
            submitted = st.form_submit_button("🔥 解析確定", use_container_width=True, type="primary")

        if submitted:
            if total_w != 100:
                st.error("配点設定の合計を100%にしてください")
            else:
                df = pd.DataFrame(results)
                df["expected_pct"] = (df["score"] / df["score"].sum() * 100).round(1) if df["score"].sum() > 0 else 0
                st.session_state["analytica_result"] = df
                st.success("解析完了！")
                
                disp = df.copy()
                disp["艇番"] = disp["boat_num"].apply(lambda x: f"{x}号艇")
                for c, name in zip(["m", "t", "w", "s"], ["モーター", "当地勝率", "枠番勝率", "枠番スタート"]):
                    disp[name] = disp[c].apply(get_symbol)
                
                st.dataframe(disp[["艇番", "expected_pct", "モーター", "當地勝率", "枠番勝率", "枠番スタート"]], use_container_width=True, hide_index=True)

# ==========================================
# 5. SNS画像生成タブ (美デザイン版へパッチ適用)
# ==========================================
with tab_sns:
    st.subheader("🖼️ Premium 画像作成")
    st.caption("SNSで映える、プロ仕様のデザイン画像を生成します、")
    
    if "analytica_result" in st.session_state:
        df = st.session_state["analytica_result"]
        
        # --- 描画関数 ---
        def create_premium_image(place_name, sorted_df):
            # 1. キャンバス & 色設定
            img_w, img_h = 1080, 1350 # インスタ等で見やすい縦長
            bg_color = (10, 10, 15) # 漆黒
            accent_neon = (255, 60, 60) # ネオンレッド
            grid_color = (40, 40, 50) # 深い灰色
            
            img = Image.new('RGB', (img_w, img_h), bg_color)
            draw = ImageDraw.Draw(img)
            
            # 2. フォント読込
            try:
                # liberation fonts (linux / cloud)
                f_title = ImageFont.truetype("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf", 65)
                f_pct = ImageFont.truetype("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf", 75)
                f_num = ImageFont.truetype("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf", 100)
                f_sub = ImageFont.truetype("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf", 35)
            except:
                f_title = f_pct = f_num = ImageFont.load_default()
                f_sub = ImageFont.load_default()

            # 3. 背景アートワーク (グリッド & グラデーション)
            for y in range(0, img_h, 80): draw.line((0, y, img_w, y), fill=grid_color, width=1)
            for x in range(0, img_w, 80): draw.line((x, 0, x, img_h), fill=grid_color, width=1)
            
            # トップの赤いグラデーションぼかし
            grad_layer = Image.new('RGBA', (img_w, img_h), (0,0,0,0))
            draw_grad = ImageDraw.Draw(grad_layer)
            draw_grad.rectangle([0,0, img_w, 200], fill=(255, 60, 60, 40))
            grad_layer = grad_layer.filter(ImageFilter.GaussianBlur(50))
            img.paste(grad_layer, (0,0), grad_layer)

            # 4. ヘッダー
            today_str = datetime.date.today().strftime("%Y.%m.%d")
            draw.text((60, 70), f"PRO ANALYTICA", fill=accent_neon, font=f_title)
            draw.text((60, 150), f"🏟️ {place_name} | {today_str}", fill=(180, 180, 200), font=f_sub)
            
            # メインライン
            draw.line((60, 220, 1020, 220), fill=accent_neon, width=6)
            
            # 5. ランキング描画
            for i, row in enumerate(sorted_df.itertuples()):
                y = 280 + (i * 170)
                b_num = int(row.boat_num)
                b_pct = row.expected_pct
                b_color_str = boat_bg[b_num]
                # RGB変換
                b_rgb = tuple(int(b_color_str.lstrip('#')[j:j+2], 16) for j in (0, 2, 4))
                
                # --- (1) 艇番ボックス (立体的な光沢仕上げ) ---
                # ネオンゴースト (背後のぼかした光)
                neon_g = Image.new('RGBA', (200, 200), (0,0,0,0))
                draw_g = ImageDraw.Draw(neon_g)
                draw_g.rounded_rectangle([30, 30, 170, 170], radius=30, fill=(*b_rgb, 80))
                neon_g = neon_g.filter(ImageFilter.GaussianBlur(25))
                img.paste(neon_g, (30, y-30), neon_g)
                
                # 本体ボックス (金属的なグラデーション風)
                draw.rounded_rectangle([60, y, 180, y + 120], radius=20, fill=b_rgb)
                # 艇番
                draw.text((88, y + 15), str(b_num), fill=boat_tx[b_num], font=f_num)

                # --- (2) パーセント & バー ---
                bar_start_x = 220
                draw.text((bar_start_x, y), f"EXPECTED PROBABILITY", fill=(150, 150, 170), font=f_sub)
                
                # バーの背景
                draw.rounded_rectangle([bar_start_x, y+60, 950, y+100], radius=15, fill=(30, 30, 40))
                
                # バー (ネオンレッド〜オレンジのグラデーション)
                # ※ここではPILでグラデは難しいため、2色のバーを重ねることで表現
                bar_w = int(b_pct * 7.7) # 最大770px
                if bar_w > 10:
                    draw.rounded_rectangle([bar_start_x, y+60, bar_start_x + bar_w, y+100], radius=15, fill=accent_neon)
                    # 先端を少し明るく
                    draw.rounded_rectangle([bar_start_x + bar_w - 10, y+60, bar_start_x + bar_w, y+100], radius=15, fill=(255, 120, 120))
                
                # パーセント数字 (右寄せ)
                draw.text(( bar_start_x + 560, y-10), f"{b_pct}%", fill=(255, 255, 255), font=f_pct)

            # 6. フッター
            draw.text((60, 1270), "Generated by Pro Analytica ©AI Prediction System", fill=(80, 80, 100), font=f_sub)
            
            return img

        # --- アプリ上の表示 ---
        sorted_df = df.sort_values("expected_pct", ascending=False)
        
        # プレビュー表示
        img_preview = create_premium_image(r_place, sorted_df)
        st.image(img_preview, caption=f"✨ {r_place} Premium Yoso", use_container_width=True)
        
        # ダウンロード
        buf = io.BytesIO()
        img_preview.save(buf, format="PNG")
        st.download_button(
            label="📲 Premium画像を保存",
            data=buf.getvalue(),
            file_name=f"Premium_{r_place}_{datetime.datetime.now().strftime('%m%d_%H%M')}.png",
            mime="image/png",
            use_container_width=True
        )
        
    else:
        st.warning("先に「当日予想」タブで解析を確定させてください。")
