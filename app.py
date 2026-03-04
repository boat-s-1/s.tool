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

# ==========================================
# 2. 便利関数
# ==========================================
get_symbol = lambda val: {6: "◎", 5: "○", 4: "▲", 3: "△", 2: "×", 1: "・", 0: "無"}.get(val, "無")
boat_bg = {1: "#ffffff", 2: "#333333", 3: "#e03131", 4: "#1971c2", 5: "#fcc419", 6: "#2f9e44"}
boat_tx = {1: "#000000", 2: "#ffffff", 3: "#ffffff", 4: "#ffffff", 5: "#000000", 6: "#ffffff"}

# ==========================================
# 3. サイドバー
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
                st.error(f"「{target_sheet}」が見つかりませんでした。")

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
# 4. メイン画面
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
                            results.append({"艇番": boat_num, "score": score, "モーター": m, "当地勝率": t, "枠番勝率": w, "枠番スタート": s})
            submitted = st.form_submit_button("🔥 解析確定", use_container_width=True, type="primary")

        if submitted:
            if total_w != 100:
                st.error("配点設定の合計を100%にしてください")
            else:
                df = pd.DataFrame(results)
                df["予想％"] = (df["score"] / df["score"].sum() * 100).round(1) if df["score"].sum() > 0 else 0
                st.session_state["analytica_result"] = df
                st.success("解析完了！")
                disp = df.copy()
                for c in ["モーター", "当地勝率", "枠番勝率", "枠番スタート"]:
                    disp[c] = disp[c].apply(get_symbol)
                st.dataframe(disp[["艇番", "予想％", "モーター", "当地勝率", "枠番勝率", "枠番スタート"]], use_container_width=True, hide_index=True)

# ==========================================
# 5. SNS画像生成タブ (ここを実装しました)
# ==========================================
with tab_sns:
    st.subheader("🖼️ SNS用画像作成")
    
    if "analytica_result" in st.session_state:
        df = st.session_state["analytica_result"]
        
        # 1. 画像設定
        img_w, img_h = 1000, 1000
        base_color = (20, 20, 30) # 濃い紺色
        accent_color = (255, 75, 75) # 赤
        
        # 2. 画像キャンバス作成
        img = Image.new('RGB', (img_w, img_h), base_color)
        draw = ImageDraw.Draw(img)
        
        # ※フォント設定（環境によってパスが異なるため、デフォルトを使用）
        try:
            # Linux(Streamlit Cloud)環境用
            font_title = ImageFont.truetype("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf", 60)
            font_main = ImageFont.truetype("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf", 40)
        except:
            font_title = ImageFont.load_default()
            font_main = ImageFont.load_default()

        # タイトル描画
        draw.text((50, 50), f"PRO ANALYTICA: {r_place}", fill=(255, 255, 255), font=font_title)
        draw.line((50, 130, 950, 130), fill=accent_color, width=5)
        
        # 各艇のスコアを描画
        sorted_df = df.sort_values("予想％", ascending=False)
        for i, row in enumerate(sorted_df.itertuples()):
            y_pos = 180 + (i * 130)
            b_num = int(row.艇番)
            b_pct = row.予想％
            
            # 艇番ボックス
            draw.rectangle([50, y_pos, 150, y_pos + 100], fill=boat_bg[b_num], outline=(255,255,255))
            draw.text((85, y_pos + 20), str(b_num), fill=boat_tx[b_num], font=font_title)
            
            # パーセントバー
            bar_width = int(b_pct * 6) # 最大600px
            draw.rectangle([180, y_pos + 60, 180 + bar_width, y_pos + 90], fill=accent_color)
            draw.text((180, y_pos + 5), f"{b_pct}% EXPECTED", fill=(200, 200, 200), font=font_main)

        # 3. プレビューと保存
        st.image(img, caption="生成されたプレビュー", use_container_width=True)
        
        # ダウンロードボタン
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        st.download_button(
            label="📲 画像をダウンロード",
            data=buf.getvalue(),
            file_name=f"Analytica_{r_place}_{datetime.datetime.now().strftime('%m%d_%H%M')}.png",
            mime="image/png",
            use_container_width=True
        )
    else:
        st.warning("先に「当日予想」タブで解析を確定させてください。")
