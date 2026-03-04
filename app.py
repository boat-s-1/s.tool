import streamlit as st
import pandas as pd
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import io
import datetime
import gspread
from google.oauth2.service_account import Credentials
import pathlib
import plotly.express as px

# ==========================================
# 1. 基本設定・認証
# ==========================================
# ページ設定（タイトルは後ほど会場名を入れる）
st.set_page_config(page_title="競艇Pro Analytica", layout="wide", page_icon="🎯")

# Google Sheets 認証
scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
try:
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scopes)
    gc = gspread.authorize(creds)
except Exception as e:
    st.error(f"⚠️ Google Sheets接続エラー: {e}")
    st.stop()

# ==========================================
# 2. SNS画像生成関数
# ==========================================
def create_modern_sns_image(race_info, df_sorted):
    width, height = 1280, 720
    img = Image.new('RGB', (width, height), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    font_path = "NotoSansJP-Bold.ttf" 
    try:
        f_title = ImageFont.truetype(font_path, 60)
        f_header = ImageFont.truetype(font_path, 36)
        f_pct = ImageFont.truetype(font_path, 80)
        f_boat = ImageFont.truetype(font_path, 120)
    except:
        f_title = f_header = f_pct = f_boat = ImageFont.load_default()

    for y in range(120):
        color = (20 + y//4, 40 + y//3, 80 + y//2)
        draw.line([(0, y), (width, y)], fill=color)
    
    # 会場名を動的に表示
    draw.text((40, 30), f"🎯 {race_info['place']} {race_info['num']}R 予想", font=f_title, fill=(255, 255, 255))
    
    boat_colors = {1: (230,126,34), 2: (52,152,219), 3: (231,76,60), 4: (241,196,15), 5: (46,204,113), 6: (149,165,166)}
    df_top3 = df_sorted.sort_values("予想％", ascending=False).head(3)
    for i in range(3):
        row = df_top3.iloc[i]
        b_no = int(row['艇番'])
        curr_x = 60 + (410 * i)
        draw.rounded_rectangle([curr_x, 160, curr_x + 380, 640], radius=20, fill=(250, 250, 250), outline=(200,200,200), width=2)
        draw.text((curr_x + 20, 180), f"{i+1}番手", font=f_header, fill=(50, 50, 50))
        draw.text((curr_x + 100, 260), f"{b_no}", font=f_boat, fill=boat_colors.get(b_no, (0,0,0)))
        draw.text((curr_x + 110, 450), f"{row['予想％']:.1f}%", font=f_pct, fill=(211, 47, 47))
    return img

# ==========================================
# 3. サイドバー（会場選択）
# ==========================================
with st.sidebar:
    st.header("📋 データ設定")
    r_date = st.date_input("レース日", datetime.date.today())
    
    # ★ 会場選択（ここで選んだ名前が全体に反映されます）
    r_place = st.selectbox("開催地を選択", 
        ["桐生", "戸田", "江戸川", "平和島", "多摩川", "浜名湖", "蒲郡", "常滑", "津", 
         "三国", "びわこ", "住之江", "尼崎", "鳴門", "丸亀", "児島", "宮島", "徳山", 
         "下関", "若松", "芦屋", "福岡", "佐賀", "大村"], index=0)
    
    r_num = st.number_input("レース番号", 1, 12, 12)
    race_type_val = st.radio("解析データ対象", ["混合", "女子"], horizontal=True)
    
    # スプレッドシートのシート名も動的に作成
    target_sheet = f"{r_place}_{race_type_val}統計"
    
    if st.button("🔄 スプレッドシート読み込み", use_container_width=True, type="primary"):
        with st.spinner(f"{target_sheet} を取得中..."):
            try:
                sh = gc.open_by_key("1lN794iGtyGV2jNwlYzUA8wEbhRwhPM7FxDAkMaoJss4")
                ws = sh.worksheet(target_sheet)
                data = ws.get_all_records()
                st.session_state["base_df"] = pd.DataFrame(data)
                # 会場が変わったら前回の解析結果をリセット
                if "auto_weights" in st.session_state:
                    del st.session_state["auto_weights"]
                st.success(f"✅ {r_place} {len(data)}件 読込完了")
            except Exception as e:
                st.error(f"シート「{target_sheet}」が見つからないか、エラーが発生しました: {e}")

# ==========================================
# 4. メインエリア
# ==========================================
# タイトルも動的に変更
st.title(f"📊 {r_place} Pro Analytica")

tab_analytica, tab_sns = st.tabs(["🔍 統計解析 & 当日予想", "🖼️ SNS画像生成"])

with tab_analytica:
    col_left, col_right = st.columns([2, 3])

    with col_left:
        st.subheader(f"🤖 {r_place}専用 重み算出")
        if "base_df" in st.session_state:
            df_base = st.session_state["base_df"]
            df_base.columns = [c.strip() for c in df_base.columns]
            
            if st.button("📈 過去データから最適重みを抽出", use_container_width=True):
                with st.spinner("統計解析中..."):
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
                        st.success(f"✅ {r_place}の解析が完了しました")
                    else:
                        st.session_state["auto_weights"] = {k: 0.2 for k in target_cols}
                        st.warning("⚠️ データ不足のため均等配分しました")

            if "auto_weights" in st.session_state:
                aw = st.session_state["auto_weights"]
                fig = px.pie(names=list(aw.keys()), values=list(aw.values()), hole=0.4, title=f"📊 {r_place}の重要度比率")
                fig.update_traces(textposition='inside', textinfo='percent+label')
                st.plotly_chart(fig, use_container_width=True)
                st.json(aw)
        else:
            st.info("サイドバーからデータを読み込んでください")

    with col_right:
        st.subheader("📝 当日予想入力")
        get_symbol = lambda val: {6: "◎", 5: "○", 4: "▲", 3: "△", 2: "×", 1: "・", 0: "無"}.get(val, "無")
        boat_bg = {1: "#ffffff", 2: "#333333", 3: "#e03131", 4: "#1971c2", 5: "#fcc419", 6: "#2f9e44"}
        boat_tx = {1: "#000000", 2: "#ffffff", 3: "#ffffff", 4: "#ffffff", 5: "#000000", 6: "#ffffff"}

        with st.form("input_form"):
            raw_data = []
            cols_i = st.columns(2)
            for i in range(1, 7):
                with cols_i[(i-1)%2]:
                    st.markdown(f'<div style="background:{boat_bg[i]}; color:{boat_tx[i]}; padding:2px 10px; border-radius:4px; font-weight:bold; border:1px solid #ddd; margin-bottom:5px;">{i}号艇</div>', unsafe_allow_html=True)
                    m = st.select_slider(f"🚀 モーター", options=range(7), value=0, format_func=get_symbol, key=f"m_{i}")
                    t = st.select_slider(f"🏟️ 当地勝率", options=range(7), value=0, format_func=get_symbol, key=f"t_{i}")
                    w = st.select_slider(f"📈 枠番勝率", options=range(7), value=0, format_func=get_symbol, key=f"w_{i}")
                    s = st.select_slider(f"⏱️ 枠番スタート", options=range(7), value=0, format_func=get_symbol, key=f"s_{i}")
                    score = (m*0.25 + t*0.2 + w*0.3 + s*0.25)
                    raw_data.append({"艇番": i, "モーター": m, "当地勝率": t, "枠番勝率": w, "枠番スタート": s, "score": score})
            submitted = st.form_submit_button(f"🔥 {r_place} 解析 ＆ 予想確定", use_container_width=True, type="primary")

        if submitted:
            df = pd.DataFrame(raw_data)
            if df["score"].sum() > 0:
                df["予想％"] = (df["score"] / df["score"].sum() * 100).round(1)
                df_fixed = df.sort_values("艇番").reset_index(drop=True)
                st.session_state["analytica_result"] = df_fixed

                def style_by_rank(col):
                    if col.name == "艇番": return [''] * 6
                    ranks = col.rank(ascending=False, method='min')
                    return ['background-color: #ff4b4b; color: white;' if r==1 else 'background-color: #ffff00; color: black;' if r==2 else '' for r in ranks]
                
                disp = df_fixed.copy()
                for c in ["モーター", "当地勝率", "枠番勝率", "枠番スタート"]: disp[c] = disp[c].apply(get_symbol)
                disp["艇番"] = disp["艇番"].apply(lambda x: f"{int(x)}号艇")
                st.dataframe(disp[["艇番", "予想％", "モーター", "当地勝率", "枠番勝率", "枠番スタート"]].style.apply(style_by_rank, axis=0), use_container_width=True, hide_index=True)

with tab_sns:
    if "analytica_result" in st.session_state:
        if st.button("✨ モダンデザイン画像を生成", use_container_width=True):
            img = create_modern_sns_image({"place": r_place, "num": r_num, "date": str(r_date)}, st.session_state["analytica_result"])
            st.image(img, use_container_width=True)
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            st.download_button("💾 画像を保存", buf.getvalue(), f"yoso_{r_place}_{r_num}R.png", "image/png", use_container_width=True)
