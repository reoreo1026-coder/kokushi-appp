
import random
import streamlit as st
import requests
from datetime import datetime, timedelta
import json
import io
import hashlib

# =========================================================
# Googleスプレッドシート連携
# =========================================================
# ここにApps Scriptの「ウェブアプリURL」（末尾が /exec）を設定してください。
API_URL = "https://script.google.com/macros/s/AKfycbw_0fl6aX0Czf30OJ8WQevzq1bRzna95kxpuNBF_E0X1-BVLZqP-QArnc0z_aM6PweXwg/exec"


def sheets_url_ready():
    return API_URL.startswith("https://script.google.com/macros/s/") and API_URL.endswith("/exec")


def sheets_get(params):
    """Apps Scriptから進捗やランキングを取得する。"""
    if not sheets_url_ready():
        return None
    try:
        response = requests.get(API_URL, params=params, timeout=20)
        response.raise_for_status()
        result = response.json()
        if result.get("status") == "success":
            return result
        return None
    except (requests.RequestException, ValueError):
        return None


def load_user_progress(user_name):
    """同じユーザー名で保存されている進捗を読み込む。"""
    result = sheets_get({"action": "progress", "user": user_name})
    if not result:
        return None
    progress = result.get("progress")
    return progress if isinstance(progress, dict) else None


def save_user_progress():
    """現在の進捗をGoogleスプレッドシートへ保存する。"""
    if not sheets_url_ready() or not st.session_state.get("user_name"):
        return False

    progress = {
        "user_name": st.session_state.user_name,
        "school_year": st.session_state.school_year,
        "exam_year": st.session_state.exam_year,
        "xp": st.session_state.xp,
        "level": st.session_state.level,
        "coins": st.session_state.coins,
        "streak": st.session_state.streak,
        "total_answered": st.session_state.total_answered,
        "total_correct": st.session_state.total_correct,
        "road_completed_questions": st.session_state.road_completed_questions,
        "review_records": st.session_state.review_records,
        "last_score": st.session_state.last_score,
        "last_total": st.session_state.last_total,
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }

    try:
        response = requests.post(
            API_URL,
            json={"action": "save_progress", "user": st.session_state.user_name, "progress": progress},
            timeout=20,
        )
        response.raise_for_status()
        result = response.json()
        return result.get("status") == "success"
    except (requests.RequestException, ValueError):
        st.warning("進捗の保存に失敗しました。Apps ScriptのデプロイとURLを確認してください。")
        return False


def send_result(q, selected_index, is_correct, confidence):
    """回答履歴をGoogleスプレッドシートへ送信する。"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    answer_text = q["choices"][selected_index]
    correct_text = q["choices"][q["answer"]]
    result_text = "正解" if is_correct else "不正解"

    data = {
        "action": "answer",
        "日時": timestamp,
        "ユーザー名": st.session_state.user_name,
        "問題番号": q["question"],
        "回答": answer_text,
        "正解": correct_text,
        "正誤": result_text,
        "自信度": confidence,
        "分野": q["field"],
    }

    if not sheets_url_ready():
        st.warning("Google Sheets連携URLを設定してください。main.py上部のAPI_URLを書き換えてください。")
        return False

    try:
        response = requests.post(API_URL, json=data, timeout=20)
        response.raise_for_status()
        result = response.json()
        if result.get("status") != "success":
            st.warning("回答履歴を保存できませんでした。Apps Script側のコードを確認してください。")
            return False
        return True
    except (requests.RequestException, ValueError) as e:
        st.warning(f"学習記録の送信に失敗しました: {e}")
        return False


def get_leaderboard():
    """ユーザー別ランキングを取得する。"""
    result = sheets_get({"action": "leaderboard"})
    if not result:
        return []
    rows = result.get("leaderboard", [])
    return rows if isinstance(rows, list) else []

# =========================================================
# ページ設定
# =========================================================

st.set_page_config(
    page_title="国試トレーナー",
    page_icon="🎓",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# =========================================================
# 初期状態
# =========================================================

DEFAULTS = {
    # 画面
    "page": "setup",
    "profile_set": False,

    # プロフィール
    "user_name": "",
    "school_year": "4年生",
    "exam_year": "2027年",

    # ゲーム
    "xp": 0,
    "level": 0,
    "coins": 0,
    "streak": 0,

    # クイズ
    "quiz_questions": [],
    "custom_questions": [],
    "slide_sources": {},
    "pending_slide_questions": [],
    "quiz_index": 0,
    "score": 0,
    "quiz_mode": "normal",
    "last_total": 5,

    # 復習データ（問題文をキーに最新の回答状況を保存）
    "review_records": {},

    # 回答状態
    "selected_answer": None,
    "confidence": None,
    "answer_revealed": False,
    "last_correct": None,

    # 国試ロード進捗（1回以上回答した問題を問題文で記録）
    "road_completed_questions": [],

    # 学習データ
    "total_answered": 0,
    "total_correct": 0,

    # 結果
    "last_score": 0,
}

for key, value in DEFAULTS.items():
    if key not in st.session_state:
        st.session_state[key] = value


# =========================================================
# 問題データ
# =========================================================

QUESTION_BANK = [
    {
        "field": "核医学",
        "question": "体内から放出されるγ線を検出して画像化する装置はどれか。",
        "choices": ["ガンマカメラ", "MRI装置", "超音波診断装置", "一般撮影装置", "リニアック"],
        "answer": 0,
        "explanation": "ガンマカメラは、放射性医薬品から放出されるγ線を検出して画像化する装置です。",
    },
    {
        "field": "核医学",
        "question": "99mTcの物理的半減期として正しいのはどれか。",
        "choices": ["約6秒", "約6分", "約6時間", "約6日", "約6年"],
        "answer": 2,
        "explanation": "99mTcの物理的半減期は約6時間です。核医学検査で広く利用される核種です。",
    },
    {
        "field": "核医学",
        "question": "PETで消滅放射線として検出する光子のエネルギーはどれか。",
        "choices": ["140 keV", "364 keV", "511 keV", "662 keV", "1.17 MeV"],
        "answer": 2,
        "explanation": "陽電子と電子が対消滅すると、通常は511 keVの光子が2本、ほぼ反対方向に放出されます。",
    },
    {
        "field": "核医学",
        "question": "肺血流シンチグラフィに用いられる代表的な放射性医薬品はどれか。",
        "choices": ["99mTc-MAA", "99mTc-DMSA", "123I-MIBG", "18F-FDG", "131I-アドステロール"],
        "answer": 0,
        "explanation": "99mTc-MAAは肺毛細血管床に一時的に捕捉されるため、肺血流シンチグラフィに用いられます。",
    },
    {
        "field": "核医学",
        "question": "腎皮質の形態や局所機能の評価に適している放射性医薬品はどれか。",
        "choices": ["99mTc-DMSA", "99mTc-MAA", "99mTc-MDP", "123I-IMP", "201TlCl"],
        "answer": 0,
        "explanation": "99mTc-DMSAは腎皮質に集積するため、腎皮質シンチグラフィに用いられます。",
    },
    {
        "field": "核医学",
        "question": "糸球体濾過量（GFR）の評価に用いられる放射性医薬品はどれか。",
        "choices": ["99mTc-DTPA", "99mTc-MAG3", "99mTc-MAA", "123I-MIBG", "99mTc-MDP"],
        "answer": 0,
        "explanation": "99mTc-DTPAは糸球体で濾過されるため、GFRの評価に用いられます。99mTc-MAG3は主に尿細管分泌を反映します。",
    },
    {
        "field": "核医学",
        "question": "99Mo-99mTcジェネレータから99mTcを取り出す操作はどれか。",
        "choices": ["溶出", "遠心分離", "昇華", "電気泳動", "蒸留"],
        "answer": 0,
        "explanation": "親核種99Moから生成した99mTcを、生理食塩液などで溶出して取り出します。",
    },
    {
        "field": "核医学",
        "question": "18F-FDG PETで集積が高くなりやすいのはどれか。",
        "choices": ["糖代謝が亢進した組織", "空気を含む部位", "皮質骨だけ", "集積は血流だけで決まる", "正常組織には全く集積しない"],
        "answer": 0,
        "explanation": "18F-FDGはブドウ糖類似体で、糖代謝が亢進した腫瘍などに集積しやすい性質があります。ただし炎症などでも集積することがあります。",
    },
    {
        "field": "核医学",
        "question": "骨シンチグラフィで一般に用いられる放射性医薬品はどれか。",
        "choices": ["99mTc-MDP", "99mTc-DMSA", "99mTc-MAA", "123I-MIBG", "123I-IMP"],
        "answer": 0,
        "explanation": "99mTc-MDPなどの99mTc標識リン酸化合物は骨代謝に関連して集積し、骨シンチグラフィに用いられます。",
    },
    {
        "field": "核医学",
        "question": "123I-MIBGシンチグラフィが診断に用いられる代表的な疾患はどれか。",
        "choices": ["褐色細胞腫", "肺塞栓症", "腎結石", "椎間板ヘルニア", "胆石症"],
        "answer": 0,
        "explanation": "123I-MIBGは交感神経系に関連する組織に集積し、褐色細胞腫や神経芽腫などの評価に用いられます。",
    },
    {
        "field": "核医学",
        "question": "分化型甲状腺癌の放射性ヨウ素内用療法に用いられる核種はどれか。",
        "choices": ["89Sr", "131I", "99mTc", "123I", "201Tl"],
        "answer": 1,
        "explanation": "131Iは分化型甲状腺癌の放射性ヨウ素内用療法に用いられます。",
    },
    {
        "field": "核医学",
        "question": "SPECTの特徴として正しいのはどれか。",
        "choices": [
            "単一方向の投影画像だけを撮影する",
            "多方向の投影データを収集し、断層像を再構成する",
            "磁気共鳴信号のみを利用する",
            "超音波の反射を画像化する",
            "X線の透過像を得る",
        ],
        "answer": 1,
        "explanation": "SPECTではガンマカメラなどで多方向から投影データを収集し、コンピュータで断層像を再構成します。",
    },
    {
        "field": "核医学",
        "question": "放射性医薬品の投与後、時間とともに集積や排泄の変化を撮影する検査はどれか。",
        "choices": ["ダイナミック収集", "単純X線撮影", "MRIのT1強調撮像", "超音波ドプラ法", "マンモグラフィ"],
        "answer": 0,
        "explanation": "ダイナミック収集では時間経過に伴う放射能分布の変化を連続的に収集し、血流や臓器機能などを評価します。",
    },
]


# =========================================================
# CSS
# =========================================================

st.markdown("""
<style>

