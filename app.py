import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import random

st.set_page_config(page_title="생활 패턴 대시보드", layout="wide")

# ─── 컨디션 텍스트 → 숫자 변환 ───────────────────────────────────────────────

CONDITION_SCORE = {"매우피곤": 1, "피곤": 3, "보통": 5, "좋음": 7, "매우좋음": 9}


def condition_to_score(series: pd.Series) -> pd.Series:
    if pd.api.types.is_numeric_dtype(series):
        return series
    return series.map(CONDITION_SCORE).fillna(5)


# ─── 더미 데이터 생성 (실제 엑셀 컬럼명 기준) ───────────────────────────────

@st.cache_data
def generate_dummy_data() -> pd.DataFrame:
    random.seed(42)
    np.random.seed(42)

    dates = pd.date_range(start="2026-04-01", end="2026-05-31", freq="D")
    categories = ["식비", "교통비", "의료비", "쇼핑", "여가", "공과금", "통신비"]
    condition_labels = list(CONDITION_SCORE.keys())

    records = []
    base_weight = 68.0
    for date in dates:
        income = 3_500_000 if date.day == 1 else (500_000 if date.day == 15 else 0)

        has_expense = random.random() < 0.75
        expense = random.randint(5_000, 80_000) if has_expense else 0
        category = random.choice(categories) if has_expense else None
        memo = f"{category} 구매" if has_expense else ""

        exercise = random.random() < 0.6
        exercise_time = random.randint(20, 90) if exercise else 0
        exercise_yn = "O" if exercise else "X"

        base_weight += random.uniform(-0.2, 0.2)
        weight = round(max(63.0, min(73.0, base_weight)), 1)

        bedtime_hour = random.choice([22, 22, 23, 23, 0, 1])
        bedtime = f"{bedtime_hour:02d}:{random.choice(['00', '15', '30', '45'])}"

        sleep_time = round(random.uniform(4.5, 8.5), 1)
        water_l = round(random.uniform(0.7, 3.5), 1)
        steps = random.randint(2_000, 14_000)

        # 수면·운동에 따라 컨디션 편향
        score = (sleep_time / 8.0) * 5 + (exercise_time / 60.0) * 3
        if score > 7:
            condition = random.choices(condition_labels, weights=[0.0, 0.05, 0.2, 0.45, 0.3])[0]
        elif score > 5:
            condition = random.choices(condition_labels, weights=[0.05, 0.15, 0.4, 0.3, 0.1])[0]
        else:
            condition = random.choices(condition_labels, weights=[0.2, 0.35, 0.3, 0.1, 0.05])[0]

        records.append({
            "날짜": date,
            "입금내역": income,
            "출금내역": expense,
            "가계부": memo,
            "카테고리": category,
            "운동여부": exercise_yn,
            "운동시간(분)": exercise_time,
            "몸무게(kg)": weight,
            "취침시간": bedtime,
            "음수량(L)": water_l,
            "컨디션": condition,
            "수면시간(시간)": sleep_time,
            "걸음수": steps,
        })

    return pd.DataFrame(records)


def load_excel(file) -> pd.DataFrame:
    df = pd.read_excel(file)
    if "날짜" in df.columns:
        df["날짜"] = pd.to_datetime(df["날짜"])
    return df


