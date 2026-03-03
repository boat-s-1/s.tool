import streamlit as st
import pandas as pd
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import io
import datetime
import os
import gspread
from google.oauth2.service_account import Credentials
import base64
import pathlib

# ==========================================
# 1. 基本設定・認証
# ==========================================
BASE_DIR = pathlib.Path(__file__).parent.resolve()
PLACE_NAME = "桐生" # 固定会場名
st.set_page_config(page_title=f"競艇Pro {PLACE_NAME}", layout="wide")

# Google Sheets 認証
scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
try:
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scopes)
    gc = gspread.authorize(creds)
except Exception as e:
    st.error(f"Google接続設定エラー: {e}")
    st.stop()

# ==========================================
# 2. 画像生成用ヘルパー関数 (SNS用)
# ==========================================
def create_sns_image(race_info, df_rank, df_sorted):
    width, height = 1200, 675
    img = Image.new('RGB', (width, height), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    
    # フォント読み込み (NotoSansJP-Regular.ttf がカレントディレクトリにある前提)
    font_path = "NotoSansJP-Regular.ttf" 
    try:
        f_title = ImageFont.truetype(font_path, 45)
        f_header = ImageFont.truetype(font_path, 28)
        f_body = ImageFont.truetype(font_path, 22)
        f_rank_big = ImageFont.truetype(font_path, 32)
    except:
        f_title = f_header = f_body = f_rank_big = ImageFont.load_default()

    # デザイン描画
    draw.rectangle([0, 0, width, 100], fill=(20, 40, 80))
    title_text = f"【事前簡易予想】 {race_info['place']} {race_info['num']}R"
    draw.text((40, 25), title_text, font=f_title, fill=(255, 255, 255))
    draw.text((width - 300, 35), race_info['date'], font=f_header, fill=(255, 255, 255))

    # 表描画
    y_start, x_start, col_w, row_h = 140, 50, 220, 55
    headers = ["艇番", "モーター", "当地勝率", "枠番勝率", "枠番ST"]
    for i, h in enumerate(headers):
        draw.rectangle([x_start + i*col_w, y_start, x_start + (i+1)*col_w, y_start + row_h], outline=(0,0,0), width=2)
        draw.text((x_start + i*col_w + 15, y_start + 12), h, font=f_header, fill=(0, 0, 0))

    items = ["🚀 モーター", "🏟️ 当地勝率", "📈 枠番勝率", "⏱️ 枠番スタート"]
    for i in range(6):
        boat_label = f"{i+1}号艇"
        curr_y = y_start + (i+1)*row_h
        draw.rectangle([x_start, curr_y, x_start + col_w, curr_y + row_h], outline=(0,0,0))
        draw.text((x_start + 15, curr_y + 12), boat_label, font=f_body, fill=(0,0,0))
        for j, col_name in enumerate(items):
            val_text = df_rank.loc[boat_label, col_name]
            cell_x = x_start + (j+1)*col_w
            bg = (255, 204, 204) if "1位" in val_text else (255, 255, 204) if "2位" in val_text else None
            if bg: draw.rectangle([cell_x + 2, curr_y + 2, cell_x + col_w - 2, curr_y + row_h - 2], fill=bg)
            draw.rectangle([cell_x, curr_y, cell_x + col_w, curr_y + row_h], outline=(0,0,0))
            draw.text((cell_x + 15, curr_y + 12), val_text, font=f_body, fill=(0,0,0))

    # 総合評価表示
    st_y = 560
    draw.text((x_start, st_y), "【総合評価ランキング】", font=f_header, fill=(20, 40, 80))
    for i in range(min(3, len(df_sorted))):
        row = df_sorted.iloc[i]
        medal = ["🥇", "🥈", "🥉"][i]
        res_txt = f"{medal} {int(row['艇番'])}号艇 ({row['予想％']}%)"
        draw.text((x_start + i*380, st_y + 50), res_txt, font=f_rank_big, fill=(211,47,47) if i==0 else (0,0,0))

    return img

# ==========================================
# 3. メインUIエリア
# ==========================================
st.title(f"🚀 {PLACE_NAME} 解析システム & SNS Generator")

# データ読込エリア
with st.container(border=True):
    c1, c2, c3 = st.columns([1.5, 2, 2])
    with c1:
        race_type_val = st.radio("解析対象を選択", ["混合", "女子"], horizontal=True)
    with c2:
        target_sheet = f"{PLACE_NAME}_{race_type_val}統計"
        if st.button(f"🔄 {target_sheet} を読み込む", use_container_width=True):
            with st.spinner("データ取得中..."):
                try:
                    sh = gc.open_by_key("1lN794iGtyGV2jNwlYzUA8wEbhRwhPM7FxDAkMaoJss4")
                    ws = sh.worksheet(target_sheet)
                    data = ws.get_all_records()
                    if data:
                        df = pd.DataFrame(data)
                        num_cols = ["展示", "直線", "一周", "回り足", "艇番", "ST", "着順"]
                        for c in num_cols:
                            if c in df.columns: df[c] = pd.to_numeric(df[c], errors="coerce")
                        st.session_state["tab2_base_df"] = df
                        st.toast(f"✅ {target_sheet} を適用しました")
                    else: st.error("シートにデータがありません")
                except Exception as e: st.error(f"読込失敗: {e}")
    with c3:
        if "tab2_base_df" in st.session_state:
            st.success(f"適用中: {target_sheet} ({len(st.session_state['tab2_base_df'])}件)")
        else: st.warning("⚠️ データ未読込です")

st.divider()
tab_pre, tab_stat, tab_start, tab_rank = st.tabs(["🎯 事前予想 & SNS画像", "📊 統計解析 & 重み算出", "🚀 スリット予想", "🏆 項目別順位"])

# --- タブ1：事前簡易予想 ＆ SNS画像 ---
with tab_pre:
    st.subheader("🎯 事前簡易予想 ＆ SNS用画像生成")
    SYMBOL_VALUES = {"◎": 100, "○": 80, "▲": 60, "△": 40, "×": 20, "無": 0}
    WEIGHTS = {"モーター": 0.25, "当地勝率": 0.2, "枠番勝率": 0.3, "枠番スタート": 0.25}

    with st.form("pre_sns_form"):
        raw_input_data = []
        cols = st.columns(2)
        for i in range(1, 7):
            with cols[(i-1)%2]:
                st.markdown(f"**🚤 {i}号艇**")
                m = st.selectbox("モーター", ["◎", "○", "▲", "△", "×", "無"], index=5, key=f"p_m_{i}")
                t = st.selectbox("当地勝率", ["◎", "○", "▲", "△", "×", "無"], index=5, key=f"p_t_{i}")
                w = st.selectbox("枠番勝率", ["◎", "○", "▲", "△", "×", "無"], index=5, key=f"p_w_{i}")
                s = st.selectbox("枠番ST", ["◎", "○", "▲", "△", "×", "無"], index=5, key=f"p_s_{i}")
                score = (SYMBOL_VALUES[m]*0.25 + SYMBOL_VALUES[t]*0.2 + SYMBOL_VALUES[w]*0.3 + SYMBOL_VALUES[s]*0.25)
                raw_input_data.append({"艇番": i, "モーター": m, "当地勝率": t, "枠番勝率": w, "枠番スタート": s, "score": score})
        submitted = st.form_submit_button("📊 解析 ＆ SNS画像生成", use_container_width=True, type="primary")

    if submitted:
        df_pre = pd.DataFrame(raw_input_data)
        total_s = df_pre["score"].sum()
        if total_s == 0: st.warning("評価を入力してください")
        else:
            df_pre["予想％"] = (df_pre["score"] / total_s * 100).round(1)
            df_sorted = df_pre.sort_values("予想％", ascending=False).reset_index(drop=True)
            
            # 画像用データの成形
            rank_dict = {"艇番": [f"{i}号艇" for i in range(1, 7)]}
            for label, col in [("🚀 モーター", "モーター"), ("🏟️ 当地勝率", "当地勝率"), ("📈 枠番勝率", "枠番勝率"), ("⏱️ 枠番スタート", "枠番スタート")]:
                # 各艇の評価をそのまま表示（簡略化）
                rank_dict[label] = [v for v in df_pre[col]]
            df_img_rank = pd.DataFrame(rank_dict).set_index("艇番")

            img = create_sns_image({"place": PLACE_NAME, "num": 12, "date": str(datetime.date.today())}, df_img_rank, df_sorted)
            st.image(img, use_container_width=True)
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            st.download_button("💾 画像を保存 (PNG)", buf.getvalue(), f"yoso_{PLACE_NAME}.png", "image/png", use_container_width=True)

# --- タブ2：統計解析 & 重み算出 ---
with tab_stat:
    st.subheader(f"📊 {PLACE_NAME} 過去データ重み算出")
    if "tab2_base_df" in st.session_state:
        df_base = st.session_state["tab2_base_df"]
        
        if st.button("📈 過去データから最適重みを計算"):
            target_cols = ["展示", "直線", "回り足", "一周", "ST"]
            work_df = df_base[target_cols + ["着順"]].apply(pd.to_numeric, errors='coerce').dropna()
            # 相関を計算（着順との正の相関が強いほど重要）
            corrs = {col: max(0.01, work_df[col].corr(work_df["着順"])) for col in target_cols}
            total = sum(corrs.values())
            st.session_state["auto_weights"] = {k: v/total for k, v in corrs.items()}
            st.success("統計解析完了！")

        if "auto_weights" in st.session_state:
            aw = st.session_state["auto_weights"]
            st.write("判明した重要度：", aw)
            st.bar_chart(pd.DataFrame({"項目": aw.keys(), "重要度": aw.values()}), x="項目", y="重要度")

        st.divider()
        with st.form("stat_input"):
            st.markdown("### 📝 当日展示タイム入力")
            input_list = []
            for b in range(1, 7):
                c = st.columns(6)
                c[0].write(f"**{b}**")
                isshu = c[1].number_input("一周", step=0.01, format="%.2f", key=f"s_iss_{b}")
                mawari = c[2].number_input("回り足", step=0.01, format="%.2f", key=f"s_maw_{b}")
                choku = c[3].number_input("直線", step=0.01, format="%.2f", key=f"s_cho_{b}")
                tenji = c[4].number_input("展示", step=0.01, format="%.2f", key=f"s_ten_{b}")
                st_val = c[5].number_input("ST", step=0.01, format="%.2f", key=f"s_st_{b}")
                input_list.append({"艇番": b, "展示": tenji, "直線": choku, "一周": isshu, "回り足": mawari, "ST": st_val})
            calc_sub = st.form_submit_button("🔥 統計重みで解析実行", use_container_width=True)

        if calc_sub:
            in_df = pd.DataFrame(input_list).set_index("艇番")
            st.session_state["tab2_input_df"] = in_df
            aw = st.session_state.get("auto_weights", {k: 0.2 for k in ["展示", "直線", "回り足", "一周", "ST"]})
            # スコアリング（タイムが良いほど加点）
            def score_row(r):
                s = sum([(in_df[col].max() - r[col]) * aw[col] * 100 for col in ["展示", "直線", "回り足", "一周", "ST"]])
                return s
            in_df["機力総合スコア"] = in_df.apply(score_row, axis=1)
            st.dataframe(in_df.sort_values("機力総合スコア", ascending=False).style.highlight_max(axis=0), use_container_width=True)

# --- タブ3：スリット予想 (既存機能を踏襲) ---
with tab_start:
    st.subheader("🟦 スリット予想イメージ")
    if "tab2_input_df" in st.session_state:
        res_df = st.session_state["tab2_input_df"].copy().reset_index()
        for _, r in res_df.iterrows():
            offset = 150 + ((r["機力総合スコア"]) * 2) # スコアで位置調整
            st.markdown(f"""<div style="height:40px; border-bottom:1px solid #333; display:flex; align-items:center;">
                <div style="margin-left:{max(10, offset)}px; background:white; color:black; padding:2px 10px; border-radius:3px; font-weight:bold;">{int(r['艇番'])}</div>
                <div style="margin-left:10px; font-size:12px; color:gray;">ST: {r['ST']:.2f}</div>
            </div>""", unsafe_allow_html=True)
    else: st.info("統計解析タブでタイムを入力してください")

# --- タブ4：項目別順位 ---
with tab_rank:
    if "tab2_input_df" in st.session_state:
        st.subheader("🥇 展示項目別・順位表")
        st.dataframe(st.session_state["tab2_input_df"].rank(method="min", ascending=True))
    else: st.info("データがありません")