* {
    box-sizing: border-box;
}

html,
body,
[data-testid="stApp"],
[data-testid="stAppViewContainer"],
section.main {
    margin: 0 !important;
    padding: 0 !important;
    width: 100% !important;
    min-height: 100vh !important;

    background:
        radial-gradient(
            circle at 50% -8%,
            #284b72 0%,
            #132942 28%,
            #071421 63%,
            #040a11 100%
        ) !important;

    color: white !important;
}

[data-testid="stHeader"] {
    display: none !important;
}

footer,
#MainMenu {
    display: none !important;
}

.block-container {
    width: min(430px, 100vw) !important;
    max-width: 430px !important;

    margin: 0 auto !important;

    padding:
        6px
        7px
        10px
        7px !important;
}


/* =========================================================
   SETUP
========================================================= */

.setup-card {
    margin-top: 8vh;

    padding: 24px 18px 20px;

    border-radius: 18px;

    background:
        linear-gradient(
            160deg,
            #102a45,
            #091729
        );

    border: 1px solid #3c607d;

    box-shadow:
        0 12px 35px
        rgba(0,0,0,.25);

    text-align: center;
}

.setup-logo {
    width: 68px;
    height: 68px;

    margin: auto;

    border-radius: 18px;

    background:
        linear-gradient(
            145deg,
            #c9c1ff,
            #8b81d3
        );

    display: flex;
    align-items: center;
    justify-content: center;

    font-size: 34px;
}

.setup-title {
    margin-top: 12px;

    font-size: 24px;

    font-weight: 900;
}

.setup-sub {
    color: #96aabd;

    font-size: 8px;

    margin-top: 5px;

    line-height: 1.5;
}

.setup-status {
    margin-top: 15px;

    padding: 8px;

    border-radius: 8px;

    background: #142b45;

    border: 1px solid #2d506d;

    color: #a9bbca;

    font-size: 7px;

    line-height: 1.5;
}

div[data-testid="stTextInput"] label,
div[data-testid="stSelectbox"] label {
    color: #d5e0e9 !important;
    font-size: 8px !important;
    font-weight: 900 !important;
}


/* =========================================================
   BUTTON
========================================================= */

div.stButton {
    margin-top: 4px !important;
}

div.stButton > button {
    width: 100% !important;

    min-height: 38px !important;

    border-radius: 10px !important;

    border: 1px solid #4a6882 !important;

    background:
        linear-gradient(
            145deg,
            #193550,
            #0e2137
        ) !important;

    color: #edf2f7 !important;

    font-weight: 900 !important;

    box-shadow:
        0 4px 10px
        rgba(0,0,0,.14) !important;
}

div.stButton > button:hover {
    border-color: #aba1ea !important;
    color: #ded8ff !important;
}


/* =========================================================
   HOME
========================================================= */

.home-header {
    height: 46px;

    display: flex;

    align-items: center;

    justify-content: space-between;
}

.brand {
    display: flex;

    align-items: center;

    gap: 7px;
}

.logo {
    width: 37px;
    height: 37px;

    border-radius: 10px;

    background:
        linear-gradient(
            145deg,
            #c8c1ff,
            #8980d1
        );

    display: flex;
    align-items: center;
    justify-content: center;

    font-size: 18px;
}

.brand-title {
    font-size: 15px;
    font-weight: 900;
    line-height: 1;
}

.brand-sub {
    font-size: 5px;
    color: #8ea4b9;
    margin-top: 3px;
}

.level-area {
    text-align: center;
}

.user-name {
    color: #91a5b9;
    font-size: 6px;
}

.level-number {
    color: white;
    font-size: 15px;
    font-weight: 900;
}

.level-bar {
    width: 55px;
    height: 4px;

    margin-top: 2px;

    border-radius: 8px;

    background: #1c3045;

    overflow: hidden;
}

.level-fill {
    height: 100%;

    background:
        linear-gradient(
            90deg,
            #c0b8ff,
            #8d84d8
        );
}

.streak {
    color: #8fa3b7;

    text-align: right;

    font-size: 6px;
}

.streak strong {
    color: #f0a17c;

    font-size: 15px;
}


/* =========================================================
   STATUS
========================================================= */

.status-row {
    height: 42px;

    display: grid;

    grid-template-columns:
        repeat(2, 1fr);

    gap: 5px;
}

.status-card {
    border-radius: 9px;

    padding: 4px;

    text-align: center;

    background:
        linear-gradient(
            160deg,
            #122c49,
            #0b1a2d
        );

    border:
        1px solid
        #2c4e6d;
}

.status-label {
    color: #91a6ba;
    font-size: 5px;
}

.status-value {
    color: #f2f5f8;
    font-size: 10px;
    font-weight: 900;
    margin-top: 2px;
}

.status-xp {
    grid-column: span 2;
}


/* =========================================================
   LEAGUE
========================================================= */

.league {
    height: 36px;

    margin-top: 4px;

    padding: 4px 9px;

    border-radius: 9px;

    display: flex;

    align-items: center;

    gap: 7px;

    background:
        linear-gradient(
            135deg,
            #112741,
            #0a1729
        );

    border:
        1px solid
        #a1864c;
}

.league-icon {
    font-size: 16px;
}

.league-label {
    color: #92a6b9;
    font-size: 5px;
}

.league-rank {
    color: #f2d07b;
    font-size: 11px;
    font-weight: 900;
}


/* =========================================================
   HERO
========================================================= */

