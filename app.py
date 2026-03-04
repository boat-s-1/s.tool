import streamlit as st
import pandas as pd
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import io
import datetime
import plotly.express as px
import streamlit.components.v1 as components

# ==========================================
# 1. 基本設定とスプレッドシートURL（2系統）
# ==========================================
st.set_page_config(page_title="競艇Pro Analytica - 実績統合モデル", layout="wide", page_icon="🎯")

# 公開したCSV用URLをここに貼り付けてください
SHEET_URL_1 = "https://docs.google.com/spreadsheets/d/e/2PACX-1vSt_AnojtOiUaKDfvsUntxnu8JIwYisFYaU7wwjsrjHq6Kv1cWPPZoqMyVM97hHgx6zWPxU02CZYBgP/pub?output=csv"
SHEET_URL_2 = "https://docs.google.com/spreadsheets/d/e/2PACX-1vT5ljmK3YV1lspajPJCSM62VP2FM4w2WKjdgQ2rOrfS6XC96eF6skCo2MAyxbtWXyHJIFyajpsM-7yU/pub?output=csv"

# ==========================================
# 2. 統計データ解析エンジン（2シート統合版）
# ==========================================
@st.cache_data(ttl=3600)
def load_and_analyze_combined_stats():
    # 読み込み失敗時のバックアップ
    DEFAULT_STATS = {
        "DEFAULT": {"展示信頼度": 35.0, "展示貢献度": 65.0, "イン逃げ率": 50.0, "サンプル数": 0}
    }

    try:
        # 2つのシートを読み込んで合体
        df1 = pd.read_csv(SHEET_URL_1)
        df2 = pd.read_csv(SHEET_URL_2)
        combined_df = pd.concat([df1, df2], ignore_index=True)
        
        # 列名のクリーニング（空白削除）
        combined_df.columns = combined_df.columns.str.strip()
        
        # 重複データの削除（キー：日付、会場、レース番号、艇番）
        combined_df = combined_df.drop_duplicates(subset=['日付', '会場', 'レース番号', '艇番'])
        
        # 着順の数値化
        combined_df['着順_num'] = pd.to_numeric(combined_df['着順'], errors='coerce')
        
        # 展示タイムに基づくレース内順位（昇順）
        combined_df['展示順位'] = combined_df.groupby(['日付', 'レース番号', '会場'])['展示'].rank(method='min')
        
        stats = {}
        unique_places = combined_df['会場'].unique()
        
        for place in unique_places:
            if pd.isna(place): continue
            p_df = combined_df[combined_df['会場'] == place]
            top_ex = p_df[p_df['展示順位'] == 1]
            
            # 統計計算
            win_rate = (top_ex['着順_num'] == 1).mean() * 100 if not top_ex.empty else 35.0
            show_rate = (top_ex['着順_num'] <= 3).mean() * 100 if not top_ex.empty else 65.0
            in_nige = (p_df[p_df['艇番'] == 1]['着順_num'] == 1).mean() * 100 if not p_df[p_df['艇番'] == 1].empty else 50.0
            
            stats[place] = {
                "展示信頼度": round(win_rate, 1),
                "展示貢献度": round(show_rate, 1),
                "イン逃げ率": round(in_nige, 1),
                "サンプル数": len(p_df)
            }
        
        if not stats: return DEFAULT_STATS
        return stats

    except Exception as e:
        st.sidebar.error(f"⚠️ 読み込みエラー: URLや列名を確認してください。")
        st.sidebar.caption(f"詳細: {e}")
        return DEFAULT_STATS

# データの実行
ACTUAL_STATS = load_and_analyze_combined_stats()

# ==========================================
# 3. 共通デザイン設定
# ==========================================
get_symbol = lambda val: {6: "◎", 5: "○", 4: "▲", 3: "△", 2: "×", 1: "・", 0: "無"}.get(val, "無")
boat_bg = {1: "#ffffff", 2: "#333333", 3: "#e03131", 4: "#1971c2", 5: "#fcc419", 6: "#2f9e44"}
boat_tx = {1: "#000000", 2: "#ffffff", 3: "#ffffff", 4: "#ffffff", 5: "#000000", 6: "#ffffff"}
boat_colors_rgb = {1: (255,255,255), 2: (51,51,51), 3: (224,49,49), 4: (25,113,194), 5: (252,196,25), 6: (47,158,68)}