def prepare(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    # 운동여부 → bool
    if "운동여부" in df.columns:
        df["_운동여부_bool"] = df["운동여부"].map({"O": True, "X": False}).fillna(False)
    # 컨디션 → 숫자
    if "컨디션" in df.columns:
        df["_컨디션_점수"] = condition_to_score(df["컨디션"])
    return df


# ─── 데이터 로드 ─────────────────────────────────────────────────────────────

st.title("생활 패턴 대시보드")

with st.sidebar:
    st.header("엑셀 파일 업로드")
    file1 = st.file_uploader("첫 번째 파일 (예: 4월)", type=["xlsx", "xls"], key="f1")
    file2 = st.file_uploader("두 번째 파일 (예: 5월)", type=["xlsx", "xls"], key="f2")
    st.caption("파일을 업로드하지 않으면 내장 더미 데이터를 사용합니다.")

if file1 or file2:
    frames = []
    if file1:
        frames.append(load_excel(file1))
    if file2:
        frames.append(load_excel(file2))
    df_all = pd.concat(frames, ignore_index=True)
    st.sidebar.success(f"업로드 완료 — 총 {len(df_all):,}행")
else:
    df_all = generate_dummy_data()
    st.sidebar.info("더미 데이터 사용 중 (2026-04-01 ~ 2026-05-31)")

df_all = prepare(df_all.sort_values("날짜").reset_index(drop=True))

# ─── 월 필터 ─────────────────────────────────────────────────────────────────

months = sorted(df_all["날짜"].dt.to_period("M").unique())
month_labels = [str(m) for m in months]

with st.sidebar:
    st.divider()
    selected_label = st.selectbox("월 선택", ["전체"] + month_labels)

if selected_label == "전체":
    df = df_all.copy()
else:
    df = df_all[df_all["날짜"].dt.to_period("M").astype(str) == selected_label].copy()

# ─── KPI ─────────────────────────────────────────────────────────────────────

total_income   = int(df["입금내역"].sum())
total_expense  = int(df["출금내역"].sum())
savings        = total_income - total_expense
avg_weight     = round(df["몸무게(kg)"].mean(), 1)
exercise_rate  = round(df["_운동여부_bool"].mean() * 100, 1)
avg_sleep      = round(df["수면시간(시간)"].mean(), 1)
avg_water      = round(df["음수량(L)"].mean(), 1)
avg_condition  = round(df["_컨디션_점수"].mean(), 1)

kpi1 = st.columns(4)
for col, (label, value, icon) in zip(kpi1, [
    ("총 입금액",   f"₩{total_income:,}",  "💰"),
    ("총 지출액",   f"₩{total_expense:,}", "💸"),
    ("월 저축액",   f"₩{savings:,}",       "🏦"),
    ("평균 몸무게", f"{avg_weight} kg",    "⚖️"),
]):
    col.metric(f"{icon} {label}", value)

kpi2 = st.columns(4)
for col, (label, value, icon) in zip(kpi2, [
    ("운동 수행률",    f"{exercise_rate} %",   "🏃"),
    ("평균 수면시간",  f"{avg_sleep} h",        "😴"),
    ("평균 음수량",    f"{avg_water} L",        "💧"),
    ("평균 컨디션",    f"{avg_condition} / 9",  "✨"),
]):
    col.metric(f"{icon} {label}", value)

st.divider()

# ─── 카테고리별 지출 ─────────────────────────────────────────────────────────

left, right = st.columns([1, 1])

with left:
    st.subheader("카테고리별 지출 금액")
    cat_df = (
        df[df["카테고리"].notna()]
        .groupby("카테고리")["출금내역"]
        .agg(건수="count", 총지출액="sum")
        .sort_values("총지출액", ascending=False)
        .reset_index()
    )
    cat_df["총지출액"] = cat_df["총지출액"].apply(lambda x: f"₩{x:,}")
    st.dataframe(cat_df.rename(columns={"카테고리": "카테고리", "총지출액": "총 지출액"}),
                 width="stretch", hide_index=True)

with right:
    st.subheader("카테고리별 지출 비중")
    cat_pie = (
        df[df["카테고리"].notna()]
        .groupby("카테고리")["출금내역"].sum().reset_index()
    )
    fig_pie = px.pie(
        cat_pie, names="카테고리", values="출금내역", hole=0.4,
        color_discrete_sequence=px.colors.qualitative.Pastel,
    )
    fig_pie.update_traces(textposition="inside", textinfo="percent+label")
    fig_pie.update_layout(showlegend=False, margin=dict(t=10, b=10))
    st.plotly_chart(fig_pie, width="stretch")

st.divider()

# ─── 운동 시간 일별 ──────────────────────────────────────────────────────────

st.subheader("운동 시간 일별")
fig_exercise = px.bar(
    df, x="날짜", y="운동시간(분)",
    color="운동여부",
    color_discrete_map={"O": "#4CAF50", "X": "#E0E0E0"},
    labels={"운동시간(분)": "운동 시간 (분)", "날짜": "날짜", "운동여부": "운동 여부"},
)
fig_exercise.update_layout(
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    margin=dict(t=30, b=10),
    xaxis_tickformat="%m/%d",
)
st.plotly_chart(fig_exercise, width="stretch")

st.divider()

# ─── 수면시간·운동시간에 따른 컨디션 ─────────────────────────────────────────

st.subheader("수면시간 · 운동시간에 따른 컨디션")

COND_ORDER = ["매우피곤", "피곤", "보통", "좋음", "매우좋음"]
COND_COLORS = {
    "매우피곤": "#d73027",
    "피곤":    "#fc8d59",
    "보통":    "#fee08b",
    "좋음":    "#91cf60",
    "매우좋음": "#1a9850",
}

tab1, tab2 = st.tabs(["수면시간 vs 컨디션", "운동시간 vs 컨디션"])

with tab1:
    sleep_agg = (
        df.groupby("컨디션")["수면시간(시간)"]
        .agg(평균수면=("mean"), 일수=("count"))
        .reindex(COND_ORDER).dropna().reset_index()
    )
    sleep_agg["평균수면"] = sleep_agg["평균수면"].round(1)
    fig_s = px.bar(
        sleep_agg, x="컨디션", y="평균수면",
        color="컨디션", color_discrete_map=COND_COLORS,
        text="평균수면",
        category_orders={"컨디션": COND_ORDER},
        labels={"평균수면": "평균 수면시간 (h)", "컨디션": "컨디션"},
    )
    fig_s.update_traces(texttemplate="%{text}h", textposition="outside")
    fig_s.update_layout(showlegend=False, margin=dict(t=30, b=10), yaxis_title="평균 수면시간 (h)")
    # 건수 주석
    for _, row in sleep_agg.iterrows():
        fig_s.add_annotation(
            x=row["컨디션"], y=0,
            text=f"({int(row['일수'])}일)",
            showarrow=False, yshift=-20, font=dict(size=11, color="gray"),
        )
    st.plotly_chart(fig_s, width="stretch")
    st.caption("각 컨디션 상태로 기록된 날의 평균 수면시간 · 괄호 안은 해당 일수")

with tab2:
    ex_agg = (
        df.groupby("컨디션")["운동시간(분)"]
        .agg(평균운동=("mean"), 일수=("count"))
        .reindex(COND_ORDER).dropna().reset_index()
    )
    ex_agg["평균운동"] = ex_agg["평균운동"].round(1)
    fig_e = px.bar(
        ex_agg, x="컨디션", y="평균운동",
        color="컨디션", color_discrete_map=COND_COLORS,
        text="평균운동",
        category_orders={"컨디션": COND_ORDER},
        labels={"평균운동": "평균 운동시간 (분)", "컨디션": "컨디션"},
    )
    fig_e.update_traces(texttemplate="%{text}분", textposition="outside")
    fig_e.update_layout(showlegend=False, margin=dict(t=30, b=10), yaxis_title="평균 운동시간 (분)")
    for _, row in ex_agg.iterrows():
        fig_e.add_annotation(
            x=row["컨디션"], y=0,
            text=f"({int(row['일수'])}일)",
            showarrow=False, yshift=-20, font=dict(size=11, color="gray"),
        )
    st.plotly_chart(fig_e, width="stretch")
    st.caption("각 컨디션 상태로 기록된 날의 평균 운동시간 · 괄호 안은 해당 일수")

# ─── 원본 데이터 ─────────────────────────────────────────────────────────────

with st.expander("원본 데이터 보기"):
    show_cols = [c for c in df.columns if not c.startswith("_")]
    disp = df[show_cols].copy()
    disp["날짜"] = disp["날짜"].dt.strftime("%Y-%m-%d")
    st.dataframe(disp, width="stretch", hide_index=True)