.hero {
    position: relative;

    height: 138px;

    margin-top: 4px;

    border-radius: 13px;

    overflow: hidden;

    background:
        radial-gradient(
            circle at 71% 39%,
            rgba(95,191,255,.28),
            transparent 23%
        ),
        radial-gradient(
            circle at 55% 75%,
            rgba(132,111,225,.13),
            transparent 28%
        ),
        linear-gradient(
            135deg,
            #09213a,
            #174d76 48%,
            #111f3b
        );

    border:
        1px solid
        #365d7f;
}

.hero-grid {
    position: absolute;

    inset: 0;

    opacity: .15;

    background:
        linear-gradient(
            rgba(150,211,240,.24) 1px,
            transparent 1px
        ),
        linear-gradient(
            90deg,
            rgba(150,211,240,.24) 1px,
            transparent 1px
        );

    background-size: 18px 18px;
}

.scan-big {
    position: absolute;

    width: 98px;
    height: 98px;

    right: 84px;
    top: 19px;

    border-radius: 50%;

    border:
        2px solid
        rgba(184,224,245,.34);
}

.scan-mid {
    position: absolute;

    width: 68px;
    height: 68px;

    right: 99px;
    top: 35px;

    border-radius: 50%;

    border:
        2px solid
        rgba(184,224,245,.24);
}

.scan-small {
    position: absolute;

    width: 37px;
    height: 37px;

    right: 114px;
    top: 51px;

    border-radius: 50%;

    border:
        2px solid
        rgba(184,224,245,.18);
}

.hero-mark {
    position: absolute;

    right: 138px;
    top: 29px;

    width: 48px;
    height: 48px;

    border-radius: 50%;

    display: flex;

    align-items: center;
    justify-content: center;

    color: #cce5f4;

    font-size: 20px;

    background:
        rgba(255,255,255,.04);

    border:
        1px solid
        rgba(220,236,248,.22);
}

.hero-copy {
    position: absolute;

    left: 14px;
    bottom: 14px;
}

.hero-kicker {
    color: #8bcbed;

    font-size: 6px;

    font-weight: 900;

    letter-spacing: .8px;
}

.hero-title {
    color: white;

    font-size: 23px;

    font-weight: 900;

    line-height: 1.03;

    text-shadow:
        0 2px 8px
        rgba(0,0,0,.35);
}

.hero-description {
    color: #9eb8cc;

    font-size: 5px;

    margin-top: 5px;
}


/* =========================================================
   トレーニング
========================================================= */

.training-label {
    height: 16px;

    display: flex;

    align-items: center;

    color: #dce6ef;

    font-size: 6px;

    font-weight: 900;
}

.match-card {
    height: 67px;

    position: relative;

    overflow: hidden;

    padding:
        6px 9px;

    border-radius: 10px;

    background:
        radial-gradient(
            circle at 78% 40%,
            rgba(72,160,222,.17),
            transparent 28%
        ),
        linear-gradient(
            135deg,
            #132b46,
            #08182a
        );

    border:
        1px solid
        #9c7f47;
}

.stage-tag {
    display: inline-block;

    padding: 2px 5px;

    border-radius: 4px;

    background: #183d5f;

    color: #c7d8e7;

    font-size: 5px;
}

.match-title {
    font-size: 16px;

    font-weight: 900;

    margin-top: 4px;
}

.match-sub {
    color: #95aabd;

    font-size: 5px;

    margin-top: 3px;
}

.match-info {
    color: #8196aa;

    font-size: 4.5px;

    margin-top: 3px;
}


/* =========================================================
   ミッション
========================================================= */

.info-grid {
    width: 100%;

    height: 70px;

    margin-top: 4px;

    display: grid;

    grid-template-columns:
        1fr;

    gap: 4px;
}

.info-panel {
    height: 70px;

    border-radius: 10px;

    overflow: hidden;

    background:
        linear-gradient(
            160deg,
            #102640,
            #09182a
        );

    border:
        1px solid
        #294968;
}

.info-head {
    height: 19px;

    display: flex;

    align-items: center;

    padding-left: 7px;

    color: #dce6ee;

    background:
        #142d49;

    border-bottom:
        1px solid
        #27445e;

    font-size: 5.5px;

    font-weight: 900;
}

.info-body {
    padding:
        4px 6px;

    display: grid;

    grid-template-columns:
        1fr
        1fr
        1fr
        1fr;

    gap: 4px;
}

.mission-box {
    font-size: 5px;

    color: #aabdcb;
}

.mission-title {
    margin-bottom: 2px;
}

.mission-progress {
    height: 4px;

    background: #1a3046;

    border-radius: 6px;

    overflow: hidden;
}

.mission-fill {
    height: 100%;

    background:
        linear-gradient(
            90deg,
            #bcb3ff,
            #8d83da
        );
}


/* =========================================================
   おすすめ
========================================================= */

.recommend {
    height: 37px;

    margin-top: 4px;

    padding:
        4px 7px;

    display: flex;

    align-items: center;

    gap: 6px;

    border-radius: 9px;

    background:
        linear-gradient(
            135deg,
            #152b45,
            #0f1b2d
        );

    border:
        1px solid
        #36536c;
}

.recommend-icon {
    font-size: 13px;
}

.recommend-title {
    color: #efd17d;

    font-size: 5px;

    font-weight: 900;
}

.recommend-text {
    color: #91a5b7;

    font-size: 4.3px;

    white-space: nowrap;
}


/* =========================================================
   ROAD
========================================================= */

.road-card {
    height: 44px;

    margin-top: 4px;

    padding:
        4px 6px;

    border-radius: 9px;

    background:
        linear-gradient(
            135deg,
            #0e2137,
            #091526
        );

    border:
        1px solid
        #294963;
}

.road-title {
    color: #dce5ee;

    font-size: 5.5px;

    font-weight: 900;
}

.road-sub {
    color: #7f94a8;

    font-size: 4px;

    margin:
        1px 0
        3px;
}

.road-line {
    display: flex;

    align-items: center;
}

.road-node {
    width: 34px;

    text-align: center;
}

.node {
    width: 18px;
    height: 18px;

    margin: auto;

    border-radius: 50%;

    display: flex;

    align-items: center;
    justify-content: center;

    background: #182b41;

    border:
        2px solid
        #657a8f;

    color: #a6b4c2;

    font-size: 6px;

    font-weight: 900;
}

.node.done {
    background:
        linear-gradient(
            145deg,
            #c1b9ff,
            #8b82d7
        );

    border-color: #a69de8;

    color: white;
}

.node-text {
    color: #8094a7;

    font-size: 3.8px;

    margin-top: 1px;
}

.connector {
    flex: 1;

    height: 2px;

    background:
        linear-gradient(
            90deg,
            #8d84d8,
            #344e66
        );
}


/* =========================================================
   その他ページ
========================================================= */

.page-box {
    margin-top: 8px;

    padding: 13px;

    border-radius: 14px;

    background:
        linear-gradient(
            160deg,
            #102742,
            #091829
        );

    border:
        1px solid
        #2b4c6b;
}

.page-title {
    font-size: 20px;
    font-weight: 900;
}

.page-subtitle {
    color: #91a5b8;
    font-size: 8px;
    margin-top: 3px;
}

.info-card {
    margin-top: 6px;

    padding: 10px;

    border-radius: 11px;

    background:
        linear-gradient(
            160deg,
            #102742,
            #091829
        );

    border:
        1px solid
        #2b4c6b;
}


/* =========================================================
   問題画面
========================================================= */

.quiz-question {
    margin-top: 7px;

    padding: 13px;

    border-radius: 12px;

    background:
        linear-gradient(
            160deg,
            #122945,
            #0a182a
        );

    border:
        1px solid
        #2c4d69;
}

.quiz-question-label {
    color: #89a0b4;

    font-size: 6px;
}

.quiz-question-text {
    margin-top: 8px;

    color: #ffffff;

    font-size: 14px;

    font-weight: 900;

    line-height: 1.6;
}

.confidence-box {
    margin-top: 9px;

    padding: 10px;

    border-radius: 10px;

    background:
        #10233b;

    border:
        1px solid
        #2b4d6a;
}

.confidence-title {
    color: #dce6ee;

    font-size: 8px;

    font-weight: 900;

    margin-bottom: 5px;
}


