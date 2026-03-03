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

# Google Sheets 認証
scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
try:
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scopes)
    gc = gspread.authorize(creds)
except Exception as e:
    st.error(f"⚠️ Google Sheets接続エラー: {e}")
    st.stop()

# 会場別特性補正値（直感解析タブ用）
PLACE_CORRECTIONS = {
    "江戸川": {"展示": 0.1, "直線": 0.2, "回り足": 0.5, "一周": 0.2},
    "戸田":   {"展示": 0.1, "直線": 0.5, "回り足": 0.2, "一周": 0.2},
    "DEFAULT": {"展示": 0.25, "直線": 0.25, "回り足": 0.25, "一周": 0.25}
}

# ==========================================
# 2. 共通関数
# ==========================================
get_symbol = lambda val: {6: "◎", 5: "○", 4: "▲", 3: "△", 2: "×", 1: "・", 0: "無"}.get(val, "無")
boat_bg = {1: "#ffffff", 2: "#333333", 3: "#e03131", 4: "#1971c2", 5: "#fcc419", 6: "#2f9e44"}
boat_tx = {1: "#000000", 2: "#ffffff", 3: "#ffffff", 4: "#ffffff", 5: "#000000", 6: "#ffffff"}
boat_colors_rgb = {1: (230,126,34), 2: (52,152,219), 3: (231,76,60), 4: (241,196,15), 5: (46,204,113), 6: (149,165,166)}

def style_by_rank(col):
    if col.name == "艇番": return [''] * 6
    ranks = col.rank(ascending=False, method='min')
    return ['background-color: #ff4b4b; color: white;' if r==1 else 'background-color: #ffff00; color: black;' if r==2 else '' for r in ranks]

