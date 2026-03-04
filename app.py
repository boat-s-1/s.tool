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