/* =========================================================
   結果
========================================================= */

.result-box {
    margin-top: 9px;

    padding: 18px;

    border-radius: 14px;

    text-align: center;

    background:
        linear-gradient(
            160deg,
            #102742,
            #091829
        );

    border:
        1px solid
        #2b4c6b;
}

.result-percent {
    margin-top: 12px;

    color: #c7bfff;

    font-size: 45px;

    font-weight: 900;
}

.result-score {
    margin-top: 4px;

    color: #95a9bb;

    font-size: 10px;
}


/* =========================================================
   スマホ
========================================================= */

@media (max-width: 430px) {

    .block-container {
        padding-left: 6px !important;
        padding-right: 6px !important;
    }

}

</style>
""", unsafe_allow_html=True)


# =========================================================
# スライドから問題・解説を自動作成する機能
# =========================================================
def get_all_questions():
    return list(QUESTION_BANK) + list(st.session_state.get("custom_questions", []))


def extract_slide_pages(uploaded_file):
    filename = uploaded_file.name.lower()
    raw = uploaded_file.getvalue()
    pages = []
    if filename.endswith(".pdf"):
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(raw))
        for i, page in enumerate(reader.pages, start=1):
            pages.append({"page": i, "text": (page.extract_text() or "").strip()})
    elif filename.endswith(".pptx"):
        from pptx import Presentation
        prs = Presentation(io.BytesIO(raw))
        for i, slide in enumerate(prs.slides, start=1):
            parts = []
            for shape in slide.shapes:
                if getattr(shape, "has_text_frame", False) and shape.text.strip():
                    parts.append(shape.text.strip())
                if getattr(shape, "has_table", False):
                    for row in shape.table.rows:
                        parts.append(" | ".join(cell.text.strip() for cell in row.cells))
            pages.append({"page": i, "text": "\n".join(parts).strip()})
    else:
        raise ValueError("PDFまたはPowerPoint（.pptx）を選択してください。")
    return raw, pages


def generate_questions_from_slides(pages, field, count, source_id):
    try:
        api_key = st.secrets.get("GEMINI_API_KEY", "")
    except Exception:
        api_key = ""
    if not api_key:
        raise RuntimeError("Gemini APIキーが未設定です。Streamlit Cloud の Settings → Secrets に GEMINI_API_KEY を設定してください。")
    usable = [{"page": p["page"], "text": p["text"][:7000]} for p in pages if p.get("text")]
    if not usable:
        raise RuntimeError("スライドから文字を抽出できませんでした。画像だけのPDFはOCRが必要です。")
    prompt = f'''あなたは診療放射線技師国家試験の教材作成アシスタントです。
スライドの文章だけを根拠に五択問題を最大{count}問作成してください。スライドにない内容を正解根拠にしないでください。
JSON配列のみで出力し、各要素を次の形式にしてください：{{"question":"問題文","choices":["選択肢1","選択肢2","選択肢3","選択肢4","選択肢5"],"answer":0,"explanation":"根拠を含む解説","source_page":1}}
answerは0始まりの正解番号、source_pageは根拠スライド番号です。情報が足りなければ問題数を減らしてください。
分野：{field}
スライド本文：{json.dumps(usable, ensure_ascii=False)}'''
    response = requests.post(
        "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent",
        params={"key": api_key},
        json={"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"responseMimeType": "application/json", "temperature": 0.2}},
        timeout=90,
    )
    response.raise_for_status()
    result = json.loads(response.json()["candidates"][0]["content"]["parts"][0]["text"])
    valid_pages = {p["page"] for p in pages}
    questions = []
    for item in result:
        choices, answer, page = item.get("choices", []), item.get("answer"), item.get("source_page")
        if isinstance(item.get("question"), str) and len(choices) == 5 and isinstance(answer, int) and 0 <= answer < 5 and isinstance(page, int) and page in valid_pages:
            questions.append({"field": field, "question": item["question"], "choices": [str(c) for c in choices], "answer": answer, "explanation": str(item.get("explanation", "")), "source_id": source_id, "source_page": page, "custom": True})
    if not questions:
        raise RuntimeError("有効な問題を作成できませんでした。スライド内容を確認して再試行してください。")
    return questions


def show_source_slide(question, key_suffix="slide"):
    source = st.session_state.get("slide_sources", {}).get(question.get("source_id"))
    if not source:
        st.info("元スライドは現在のセッションにありません。アップロードし直してください。")
        return
    page_no = int(question.get("source_page", 1))
    with st.expander(f"📄 元のスライドを見る（{source['name']}・{page_no}ページ/スライド）"):
        if source["type"] == "pdf":
            try:
                import fitz
                doc = fitz.open(stream=source["bytes"], filetype="pdf")
                page = doc.load_page(max(0, min(page_no - 1, len(doc) - 1)))
                pix = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5), alpha=False)
                st.image(pix.tobytes("png"), caption=f"元スライド {page_no}ページ", use_container_width=True)
                doc.close()
            except Exception:
                st.warning("PDFプレビューに失敗しました。原本をダウンロードしてください。")
        else:
            texts = source.get("texts", [])
            if 1 <= page_no <= len(texts):
                st.markdown(texts[page_no - 1] or "抽出できる文字がありません。")
            st.info("PowerPointはテキスト表示です。原本をダウンロードしてスライド画像を確認してください。")
        st.download_button("原本をダウンロード", data=source["bytes"], file_name=source["name"], mime=source["mime"], key=f"src_download_{key_suffix}_{source['id']}_{page_no}", use_container_width=True)


def show_add_questions():
    st.markdown("## 📥 スライドから問題を追加")
    st.caption("講義スライドを読み込み、AIで五択問題を作成します。解説から根拠となったスライドを確認できます。")
    st.warning("AIが作った問題や解説には誤りが含まれる可能性があります。登録前に必ず原資料と照合してください。")
    uploaded = st.file_uploader("講義スライド（PDF / PowerPoint）", type=["pdf", "pptx"], key="slide_question_upload")
    field = st.selectbox("分野", ["基礎医学", "放射線物理", "放射線技術", "画像工学", "X線撮影", "CT", "MRI", "核医学", "放射線治療", "放射線管理", "その他"], key="slide_question_field")
    count = st.slider("作成する問題数", 1, 10, 5, key="slide_question_count")
    if st.button("✨ スライドから問題を作成", type="primary", use_container_width=True, disabled=uploaded is None):
        try:
            raw, pages = extract_slide_pages(uploaded)
            source_id = hashlib.sha256(raw).hexdigest()[:16]
            ext = uploaded.name.lower().rsplit(".", 1)[-1]
            source = {"id": source_id, "name": uploaded.name, "bytes": raw, "type": ext, "mime": uploaded.type or "application/octet-stream", "texts": [p["text"] for p in pages], "pages": pages}
            st.session_state.slide_sources[source_id] = source
            with st.spinner("スライドを読み取り、問題を作成しています…"):
                st.session_state.pending_slide_questions = generate_questions_from_slides(pages, field, count, source_id)
            st.success(f"{len(st.session_state.pending_slide_questions)}問作成しました。登録する問題を選んでください。")
        except Exception as e:
            st.error(f"問題を作成できませんでした：{e}")
    pending = st.session_state.get("pending_slide_questions", [])
    if pending:
        approved = []
        st.markdown("### 作成した問題の確認")
        for i, q in enumerate(pending):
            with st.expander(f"{i+1}. {q['question']}", expanded=(i == 0)):
                for j, choice in enumerate(q["choices"], 1):
                    st.write(f"{j}. {choice}")
                st.write(f"**正解：** {q['choices'][q['answer']]}")
                st.write(f"**解説：** {q['explanation']}")
                st.write(f"**根拠スライド：** {q['source_page']}ページ/スライド")
                show_source_slide(q, f"preview_{i}")
                if st.checkbox("この問題を登録する", value=True, key=f"approve_slide_q_{i}"):
                    approved.append(q)
        if st.button("📚 選択した問題を登録", type="primary", use_container_width=True):
            existing = {q.get("question") for q in st.session_state.custom_questions}
            additions = [q for q in approved if q.get("question") not in existing]
            st.session_state.custom_questions.extend(additions)
            st.session_state.pending_slide_questions = []
            st.success(f"{len(additions)}問を登録しました。ホームの「スライド問題を解く」から出題できます。")
    if st.session_state.get("custom_questions"):
        st.caption(f"登録済み：{len(st.session_state.custom_questions)}問（現在のセッション内）")
        if st.button("登録したスライド問題をすべて削除", use_container_width=True):
            st.session_state.custom_questions = []
            st.session_state.review_records = {k: v for k, v in st.session_state.review_records.items() if not v.get("q", {}).get("custom")}
            st.rerun()
    if st.button("🏠 ホームへ戻る", use_container_width=True):
        go("home")

# =========================================================
# 共通関数
# =========================================================

def go(page):
    st.session_state.page = page
    st.rerun()


def add_xp(amount):
    st.session_state.xp += amount

    while st.session_state.xp >= 100:
        st.session_state.xp -= 100
        st.session_state.level += 1


def start_quiz():
    """期限到来問題と苦手問題を優先し、残りをランダム出題する。"""
    now = datetime.now()
    records = st.session_state.review_records

    due_questions = []
    weak_questions = []
    for record in records.values():
        q = record.get("q")
        if not q:
            continue

        # 間違い・自信のない問題は、期限前でも優先して復習する。
        if needs_review(record):
            weak_questions.append(q)

        due_text = record.get("next_review")
        if due_text:
            try:
                due_at = datetime.fromisoformat(due_text)
            except (TypeError, ValueError):
                due_at = None
            if due_at is not None and due_at <= now:
                due_questions.append(q)

    # 苦手問題と期限到来問題を優先。重複を避けて5問まで選ぶ。
    priority = {}
    for q in weak_questions + due_questions:
        priority[q.get("question")] = q
    selected = list(priority.values())
    random.shuffle(selected)
    selected = selected[:5]
    selected_keys = {q.get("question") for q in selected}
    remaining = [q for q in get_all_questions() if q.get("question") not in selected_keys]
    random.shuffle(remaining)
    selected.extend(remaining[:max(0, 5 - len(selected))])

    st.session_state.quiz_questions = selected
    st.session_state.quiz_mode = "normal"
    reset_quiz_state()
    go("quiz")


def reset_quiz_state():
    st.session_state.quiz_index = 0
    st.session_state.score = 0
    st.session_state.selected_answer = None
    st.session_state.confidence = None
    st.session_state.answer_revealed = False
    st.session_state.last_correct = None


def needs_review(record):
    """不正解、または自信度が低い問題を復習対象にする。"""
    return (
        not record.get("last_correct", False)
        or record.get("confidence") in ("自信なし", "やや自信なし")
    )


def start_review():
    records = st.session_state.review_records
    review_questions = [
        record["q"] for record in records.values()
        if needs_review(record)
    ]
    if not review_questions:
        st.session_state.page = "review"
        st.rerun()
        return

    random.shuffle(review_questions)
    st.session_state.quiz_questions = review_questions
    st.session_state.quiz_mode = "review"
    reset_quiz_state()
    go("quiz")


def show_review():
    records = st.session_state.review_records
    items = [record for record in records.values() if needs_review(record)]

    st.markdown("## 🔁 復習")
    st.caption("間違えた問題と、自信度が低かった問題をまとめています。")

    col1, col2, col3 = st.columns(3)
    col1.metric("復習対象", f"{len(items)}問")
    col2.metric("記録済み", f"{len(records)}問")
    col3.metric("累計回答", f"{st.session_state.total_answered}問")

    if not items:
        st.success("復習対象の問題はありません。問題を解くと、間違いや自信度に応じてここに追加されます。")
    else:
        if st.button("🔁 復習を開始する", use_container_width=True, type="primary"):
            start_review()

        st.markdown("### 復習リスト")
        for i, record in enumerate(items, start=1):
            q = record["q"]
            reasons = []
            if not record.get("last_correct", False):
                reasons.append("前回不正解")
            if record.get("confidence") in ("自信なし", "やや自信なし"):
                reasons.append("自信度低め")
            with st.expander(f"{i}. {q['question']}"):
                st.caption("・".join(reasons) or "復習対象")
                st.write("**選択肢**")
                for j, choice in enumerate(q["choices"]):
                    st.write(f"{j + 1}. {choice}")
                st.write(f"**正解：** {q['choices'][q['answer']]}")
                st.write(f"**解説：** {q['explanation']}")
                st.caption(f"回答回数：{record.get('attempts', 0)}回 / 不正解：{record.get('wrong_count', 0)}回")

    if st.button("📚 通常の学習へ", use_container_width=True):
        start_quiz()

    bottom_navigation("review")


# =========================================================
# 初回設定
# =========================================================

def show_setup():

    st.markdown(
        """