def create_modern_sns_image(race_info, df_sorted):
    width, height = 1280, 720
    img = Image.new('RGB', (width, height), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    font_path = "NotoSansJP-Bold.ttf" 
    try:
        f_title = ImageFont.truetype(font_path, 60); f_header = ImageFont.truetype(font_path, 36)
        f_pct = ImageFont.truetype(font_path, 80); f_boat = ImageFont.truetype(font_path, 120)
    except:
        f_title = f_header = f_pct = f_boat = ImageFont.load_default()
    for y in range(120):
        color = (20 + y//4, 40 + y//3, 80 + y//2)
        draw.line([(0, y), (width, y)], fill=color)
    draw.text((40, 30), f"🎯 {race_info['place']} {race_info['num']}R 予想", font=f_title, fill=(255, 255, 255))
    df_top3 = df_sorted.sort_values("予想％", ascending=False).head(3)
    for i in range(3):
        row = df_top3.iloc[i]; b_no = int(row['艇番']); curr_x = 60 + (410 * i)
        draw.rounded_rectangle([curr_x, 160, curr_x + 380, 640], radius=20, fill=(250, 250, 250), outline=(200,200,200), width=2)
        draw.text((curr_x + 20, 180), f"{i+1}番手", font=f_header, fill=(50, 50, 50))
        draw.text((curr_x + 100, 260), str(b_no), font=f_boat, fill=boat_colors_rgb.get(b_no, (0,0,0)))
        draw.text((curr_x + 110, 450), f"{row['予想％']:.1f}%", font=f_pct, fill=(211, 47, 47))
    return img

# ==========================================
# 3. サイドバー（インデント修正版）
# ==========================================
with st.sidebar:
    st.header("📋 データ設定")
    r_date = st.date_input("レース日", datetime.date.today())
    r_place = st.selectbox("開催地を選択", ["桐生", "戸田", "江戸川", "平和島", "多摩川", "浜名湖", "蒲郡", "常滑", "津", "三国", "びわこ", "住之江", "尼崎", "鳴門", "丸亀", "児島", "宮島", "徳山", "下関", "若松", "芦屋", "福岡", "佐賀", "大村"])
    r_num = st.number_input("レース番号", 1, 12, 12)
    race_type_val = st.radio("解析データ対象", ["混合", "女子"], horizontal=True)
    
    # 🔗 スプレッドシートID設定
    SS_ID_1 = "1lN794iGtyGV2jNwlYzUA8wEbhRwhPM7FxDAkMaoJss4"
    SS_ID_2 = "1rSzJuk5Hyv60nMwX67pCufXz45HLykyIXuqVE6wtNII"
    
   if st.button("🔄 2つのファイルを読み込み", use_container_width=True, type="primary"):
        with st.spinner("ファイルを読み込み中..."):
            try:
                # プログラムが探している標準的な名前
                target_name = f"{r_place}_{race_type_val}統計"
                
                # --- ファイル1の処理 ---
                sh1 = gc.open_by_key(SS_ID_1)
                # 全タブのリストを取得
                ws1_list = sh1.worksheets()
                ws1_titles = [ws.title for ws in ws1_list]
                
                # 柔軟にシートを探す (完全一致 or 前後空白無視 or 部分一致)
                selected_ws1 = None
                for ws in ws1_list:
                    t = ws.title.strip().replace("＿", "_") # 全角アンダーバーも許容
                    if t == target_name or target_name in t:
                        selected_ws1 = ws
                        break
                
                if selected_ws1:
                    df1 = pd.DataFrame(selected_ws1.get_all_records())
                    st.info(f"📍 ファイル1: 「{selected_ws1.title}」を読み込みました")
                else:
                    # 見つからない場合は存在するシート名をヒントとして出す
                    st.error(f"ファイル1に「{target_name}」が見つかりません。")
                    st.write("📂 ファイル1にあるシート名一覧:")
                    st.write(ws1_titles)
                    st.stop()

                # --- ファイル2の処理 ---
                df_combined = df1
                try:
                    sh2 = gc.open_by_key(SS_ID_2)
                    ws2_list = sh2.worksheets()
                    for ws in ws2_list:
                        t = ws.title.strip().replace("＿", "_")
                        if t == target_name or target_name in t:
                            df2 = pd.DataFrame(ws.get_all_records())
                            df_combined = pd.concat([df1, df2], ignore_index=True)
                            st.info(f"📁 ファイル2: 「{ws.title}」から {len(df2)} 件追加しました")
                            break
                except:
                    pass

                st.session_state["base_df"] = df_combined
                st.success(f"✅ 合計 {len(df_combined)} 件 読込完了")
            except Exception as e:
                st.error(f"読み込み失敗: {e}")

# ==========================================
# 4. メインエリア
# ==========================================
st.title(f"📊 {r_place} Pro Analytica")
tab1, tab2, tab3 = st.tabs(["🔍 統計解析予想", "🎯 直感気配解析", "🖼️ SNS画像生成"])

# --- タブ1: 統計解析予想 ---
with tab1:
    col_left, col_right = st.columns([2, 3])
    with col_left:
        st.subheader("🤖 統計データ重み算出")
        if "base_df" in st.session_state:
            if st.button("📈 最適重みを抽出", use_container_width=True):
                df = st.session_state["base_df"].copy()
                df.columns = [c.strip() for c in df.columns]
                target = ["展示", "直線", "回り足", "一周", "ST"]
                if all(c in df.columns for c in target + ["着順"]):
                    for c in target + ["着順"]:
                        df[c] = pd.to_numeric(df[c].astype(str).str.replace('S','').replace('NULL',''), errors='coerce')
                    df = df.fillna(df.mean())
                    clean = df[df["着順"] > 0]
                    if len(clean) >= 2:
                        corrs = {c: abs(clean[c].corr(clean["着順"])) or 0.01 for c in target}
                        total = sum(corrs.values())
                        st.session_state["auto_weights"] = {k: v/total for k, v in corrs.items()}
                else:
                    st.error("必要な列（展示、直線など）が見つかりません。")

            if "auto_weights" in st.session_state:
                aw = st.session_state["auto_weights"]
                st.plotly_chart(px.pie(names=list(aw.keys()), values=list(aw.values()), hole=0.4, title="統計重要度"), use_container_width=True)

    with col_right:
        with st.form("form1"):
            raw = []
            c_i = st.columns(2)
            for i in range(1, 7):
                with c_i[(i-1)%2]:
                    st.markdown(f'<div style="background:{boat_bg[i]}; color:{boat_tx[i]}; padding:2px; border-radius:4px; text-align:center;">{i}号艇</div>', unsafe_allow_html=True)
                    m = st.select_slider(f"モーター", range(7), 0, get_symbol, key=f"t1_m_{i}")
                    t = st.select_slider(f"当地勝率", range(7), 0, get_symbol, key=f"t1_t_{i}")
                    w = st.select_slider(f"枠番勝率", range(7), 0, get_symbol, key=f"t1_w_{i}")
                    s = st.select_slider(f"枠番ST", range(7), 0, get_symbol, key=f"t1_s_{i}")
                    raw.append({"艇番": i, "score": (m*0.25+t*0.2+w*0.3+s*0.25), "モーター":m, "当地勝率":t, "枠番勝率":w, "枠番スタート":s})
            if st.form_submit_button("🔥 統計解析で確定"):
                df_res = pd.DataFrame(raw)
                total_s = df_res["score"].sum()
                if total_s > 0:
                    df_res["予想％"] = (df_res["score"]/total_s*100).round(1)
                    st.session_state["res"] = df_res; st.dataframe(df_res.style.apply(style_by_rank, axis=0))

# --- タブ2: 直感気配解析 ---
with tab2:
    col_l, col_r = st.columns([2, 3])
    with col_l:
        st.subheader(f"⚖️ {r_place} 特性補正")
        corr = PLACE_CORRECTIONS.get(r_place, PLACE_CORRECTIONS["DEFAULT"])
        st.plotly_chart(px.bar(x=list(corr.keys()), y=list(corr.values()), title="会場別補正ウェイト"), use_container_width=True)

    with col_r:
        with st.form("form2"):
            raw_feel = []
            c_f = st.columns(2)
            for i in range(1, 7):
                with c_f[(i-1)%2]:
                    st.markdown(f'<div style="background:{boat_bg[i]}; color:{boat_tx[i]}; padding:2px; border-radius:4px; text-align:center;">{i}号艇</div>', unsafe_allow_html=True)
                    f1 = st.select_slider(f"展示気配", range(7), 0, get_symbol, key=f"f1_{i}")
                    f2 = st.select_slider(f"直線(伸び)", range(7), 0, get_symbol, key=f"f2_{i}")
                    f3 = st.select_slider(f"回り足", range(7), 0, get_symbol, key=f"f3_{i}")
                    f4 = st.select_slider(f"一周タイム", range(7), 0, get_symbol, key=f"f4_{i}")
                    f_score = (f1 * corr["展示"] + f2 * corr["直線"] + f3 * corr["回り足"] + f4 * corr["一周"])
                    raw_feel.append({"艇番": i, "score": f_score, "展示": f1, "直線": f2, "回り足": f3, "一周": f4})
            if st.form_submit_button("🚀 直感気配で確定"):
                df_f = pd.DataFrame(raw_feel)
                total_f = df_f["score"].sum()
                if total_f > 0:
                    df_f["予想％"] = (df_f["score"]/total_f*100).round(1)
                    st.session_state["res"] = df_f; st.dataframe(df_f.sort_values("艇番").style.apply(style_by_rank, axis=0))

# --- タブ3: SNS画像生成 ---
with tab3:
    if "res" in st.session_state:
        if st.button("✨ モダンデザイン画像を生成"):
            img = create_modern_sns_image({"place": r_place, "num": r_num}, st.session_state["res"])
            st.image(img)
            buf = io.BytesIO(); img.save(buf, format="PNG")
            st.download_button("💾 画像を保存", buf.getvalue(), f"yoso_{r_place}_{r_num}R.png", "image/png")