def create_final_image(place, num, df_live):
    width, height = 1200, 800
    img = Image.new('RGB', (width, height), color=(245, 245, 245))
    draw = ImageDraw.Draw(img)
    draw.rectangle([0, 0, width, 150], fill=(30, 40, 60))
    draw.text((40, 60), f"{place} {num}R FINAL YOSO", fill=(255, 255, 255))
    records = df_live.head(3).to_dict(orient='records')
    for i, row in enumerate(records):
        y_off = 180 + (i * 180)
        b_no = int(row.get('艇番', 0))
        exp_val = row.get('期待値', 0)
        fill_color = boat_colors_rgb.get(b_no, (200, 200, 200))
        draw.rounded_rectangle([50, y_off, 1150, y_off + 150], radius=15, fill=fill_color)
        txt_color = (0,0,0) if b_no in [1, 5] else (255,255,255)
        draw.text((80, y_off + 65), f"RANK {i+1}   BOAT: {b_no}号艇   EXPECTED: {exp_val}%", fill=txt_color)
    return img

# ==========================================
# 4. サイドバー・メイン画面
# ==========================================
with st.sidebar:
    st.header("📋 設定")
    available_places = sorted(list(ACTUAL_STATS.keys()))
    r_place = st.selectbox("開催地", available_places if available_places else ["桐生"])
    r_num = st.number_input("レース番号", 1, 12, 1)
    
    p_stat = ACTUAL_STATS.get(r_place, ACTUAL_STATS.get("DEFAULT"))
    st.divider()
    st.metric("実績イン逃げ率", f"{p_stat['イン逃げ率']}%")
    st.metric("展示1位の1着率", f"{p_stat['展示信頼度']}%")
    st.caption(f"分析対象: {p_stat['サンプル数']} レース統合")
    
    st.write("")
    ad_code = '<div style="display:flex; justify-content:center;"><script src="https://adm.shinobi.jp/s/00848ad75df65c15ca7f98de1efcf942"></script></div>'
    components.html(ad_code, height=260)

tab1, tab2, tab3 = st.tabs(["📝 事前予想", "🔥 実績連動解析", "📸 SNS画像生成"])

# --- タブ1: 事前 ---
with tab1:
    st.subheader("📊 事前スコアリング")
    with st.form("pre_form"):
        pre_raw = []
        for i in range(1, 7):
            with st.expander(f"{i}号艇の詳細入力", expanded=(i==1)):
                st.markdown(f'<div style="background:{boat_bg[i]}; color:{boat_tx[i]}; padding:5px; border-radius:5px; text-align:center;">{i}号艇</div>', unsafe_allow_html=True)
                m = st.select_slider(f"モーター_{i}", range(7), 0, get_symbol)
                t = st.select_slider(f"当地_{i}", range(7), 0, get_symbol)
                w = st.select_slider(f"枠番勝率_{i}", range(7), 0, get_symbol)
                s = st.select_slider(f"枠番ST_{i}", range(7), 0, get_symbol)
                pre_raw.append({"艇番": i, "score": (m*0.25+t*0.2+w*0.35+s*0.2)})
        st.form_submit_button("事前ランキング確定")

# --- タブ2: 直前解析 ---
with tab2:
    st.subheader(f"🏟️ {r_place} 実績連動モデル")
    
    # 展示信頼度に基づいた動的ウェイト
    ex_w = min(0.5, p_stat['展示信頼度'] / 100 + 0.1)
    other_w = (1.0 - ex_w) / 3
    weights = {"展示": round(ex_w, 2), "直線": round(other_w, 2), "回り足": round(other_w, 2), "一周": round(other_w, 2)}

    # 
    st.plotly_chart(px.pie(values=list(weights.values()), names=list(weights.keys()), hole=0.4, title="この会場の重要度配分"), use_container_width=True)

    with st.form("live_form"):
        live_raw = []
        cols = st.columns(2)
        for i in range(1, 7):
            with cols[(i-1)%2]:
                with st.expander(f"{i}号艇の気配入力", expanded=(i==1)):
                    st.markdown(f'<div style="background:{boat_bg[i]}; color:{boat_tx[i]}; padding:5px; border-radius:4px; text-align:center;">{i}号艇</div>', unsafe_allow_html=True)
                    f1 = st.select_slider(f"展示_{i}", range(7), 0, get_symbol)
                    f2 = st.select_slider(f"直線_{i}", range(7), 0, get_symbol)
                    f3 = st.select_slider(f"回り足_{i}", range(7), 0, get_symbol)
                    f4 = st.select_slider(f"一周_{i}", range(7), 0, get_symbol)
                    score = (f1*weights["展示"] + f2*weights["直線"] + f3*weights["回り足"] + f4*weights["一周"])
                    live_raw.append({"艇番": i, "score": score, "展示": get_symbol(f1), "直線": get_symbol(f2), "回り足": get_symbol(f3), "一周": get_symbol(f4)})
        
        if st.form_submit_button("実績反映して最終解析", use_container_width=True, type="primary"):
            df_live = pd.DataFrame(live_raw).sort_values("score", ascending=False)
            df_live["期待値"] = (df_live["score"] / df_live["score"].sum() * 100).round(1)
            st.session_state["final_res"] = df_live
            st.success(f"推奨：{df_live.iloc[0]['艇番']}号艇（展示貢献度: {p_stat['展示貢献度']}%）")
            st.dataframe(df_live[["艇番", "期待値", "展示", "直線", "回り足", "一周"]], use_container_width=True, hide_index=True)