<div class="setup-card">

<div class="setup-logo">
🎓
</div>

<div class="setup-title">
国試トレーナー
</div>

<div class="setup-sub">
放射線技師国家試験を<br>
ゲーム感覚で攻略しよう
</div>

<div class="setup-status">
ここからあなたの国試攻略がスタートします。<br>
Lv.0　・　XP 0　・　🪙 0　・　🔥 0日
</div>

</div>
""",
        unsafe_allow_html=True
    )

    with st.form("profile_form"):

        name = st.text_input(
            "名前",
            placeholder="例：ヤマダ タロウ",
            max_chars=20
        )

        school_year = st.selectbox(
            "学年",
            [
                "1年生",
                "2年生",
                "3年生",
                "4年生",
            ],
            index=3
        )

        exam_year = st.selectbox(
            "受験予定年",
            [
                "2027年",
                "2028年",
                "2029年",
                "2030年",
            ],
            index=0
        )

        submitted = st.form_submit_button(
            "🚀 学習をスタート",
            use_container_width=True
        )

    if submitted:

        name = name.strip()

        if not name:

            st.error(
                "名前を入力してください。"
            )

        else:

            # 同じ名前の保存済み進捗があれば復元し、なければ新規ユーザーとして開始
            saved = load_user_progress(name)

            st.session_state.user_name = name
            st.session_state.school_year = school_year
            st.session_state.exam_year = exam_year

            if saved:
                st.session_state.school_year = saved.get("school_year", school_year)
                st.session_state.exam_year = saved.get("exam_year", exam_year)
                st.session_state.xp = int(saved.get("xp", 0))
                st.session_state.level = int(saved.get("level", 0))
                st.session_state.coins = int(saved.get("coins", 0))
                st.session_state.streak = int(saved.get("streak", 0))
                st.session_state.total_answered = int(saved.get("total_answered", 0))
                st.session_state.total_correct = int(saved.get("total_correct", 0))
                st.session_state.road_completed_questions = saved.get("road_completed_questions", [])
                st.session_state.review_records = saved.get("review_records", {})
                st.session_state.last_score = int(saved.get("last_score", 0))
                st.session_state.last_total = int(saved.get("last_total", 5))
                st.session_state.resume_notice = True
            else:
                st.session_state.xp = 0
                st.session_state.level = 0
                st.session_state.coins = 0
                st.session_state.streak = 0
                st.session_state.total_answered = 0
                st.session_state.total_correct = 0
                st.session_state.road_completed_questions = []
                st.session_state.review_records = {}
                st.session_state.last_score = 0
                st.session_state.last_total = 5
                st.session_state.resume_notice = False

            st.session_state.profile_set = True
            st.session_state.page = "home"
            save_user_progress()
            st.rerun()


# =========================================================
# 下部ナビ
# =========================================================

def bottom_navigation(active):

    st.write("")

    cols = st.columns(6)

    items = [
        ("🏠", "ホーム", "home"),
        ("📚", "学習", "quiz"),
        ("🔁", "復習", "review"),
        ("📖", "ロード", "road"),
        ("📁", "分野", "fields"),
        ("👤", "マイ", "mypage"),
    ]

    for col, (icon, label, page) in zip(cols, items):

        with col:

            if page == active:
                text = f"●\n{label}"
            else:
                text = f"{icon}\n{label}"

            if st.button(
                text,
                key=f"nav_{active}_{page}",
                use_container_width=True,
            ):

                if page == "quiz":

                    start_quiz()

                else:

                    go(page)


# =========================================================
# ホーム
# =========================================================

def show_home():

    if st.session_state.pop("resume_notice", False):
        st.success("前回の学習進捗を復元しました！")

    xp_percent = st.session_state.xp

    st.markdown(
        f"""
