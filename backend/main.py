import re
import requests
import pandas as pd
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="산지쌀값 분석 API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# =========================
# KOSIS 설정
# =========================
BASE_URL = "https://kosis.kr/openapi/Param/statisticsParameterData.do"
API_KEY = "MGNlMjg3ZDg1OGY1MWY5N2NiOTdiMWQzOGNhNGY0YTA="
ORG_ID = "101"
TBL_ID = "DT_1EI10122"

PRICE_ITM_ID = "T10"
MULTIPLY_TO_80KG = 4
PROCESSING_FEE = 8258
RATE = 0.5 * 0.72

PARAMS = {
    "method": "getList",
    "apiKey": API_KEY,
    "orgId": ORG_ID,
    "tblId": TBL_ID,
    "prdSe": "M",
    "startPrdDe": "202001",
    "endPrdDe": "202512",
    "objL1": "ALL",
    "itmId": "T10 T20 T30 T40",
    "format": "json",
    "jsonVD": "Y",
}


def won_str(x):
    if x is None or (isinstance(x, float) and pd.isna(x)):
        return ""
    return f"{int(round(float(x))):,}원"


def signed_won_str(x):
    if x is None or (isinstance(x, float) and pd.isna(x)):
        return ""
    x = float(x)
    sign = "+" if x > 0 else ""
    return f"{sign}{int(round(x)):,}원"


def pct_str(x):
    if x is None or (isinstance(x, float) and pd.isna(x)):
        return ""
    return f"{float(x):.2f}%"


def diff_and_pct(new, base):
    if new is None or base is None or base == 0:
        return None, None
    d = new - base
    p = d / base * 100
    return d, p


def parse_day_from_c1nm(c1_nm):
    if c1_nm is None:
        return None
    m = re.search(r"(\d+)", str(c1_nm))
    if not m:
        return None
    d = int(m.group(1))
    return d if 1 <= d <= 31 else None


def latest_marker_for_year(harvest_df, year):
    sub = harvest_df[harvest_df["YEAR"] == year].copy()
    if sub.empty:
        return None
    latest_month = sub["PRD_DE"].max()
    sub_m = sub[sub["PRD_DE"] == latest_month].copy()
    if sub_m.empty:
        return latest_month.strftime("%Y-%m")
    sub_m["DAY_INT"] = sub_m["C1_NM"].apply(parse_day_from_c1nm)
    if sub_m["DAY_INT"].dropna().empty:
        return latest_month.strftime("%Y-%m")
    day = int(sub_m["DAY_INT"].max())
    return f"{latest_month.strftime('%Y-%m')}-{day:02d}"


@app.get("/")
def root():
    return {"status": "ok", "message": "산지쌀값 분석 API 정상 작동 중"}


@app.get("/analyze")
def analyze():
    # KOSIS 데이터 수집
    r = requests.get(BASE_URL, params=PARAMS, timeout=30)
    r.raise_for_status()
    data = r.json()

    if not isinstance(data, list) or len(data) == 0:
        return {"error": "API 응답이 비어있습니다."}

    df = pd.DataFrame(data)
    df["DT"] = pd.to_numeric(df["DT"], errors="coerce")
    df["PRD_DE"] = pd.to_datetime(df["PRD_DE"], format="%Y%m")
    df["YEAR"] = df["PRD_DE"].dt.year
    df["MONTH"] = df["PRD_DE"].dt.month

    price_df = df[df["ITM_ID"] == PRICE_ITM_ID].copy()
    harvest = price_df[price_df["MONTH"].between(10, 12)].copy()
    harvest["PRICE_80KG"] = harvest["DT"] * MULTIPLY_TO_80KG

    yearly = (
        harvest.groupby("YEAR", as_index=False)
        .agg(
            harvest_price_80kg=("PRICE_80KG", "mean"),
            n_obs=("PRICE_80KG", "count"),
        )
        .sort_values("YEAR")
        .reset_index(drop=True)
    )

    yearly["public_stock_price_40kg"] = (
        yearly["harvest_price_80kg"] - PROCESSING_FEE
    ) * RATE

    yearly["harvest_price_80kg"] = yearly["harvest_price_80kg"].round(0)
    yearly["public_stock_price_40kg"] = yearly["public_stock_price_40kg"].round(0)

    def make_note(row):
        n = int(row["n_obs"])
        if n == 9:
            return ""
        y = int(row["YEAR"])
        latest = latest_marker_for_year(harvest, y)
        if not latest:
            return f"관측 {n}회 기준"
        return f"관측 {n}회 기준 / 최신 {latest}"

    yearly["note"] = yearly.apply(make_note, axis=1)

    # 연도별 결과 리스트
    yearly_result = []
    for _, row in yearly.iterrows():
        yearly_result.append({
            "year": int(row["YEAR"]),
            "harvest_price_80kg": won_str(row["harvest_price_80kg"]),
            "public_stock_price_40kg": won_str(row["public_stock_price_40kg"]),
            "note": row["note"],
        })

    # 비교 계산
    base_5y = yearly[(yearly["YEAR"] >= 2020) & (yearly["YEAR"] <= 2024)]["public_stock_price_40kg"].dropna()
    avg_2020_2024 = float(base_5y.mean()) if len(base_5y) else None

    v2024_s = yearly.loc[yearly["YEAR"] == 2024, "public_stock_price_40kg"]
    v2025_s = yearly.loc[yearly["YEAR"] == 2025, "public_stock_price_40kg"]
    v2024 = float(v2024_s.iloc[0]) if len(v2024_s) else None
    v2025 = float(v2025_s.iloc[0]) if len(v2025_s) else None

    d1, p1 = diff_and_pct(v2025, avg_2020_2024)
    d2, p2 = diff_and_pct(v2025, v2024)

    compare_result = [
        {
            "label": "최근 5년(2020~2024) 평균 vs 2025",
            "base": won_str(avg_2020_2024),
            "current": won_str(v2025),
            "diff": signed_won_str(d1),
            "pct": pct_str(p1),
            "is_up": d1 > 0 if d1 is not None else None,
        },
        {
            "label": "2024 vs 2025",
            "base": won_str(v2024),
            "current": won_str(v2025),
            "diff": signed_won_str(d2),
            "pct": pct_str(p2),
            "is_up": d2 > 0 if d2 is not None else None,
        },
    ]

    return {
        "yearly": yearly_result,
        "compare": compare_result,
        "fetched_rows": len(df),
        "latest_year": int(yearly["YEAR"].max()) if len(yearly) else None,
    }