# --- タブ3: 画像生成 ---
with tab3:
    if "final_res" in st.session_state:
        if st.button("✨ 画像生成"):
            img = create_final_image(r_place, r_num, st.session_state["final_res"])
            st.image(img, use_container_width=True)
import streamlit.components.v1 as components

# ==========================================
# 1. 基本設定とスプレッドシートURL（2系統）
# ==========================================
st.set_page_config(page_title="競艇Pro Analytica - 複数シート統合版", layout="wide", page_icon="🎯")

# 1枚目のスプレッドシートURL
SHEET_URL_1 = "https://docs.google.com/spreadsheets/d/e/2PACX-1vSt_AnojtOiUaKDfvsUntxnu8JIwYisFYaU7wwjsrjHq6Kv1cWPPZoqMyVM97hHgx6zWPxU02CZYBgP/pub?output=csv"
# 2枚目のスプレッドシートURL
SHEET_URL_2 = "https://docs.google.com/spreadsheets/d/e/2PACX-1vT5ljmK3YV1lspajPJCSM62VP2FM4w2WKjdgQ2rOrfS6XC96eF6skCo2MAyxbtWXyHJIFyajpsM-7yU/pub?output=csv"

# ==========================================
# 2. 統計データ解析エンジン（統合版）
# ==========================================
@st.cache_data(ttl=3600)
def load_and_analyze_combined_stats():
    DEFAULT_STATS = {
        "DEFAULT": {"展示信頼度": 35.0, "展示貢献度": 65.0, "イン逃げ率": 50.0, "サンプル数": 0}
    }

    try:
        # 1. 両方のシートを読み込む
        df1 = pd.read_csv(SHEET_URL_1)
        df2 = pd.read_csv(SHEET_URL_2)
        
        # 2. データを合体させる
        combined_df = pd.concat([df1, df2], ignore_index=True)
        
        # 3. 列名の空白削除
        combined_df.columns = combined_df.columns.str.strip()
        
        # 4. 重複データの削除（日付・会場・レース番号・艇番が同じなら1つにする）
        combined_df = combined_df.drop_duplicates(subset=['日付', '会場', 'レース番号', '艇番'])
        
        # 5. 解析処理（数値化など）
        combined_df['着順_num'] = pd.to_numeric(combined_df['着順'], errors='coerce')
        combined_df['展示順位'] = combined_df.groupby(['日付', 'レース番号', '会場'])['展示'].rank(method='min')
        
        stats = {}
        unique_places = combined_df['会場'].unique()
        
        for place in unique_places:
            p_df = combined_df[combined_df['会場'] == place]
            top_ex = p_df[p_df['展示順位'] == 1]
            
            win_rate = (top_ex['着順_num'] == 1).mean() * 100 if not top_ex.empty else 35.0
            show_rate = (top_ex['着順_num'] <= 3).mean() * 100 if not top_ex.empty else 65.0
            in_nige = (p_df[p_df['艇番'] == 1]['着順_num'] == 1).mean() * 100 if not p_df[p_df['艇番'] == 1].empty else 50.0
            
            stats[place] = {
                "展示信頼度": round(win_rate, 1),
                "展示貢献度": round(show_rate, 1),
                "イン逃げ率": round(in_nige, 1),
                "サンプル数": len(p_df)
            }
        
        if not stats: return DEFAULT_STATS
        return stats

    except Exception as e:
        st.sidebar.error(f"⚠️ シート統合エラー: {e}")
        return DEFAULT_STATS

# データの実行
ACTUAL_STATS = load_and_analyze_combined_stats()

# ==========================================
# 3. 画面表示（前回と同様）
# ==========================================
# デザイン・タブ・フォーム部分は前回のコードをそのまま引き継いでください
# （ACTUAL_STATS を使う部分は自動で統合されたデータが反映されます）

# --- 以下、前回のコードの「ユーティリティ」以降を貼り付けてください ---