<div class="home-header">

<div class="brand">

<div class="logo">
🎓
</div>

<div>

<div class="brand-title">
国試トレーナー
</div>

<div class="brand-sub">
放射線技師国家試験
</div>

</div>

</div>


<div class="level-area">

<div class="user-name">
{st.session_state.user_name}
</div>

<div class="level-number">
Lv.{st.session_state.level}
</div>

<div class="level-bar">

<div class="level-fill"
style="width:{xp_percent}%">
</div>

</div>

</div>


<div class="streak">

🔥 <strong>
{st.session_state.streak}
</strong>日<br>

連続学習

</div>

</div>
""",
        unsafe_allow_html=True
    )

    # -------------------------
    # XP / コイン
    # -------------------------

    st.markdown(
        f"""
<div class="status-row">

<div class="status-card status-xp">

<div class="status-label">
⭐ XP
</div>

<div class="status-value">
{st.session_state.xp} / 100
</div>

<div style="
height:3px;
margin-top:2px;
background:#1a3046;
border-radius:8px;
overflow:hidden;
">

<div style="
height:100%;
width:{xp_percent}%;
background:
linear-gradient(
90deg,
#c0b8ff,
#8d84d8
);
">
</div>

</div>

</div>


<div class="status-card">

<div class="status-label">
🪙 コイン
</div>

<div class="status-value">
{st.session_state.coins:,}
</div>

</div>

</div>
""",
        unsafe_allow_html=True
    )

    # -------------------------
    # リーグ
    # -------------------------

    st.markdown(
        """
<div class="league">

<div class="league-icon">
🏆
</div>

<div>

<div class="league-label">
国試リーグ
</div>

<div class="league-rank">
START
</div>

</div>

<div style="
margin-left:auto;
color:#8196aa;
font-size:5px;
">
まずは5問挑戦
</div>

</div>
""",
        unsafe_allow_html=True
    )

    # -------------------------
    # HERO
    # -------------------------

    st.markdown(
        """
<div class="hero">

<div class="hero-grid"></div>

<div class="scan-big"></div>
<div class="scan-mid"></div>
<div class="scan-small"></div>

<div class="hero-mark">
✚
</div>

<div class="hero-copy">

<div class="hero-kicker">
NATIONAL EXAM TRAINER
</div>

<div class="hero-title">
国試突破への、<br>
次の一歩。
</div>

<div class="hero-description">
毎日の学習を積み重ねて合格へ。
</div>

</div>

</div>
""",
        unsafe_allow_html=True
    )

    # -------------------------
    # 本日の学習
    # -------------------------

    st.markdown(
        """
<div class="training-label">
⚔ 本日のトレーニング
</div>

<div class="match-card">

<div class="stage-tag">
STAGE 1　FIRST STEP
</div>

<div class="match-title">
核医学 国試演習
</div>

<div class="match-sub">
核医学
</div>

<div class="match-info">
核医学・5問 / 1セット
</div>

</div>
""",
        unsafe_allow_html=True
    )

    if st.button(
        "📚　学習開始　▶",
        key="home_start",
        use_container_width=True,
    ):
        start_quiz()

    # -------------------------
    # ミッション
    # -------------------------

    st.markdown(
        """
<div class="info-grid">

<div class="info-panel">

<div class="info-head">
🎯 今日のミッション
</div>

<div class="info-body">

<div class="mission-box">
<div class="mission-title">
5問解く
</div>
<div class="mission-progress">
<div class="mission-fill" style="width:0%"></div>
</div>
</div>

<div class="mission-box">
<div class="mission-title">
3問正解
</div>
<div class="mission-progress">
<div class="mission-fill" style="width:0%"></div>
</div>
</div>

<div class="mission-box">
<div class="mission-title">
自信度入力
</div>
<div class="mission-progress">
<div class="mission-fill" style="width:0%"></div>
</div>
</div>

<div class="mission-box">
<div class="mission-title">
復習する
</div>
<div class="mission-progress">
<div class="mission-fill" style="width:0%"></div>
</div>
</div>

</div>

</div>

</div>
""",
        unsafe_allow_html=True
    )

    # -------------------------
    # おすすめ
    # -------------------------

    st.markdown(
        """
<div class="recommend">

<div class="recommend-icon">
💡
</div>

<div>

<div class="recommend-title">
今日のおすすめ
</div>

<div class="recommend-text">
答えを見る前に、自分の自信度を考えてみよう。
</div>

</div>

</div>
""",
        unsafe_allow_html=True
    )

    # -------------------------
    # 国試ロード
    # -------------------------

    st.markdown(
        """
<div class="road-card">

<div class="road-title">
📖 国試ロード
</div>

<div class="road-sub">
ここから合格までの道を進もう
</div>

<div class="road-line">

<div class="road-node">
<div class="node done">1</div>
<div class="node-text">基礎</div>
</div>

<div class="connector"></div>

<div class="road-node">
<div class="node">2</div>
<div class="node-text">X線</div>
</div>

<div class="connector"></div>

<div class="road-node">
<div class="node">3</div>
<div class="node-text">CT</div>
</div>

<div class="connector"></div>

<div class="road-node">
<div class="node">4</div>
<div class="node-text">MRI</div>
</div>

</div>

</div>
""",
        unsafe_allow_html=True
    )

    st.divider()
    if st.button("➕ スライドから問題を追加する", use_container_width=True, key="home_add_slide_questions"):
        go("add_questions")
    if st.session_state.get("custom_questions"):
        if st.button("📝 スライド問題を解く", use_container_width=True, key="home_solve_slide_questions"):
            qs = list(st.session_state.custom_questions)
            random.shuffle(qs)
            st.session_state.quiz_questions = qs[:5]
            st.session_state.quiz_mode = "normal"
            reset_quiz_state()
            go("quiz")
    if st.button("📊 問題別正答率・難易度分析", use_container_width=True):
        go("accuracy")
    bottom_navigation("home")


def show_question_accuracy():
    """自分の回答履歴から問題ごとの正答率を表示する。"""
    st.markdown("## 📊 問題別正答率・難易度分析")
    st.caption("自分が回答した問題について、回答回数・正解数・正答率を確認できます。")

    records = st.session_state.get("review_records", {})
    rows = []
    for question_key, record in records.items():
        q = record.get("q", {})
        attempts = int(record.get("attempts", 0) or 0)
        wrong_count = int(record.get("wrong_count", 0) or 0)
        if attempts <= 0 or not q:
            continue
        correct_count = max(0, attempts - wrong_count)
        accuracy = round(correct_count / attempts * 100, 1)
        rows.append({
            "問題": str(question_key),
            "分野": q.get("field", "未分類"),
            "問題文": q.get("question", ""),
            "回答回数": attempts,
            "正解数": correct_count,
            "不正解数": wrong_count,
            "正答率（%）": accuracy,
        })

    if not rows:
        st.info("まだ回答履歴がありません。問題を解くと、ここに問題ごとの正答率が表示されます。")
    else:
        rows.sort(key=lambda row: (row["正答率（%）"], -row["回答回数"]))
        total_attempts = sum(row["回答回数"] for row in rows)
        total_correct = sum(row["正解数"] for row in rows)
        overall_accuracy = round(total_correct / total_attempts * 100, 1) if total_attempts else 0
        c1, c2, c3 = st.columns(3)
        c1.metric("回答した問題数", f"{len(rows)}問")
        c2.metric("総回答数", f"{total_attempts}回")
        c3.metric("全体正答率", f"{overall_accuracy}%")

        weak_rows = [row for row in rows if row["正答率（%）"] < 60]
        if weak_rows:
            st.warning(f"正答率60%未満の問題が{len(weak_rows)}問あります。優先して復習しましょう。")

        fields = sorted({row["分野"] for row in rows})
        selected_field = st.selectbox("分野で絞り込む", ["すべて"] + fields, key="question_accuracy_field")
        filtered = rows if selected_field == "すべて" else [row for row in rows if row["分野"] == selected_field]
        st.dataframe(filtered, use_container_width=True, hide_index=True)
        st.caption("正答率の低い問題から表示しています。回答回数が少ない問題は、正答率が安定していない場合があります。")

    if st.button("🏠 ホームに戻る", use_container_width=True):
        go("home")
    bottom_navigation("accuracy")


# =========================================================
# 学習画面
# =========================================================

def show_quiz():

    if not st.session_state.quiz_questions:

        st.session_state.quiz_questions = random.sample(
            get_all_questions(),
            min(5, len(get_all_questions()))
        )

    q = st.session_state.quiz_questions[
        st.session_state.quiz_index
    ]

    # -------------------------
    # タイトル
    # -------------------------

    st.markdown(
        f"""
<div class="page-box">

<div class="page-title">
{"🔁 復習モード" if st.session_state.quiz_mode == "review" else "📚 核医学 国試演習"}
</div>

<div class="page-subtitle">
第 {st.session_state.quiz_index + 1} 問 / {len(st.session_state.quiz_questions)}問
・ {q["field"]}
</div>

</div>
""",
        unsafe_allow_html=True
    )

    # -------------------------
    # 問題
    # -------------------------

    st.markdown(
        f"""
<div class="quiz-question">

<div class="quiz-question-label">
QUESTION
</div>

<div class="quiz-question-text">
{q["question"]}
</div>

</div>
""",
        unsafe_allow_html=True
    )

    # -------------------------
    # 選択肢
    # -------------------------

    selected_choice = st.radio(
        "選択肢",
        q["choices"],
        index=None,
        key=f"choice_{st.session_state.quiz_index}",
        label_visibility="collapsed",
        disabled=st.session_state.answer_revealed,
    )

    # -------------------------
    # 自信度
    # -------------------------

    st.markdown(
        """
<div class="confidence-box">

<div class="confidence-title">
💭 答えを見る前に、自信度を選択
</div>

</div>
""",
        unsafe_allow_html=True
    )

    confidence = st.selectbox(
        "自信度",
        [
            "選択してください",
            "自信なし",
            "やや自信なし",
            "どちらでもない",
            "やや自信あり",
            "自信あり",
        ],
        key=f"confidence_{st.session_state.quiz_index}",
        disabled=st.session_state.answer_revealed,
        label_visibility="collapsed",
    )

    # =====================================================
    # 答えを見る
    # =====================================================

    if not st.session_state.answer_revealed:

        can_reveal = (
            selected_choice is not None
            and confidence != "選択してください"
        )

        if can_reveal:

            if st.button(
                "🔓　答えを見る",
                key=f"reveal_{st.session_state.quiz_index}",
                use_container_width=True,
            ):

                selected_index = q["choices"].index(
                    selected_choice
                )

                is_correct = (
                    selected_index == q["answer"]
                )

                st.session_state.selected_answer = (
                    selected_index
                )

                st.session_state.confidence = (
                    confidence
                )

                st.session_state.last_correct = (
                    is_correct
                )

                st.session_state.answer_revealed = True

                # 復習記録と次回出題日を更新する（間隔反復）。
                question_key = q["question"]
                previous = st.session_state.review_records.get(question_key, {})
                attempts = previous.get("attempts", 0) + 1
                wrong_count = previous.get("wrong_count", 0) + (0 if is_correct else 1)
                correct_streak = int(previous.get("correct_streak", 0))

                if is_correct:
                    correct_streak += 1
                    # 2週間の定期テスト向け：正解回数に応じて2→3→4→7日と間隔を延ばす。
                    intervals = [2, 3, 4, 7]
                    interval_days = intervals[min(correct_streak - 1, len(intervals) - 1)]
                    # 自信度が低い正解は翌日。苦手問題は次の学習でも優先出題する。
                    if confidence in ("自信なし", "やや自信なし"):
                        interval_days = 1
                    next_review = datetime.now() + timedelta(days=interval_days)
                else:
                    # 不正解は復習候補として次の学習時に優先出題する。
                    correct_streak = 0
                    next_review = datetime.now()

                st.session_state.review_records[question_key] = {
                    "q": dict(q),
                    "last_correct": is_correct,
                    "confidence": confidence,
                    "attempts": attempts,
                    "wrong_count": wrong_count,
                    "correct_streak": correct_streak,
                    "next_review": next_review.isoformat(timespec="seconds"),
                    "interval_days": interval_days if is_correct else 0,
                }

                st.session_state.total_answered += 1

                # 国試ロード：初めて回答した問題を進捗に反映
                completed = st.session_state.road_completed_questions
                if question_key not in completed:
                    completed.append(question_key)

                if is_correct:

                    st.session_state.score += 1

                    st.session_state.total_correct += 1

                    add_xp(20)

                    st.session_state.coins += 10

                else:

                    add_xp(5)

                # 回答履歴と更新後の進捗を保存
                send_result(
                    q=q,
                    selected_index=selected_index,
                    is_correct=is_correct,
                    confidence=confidence,
                )
                save_user_progress()

                st.rerun()

        else:

            st.button(
                "🔒　選択肢と自信度を選ぶと答えが見られます",
                disabled=True,
                use_container_width=True,
            )

    # =====================================================
    # 答え表示
    # =====================================================

    else:

        if st.session_state.last_correct:

            st.success(
                "⭕ 正解！ +20 XP"
            )

        else:

            st.error(
                "❌ 不正解"
            )

        # 次回の復習予定は内部で管理し、画面には表示しない。

        st.markdown(
            f"""
<div class="info-card">

<div style="
font-size:8px;
color:#91a5b8;
">
正解
</div>

<div style="
font-size:15px;
font-weight:900;
margin-top:4px;
">
{q["choices"][q["answer"]]}
</div>

<div style="
font-size:8px;
color:#91a5b8;
margin-top:10px;
">
あなたの自信度
</div>

<div style="
font-size:11px;
font-weight:900;
color:#c8c0ff;
margin-top:3px;
">
{st.session_state.confidence}
</div>

<div style="
font-size:8px;
color:#91a5b8;
margin-top:10px;
">
解説
</div>

<div style="
font-size:10px;
line-height:1.6;
margin-top:3px;
">
{q["explanation"]}
</div>

</div>
""",
            unsafe_allow_html=True
        )

        if q.get("custom") and q.get("source_id"):
            show_source_slide(q, f"quiz_{st.session_state.quiz_index}")

        # -------------------------
        # 次の問題
        # -------------------------

        if st.session_state.quiz_index < len(st.session_state.quiz_questions) - 1:

            if st.button(
                "次の問題　▶",
                key=f"next_{st.session_state.quiz_index}",
                use_container_width=True,
            ):

                st.session_state.quiz_index += 1

                st.session_state.selected_answer = None
                st.session_state.confidence = None
                st.session_state.answer_revealed = False
                st.session_state.last_correct = None

                st.rerun()

        else:

            if st.button(
                "結果を見る　🏁",
                key="finish_quiz",
                use_container_width=True,
            ):

                st.session_state.last_score = st.session_state.score
                st.session_state.last_total = len(st.session_state.quiz_questions)

                go("result")

    # -------------------------
    # ホーム
    # -------------------------

    if st.button(
        "🏠 ホームへ",
        key="quiz_home",
        use_container_width=True,
    ):

        go("home")


# =========================================================
# 結果
# =========================================================

def show_result():

    total = max(1, st.session_state.last_total)
    rate = round(st.session_state.last_score / total * 100)

    st.markdown(
        f"""
<div class="result-box">

<div class="page-title">
🏁 学習結果
</div>

<div class="page-subtitle">
今回の{total}問
</div>

<div class="result-percent">
{rate}%
</div>

<div class="result-score">
{st.session_state.last_score} / {total} 問正解
</div>

</div>
""",
        unsafe_allow_html=True
    )

    if st.button(
        "📚 もう一度学習",
        use_container_width=True,
    ):

        start_quiz()

    if st.button(
        "🔁 復習する",
        use_container_width=True,
    ):
        go("review")

    if st.button(
        "🏠 ホームへ",
        use_container_width=True,
    ):
        go("home")


# =========================================================
# 国試ロード
# =========================================================

def show_road():

    st.markdown(
        """
<div class="page-box">

<div class="page-title">
📖 国試ロード
</div>

<div class="page-subtitle">
ステージを進めて合格を目指そう
</div>

</div>
""",
        unsafe_allow_html=True
    )

    stages = [
        ("1", "基礎知識", "基礎知識"),
        ("2", "一般撮影", "一般撮影"),
        ("3", "CT", "CT"),
        ("4", "MRI", "MRI"),
        ("5", "核医学", "核医学"),
        ("6", "放射線治療", "放射線治療"),
    ]

    completed_questions = set(st.session_state.road_completed_questions)

    for no, name, field_name in stages:
        field_questions = [q for q in get_all_questions() if q.get("field") == field_name]
        total = len(field_questions)
        completed_count = sum(1 for q in field_questions if q.get("question") in completed_questions)
        progress = int(completed_count / total * 100) if total else 0
        progress_label = f"{progress}%" if total else "準備中"
        detail_label = f"{completed_count} / {total} 問回答済み" if total else "問題を追加すると進捗が表示されます"

        st.markdown(
            f"""
<div class="info-card">

<div style="
display:flex;
justify-content:space-between;
font-size:10px;
font-weight:900;
">

<span>
STAGE {no}　{name}
</span>

<span>
{progress_label}
</span>

</div>

<div style="
height:6px;
margin-top:6px;
background:#1b3046;
border-radius:10px;
overflow:hidden;
">

<div style="
height:100%;
width:{progress}%;
background:linear-gradient(90deg, #b9b0ff, #8d83d8);
border-radius:10px;
">
</div>

</div>
<div style="font-size:10px;color:#9aaec3;margin-top:7px;">
{detail_label}
</div>

</div>
""",
            unsafe_allow_html=True
        )

    bottom_navigation("road")


# =========================================================
# 分野
# =========================================================

def show_fields():

    st.markdown(
        """
<div class="page-box">

<div class="page-title">
📁 分野
</div>

<div class="page-subtitle">
分野別の学習状況
</div>

</div>
""",
        unsafe_allow_html=True
    )

    # 分野一覧は残し、今回は核医学のみ学習できるようにする
    fields = [
        ("一般撮影", False),
        ("CT", False),
        ("MRI", False),
        ("放射線物理", False),
        ("核医学", True),
        ("放射線治療", False),
        ("超音波", False),
        ("放射線防護", False),
    ]

    for field, available in fields:
        st.markdown(
            f"""
<div class="info-card">
<div style="
display:flex;
justify-content:space-between;
align-items:center;
font-size:10px;
font-weight:900;
">
<span>{field}</span>
<span style="color:{'#8bd7ff' if available else '#8194a7'};font-size:8px;">
{'学習可能' if available else '準備中'}
</span>
</div>
</div>
""",
            unsafe_allow_html=True
        )

        if available:
            if st.button(
                "📚 核医学の問題を解く",
                key="start_nuclear_quiz",
                use_container_width=True,
            ):
                start_quiz()
        else:
            st.caption(f"{field}の問題は今後追加予定です。")

    bottom_navigation("fields")


# =========================================================
# ランキング
# =========================================================

def show_ranking():
    st.markdown(
        """
<div class="page-box">
<div class="page-title">🏆 学習ランキング</div>
<div class="page-subtitle">全ユーザーの学習状況（XP順）</div>
</div>
""",
        unsafe_allow_html=True,
    )

    if st.button("🔄 ランキングを更新", use_container_width=True):
        st.rerun()

    leaderboard = get_leaderboard()
    if not leaderboard:
        st.info("ランキングを取得できませんでした。Apps Scriptのコード・デプロイ・API_URLを確認してください。")
    else:
        for index, item in enumerate(leaderboard, start=1):
            name = str(item.get("user_name", "ユーザー"))
            xp = int(item.get("xp", 0) or 0)
            level = int(item.get("level", 0) or 0)
            answered = int(item.get("total_answered", 0) or 0)
            correct = int(item.get("total_correct", 0) or 0)
            accuracy = round(correct / answered * 100) if answered else 0
            medal = "🥇" if index == 1 else "🥈" if index == 2 else "🥉" if index == 3 else f"{index}位"
            st.markdown(
                f"""
<div class="info-card" style="display:flex;align-items:center;gap:10px;">
  <div style="font-size:18px;font-weight:900;min-width:38px;">{medal}</div>
  <div style="flex:1;">
    <div style="font-size:11px;font-weight:900;">{name}</div>
    <div style="font-size:7px;color:#8fa4b8;margin-top:4px;">Lv.{level} ・ 回答 {answered}問 ・ 正答率 {accuracy}%</div>
  </div>
  <div style="font-size:13px;font-weight:900;color:#c8c0ff;">{xp} XP</div>
</div>
""",
                unsafe_allow_html=True,
            )

    if st.button("👤 マイページへ", use_container_width=True):
        go("mypage")
    bottom_navigation("ranking")


# =========================================================
# マイページ
# =========================================================

def show_mypage():

    if st.session_state.total_answered > 0:

        accuracy = round(
            st.session_state.total_correct
            / st.session_state.total_answered
            * 100
        )

    else:

        accuracy = 0

    st.markdown(
        f"""
<div class="page-box">

<div class="page-title">
👤 マイページ
</div>

<div class="page-subtitle">
プロフィールと学習状況
</div>


<div class="info-card">

<div style="
font-size:12px;
font-weight:900;
">
{st.session_state.user_name}
</div>

<div style="
font-size:7px;
color:#8fa4b8;
margin-top:4px;
">
{st.session_state.school_year}
・
受験予定 {st.session_state.exam_year}
</div>

</div>


<div style="
display:grid;
grid-template-columns:1fr 1fr;
gap:6px;
">

<div class="info-card"
style="
margin-top:6px;
text-align:center;
">

<div style="
font-size:7px;
color:#8fa4b8;
">
Lv.
</div>

<div style="
font-size:25px;
font-weight:900;
">
{st.session_state.level}
</div>

</div>


<div class="info-card"
style="
margin-top:6px;
text-align:center;
">

<div style="
font-size:7px;
color:#8fa4b8;
">
正答率
</div>

<div style="
font-size:25px;
font-weight:900;
">
{accuracy}%
</div>

</div>

</div>


<div class="info-card">

<div style="
font-size:10px;
font-weight:900;
">
📊 学習データ
</div>

<div style="
font-size:7px;
color:#8fa4b8;
margin-top:7px;
">
回答数　{st.session_state.total_answered}問
</div>

<div style="
font-size:7px;
color:#8fa4b8;
margin-top:4px;
">
正解数　{st.session_state.total_correct}問
</div>

<div style="
font-size:7px;
color:#8fa4b8;
margin-top:4px;
">
XP　{st.session_state.xp} / 100
</div>

<div style="
font-size:7px;
color:#8fa4b8;
margin-top:4px;
">
🪙 コイン　{st.session_state.coins:,}
</div>

</div>

</div>
""",
        unsafe_allow_html=True
    )

    if st.button("🏆 全ユーザーのランキングを見る", use_container_width=True):
        go("ranking")

    bottom_navigation("mypage")


# =========================================================
# 実行
# =========================================================

if not st.session_state.profile_set:

    show_setup()

else:

    if st.session_state.page == "home":
        show_home()

    elif st.session_state.page == "quiz":
        show_quiz()

    elif st.session_state.page == "result":
        show_result()

    elif st.session_state.page == "review":
        show_review()

    elif st.session_state.page == "road":
        show_road()

    elif st.session_state.page == "fields":
        show_fields()

    elif st.session_state.page == "mypage":
        show_mypage()

    elif st.session_state.page == "ranking":
        show_ranking()

    elif st.session_state.page == "accuracy":
        show_question_accuracy()

    elif st.session_state.page == "add_questions":
        show_add_questions()

    else:
        show_home()
