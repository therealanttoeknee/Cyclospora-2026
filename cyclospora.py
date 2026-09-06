# -- Introduction


# This EDA project explains how the 2026 Cyclospora outbreak affected
# public concern, food-safety behavior, and fresh-produce prices in the United States
# ---------------------------------------------------------------------------

import streamlit as st
import pandas as pd
import plotly.express as px
import hashlib
import json
import random
import time
from pathlib import Path
from pytrends.request import TrendReq

# ---------------------------------------------------------------------------
# -- Data

#Outbreak is a .csv file I created using CDC data and the wayback machine to count
#the updates to the CDC's chart over time.
outbreak = pd.read_csv("data/outbreak.csv")

#
amc = pd.read_csv("data/amc.csv")

# ---------------------------------------------------------------------------
# -- Clean Up
# Columns that are effectively empty or irrelevant to a price analysis
cols_to_drop = [
    "item_size_comment", "condition",      # 100% missing
    "unit_sales", "storage", "quality",    # >95% missing
    "environment", "appearance",
    "grade",                               # 77% missing
    "market_tone_comments", "supply_tone_comments",   # free-text commentary, not needed for price analysis
    "demand_tone_comments", "commodity_comments", "comment",
]

amc_clean = amc.drop(columns=cols_to_drop)

daily_price_range = (
    amc_clean.groupby(["report_date" , "commodity"])
    .agg(low_price=("low_price", "min"), high_price=("high_price" , "max"), n_listings = ("low_price", "count"))).reset_index()


amc_clean["report_date"] = pd.to_datetime(amc_clean["report_date"], format="%m/%d/%Y")

state_abbrev = {
    'Alabama': 'AL', 'Alaska': 'AK', 'Arizona': 'AZ', 'Arkansas': 'AR',
    'California': 'CA', 'Colorado': 'CO', 'Connecticut': 'CT', 'Delaware': 'DE', 
    'Florida': 'FL', 'Georgia': 'GA', 'Idaho': 'ID', 'Illinois': 'IL',
    'Indiana': 'IN', 'Iowa': 'IA', 'Kansas': 'KS', 'Kentucky': 'KY',
    'Louisiana': 'LA', 'Maine': 'ME', 'Maryland': 'MD', 'Massachusetts': 'MA',
    'Michigan': 'MI', 'Minnesota': 'MN', 'Mississippi': 'MS', 'Missouri': 'MO',
    'Montana': 'MT', 'Nebraska': 'NE', 'Nevada': 'NV', 'New Hampshire': 'NH',
    'New Jersey': 'NJ', 'New Mexico': 'NM', 'New York': 'NY', 'North Carolina': 'NC',
    'North Dakota': 'ND', 'Ohio': 'OH', 'Oklahoma': 'OK', 'Oregon': 'OR',
    'Pennsylvania': 'PA', 'Rhode Island': 'RI', 'South Carolina': 'SC',
    'South Dakota': 'SD', 'Tennessee': 'TN', 'Texas': 'TX', 'Utah': 'UT',
    'Vermont': 'VT', 'Virginia': 'VA', 'Washington': 'WA', 'West Virginia': 'WV',
    'Wisconsin': 'WI', 'Wyoming': 'WY'
}

# ---------------------------------------------------------------------------

st.title("Cyclospora 2026 Outbreak EDA") 
st.write(
    "U.S. outbreaks of cyclosporiasis have repeatedly been linked to contaminated "
    "fresh produce. In 2026, a major multistate outbreak was linked to processed "
    "iceberg lettuce from central Mexico. This EDA examines how public concern, "
    "food-safety searches, and wholesale produce prices changed during the outbreak."
)
st.write("Note: The true number of people sick with cyclosporiasis is likely higher "
"than the number reported below. Some people recover without medical care and are "
"not tested for Cyclospora.")

st.header("Progression")

outbreak["State_Abbrev"] = outbreak["Location"].map(state_abbrev)

case_order = [
    "N/A",
    "1 to 10",
    "1 to 49",
    "11 to 30",
    "31 to 80",
    "50 to 199",
    "81 to 160",
    "161 to 300",
    "200 to 499",
    "301 to 500",
    "500 to 999",
    "901 to 2100",
    "1000 to 3999",
    "1000 to 4000",
    "4000 to 6999"
]


case_colors = {
    "N/A": "#E5E7EB",
    "1 to 10": "#EFF6FF",
    "1 to 49": "#DBEAFE",
    "11 to 30": "#BFDBFE",
    "31 to 80": "#93C5FD",
    "50 to 199": "#60A5FA",
    "81 to 160": "#3B82F6",
    "161 to 300": "#2583EB",
    "200 to 499": "#1D6FD1",
    "301 to 500": "#1D5EBA",
    "500 to 999": "#1E4FA3",
    "901 to 2100": "#1E428A",
    "1000 to 3999": "#1E3A78",
    "1000 to 4000": "#172F63",
    "4000 to 6999": "#0F234A"
}


selected_date = st.selectbox(
    "Select a reporting date",
    outbreak["Date"].unique()
)

outbreak_by_date = outbreak[
    outbreak["Date"] == selected_date
]


fig = px.choropleth(
    outbreak_by_date,
    locations="State_Abbrev",
    locationmode="USA-states",
    color="Number of Sick People",
    scope="usa",
    hover_name="Location",
    hover_data={
        "Number of Sick People": True,
        "State_Abbrev": False,
        "Date": False
    },
    color_discrete_map=case_colors,
    category_orders={
        "Number of Sick People": case_order
    }
)

fig.update_traces(
    marker_line_color="black",
    marker_line_width=0.5
)

st.plotly_chart(fig, use_container_width=True)

# ---------------------------------------------------------------------------
# Google Trends helper
#
# Why this is more reliable:
# 1. Each keyword group is downloaded once for both 2025 and 2026.
# 2. Successful downloads are saved locally and reused on later app runs.
# 3. Requests are spaced out and retried with backoff.
# 4. A temporary Google failure returns an empty DataFrame instead of exposing
#    a technical exception in the Streamlit UI.
# ---------------------------------------------------------------------------
TRENDS_CACHE_DIR = Path("data/google_trends_cache")
try:
    TRENDS_CACHE_DIR.mkdir(parents=True, exist_ok=True)
except OSError:
    # Some hosted environments use a read-only filesystem. The in-memory
    # Streamlit cache below still prevents repeated calls within the session.
    pass

_last_trends_request_at = 0.0


def _trends_cache_path(keywords, timeframe, geo):
    """Return a stable cache filename for one exact Trends request."""
    request_key = json.dumps(
        {
            "keywords": list(keywords),
            "timeframe": timeframe,
            "geo": geo,
        },
        sort_keys=True,
    )
    digest = hashlib.sha256(request_key.encode("utf-8")).hexdigest()[:16]
    return TRENDS_CACHE_DIR / f"trends_{digest}.csv"


def _read_trends_cache(cache_path):
    """Read a previously successful download, if one exists."""
    if not cache_path.exists():
        return pd.DataFrame()

    try:
        cached = pd.read_csv(cache_path, parse_dates=["date"])
        return cached if not cached.empty else pd.DataFrame()
    except (OSError, ValueError, pd.errors.ParserError):
        return pd.DataFrame()


def _write_trends_cache(df, cache_path):
    """Save data atomically so an interrupted write cannot corrupt the cache."""
    temporary_path = cache_path.with_suffix(".tmp")
    df.to_csv(temporary_path, index=False)
    temporary_path.replace(cache_path)


def _space_out_trends_requests(minimum_gap_seconds=2.0):
    """Avoid sending several Google Trends requests at the same instant."""
    global _last_trends_request_at

    elapsed = time.monotonic() - _last_trends_request_at
    if elapsed < minimum_gap_seconds:
        time.sleep(minimum_gap_seconds - elapsed)


@st.cache_data(ttl=6 * 60 * 60, show_spinner=False)
def _download_trends(keywords, timeframe, geo):
    """Download Trends data with a small retry/backoff policy."""
    global _last_trends_request_at

    for attempt in range(2):
        try:
            _space_out_trends_requests()

            pytrends = TrendReq(
                hl="en-US",
                tz=360,
                timeout=(10, 30),
                requests_args={
                    "headers": {
                        "User-Agent": (
                            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                            "AppleWebKit/537.36 (KHTML, like Gecko) "
                            "Chrome/131.0 Safari/537.36"
                        )
                    }
                },
            )
            pytrends.build_payload(
                kw_list=list(keywords),
                timeframe=timeframe,
                geo=geo,
            )
            downloaded = pytrends.interest_over_time()
            _last_trends_request_at = time.monotonic()

            if downloaded.empty:
                return pd.DataFrame()

            downloaded = (
                downloaded.drop(columns=["isPartial"], errors="ignore")
                .reset_index()
            )
            downloaded["date"] = pd.to_datetime(downloaded["date"])
            return downloaded

        except Exception:
            _last_trends_request_at = time.monotonic()
            if attempt == 0:
                time.sleep(5 + random.random())

    return pd.DataFrame()


def get_trends(keywords, timeframe, geo="US"):
    """Use saved Trends data first; download it only when it is not cached."""
    keywords = (keywords,) if isinstance(keywords, str) else tuple(keywords)
    cache_path = _trends_cache_path(keywords, timeframe, geo)

    cached = _read_trends_cache(cache_path)
    if not cached.empty:
        return cached

    downloaded = _download_trends(keywords, timeframe, geo)
    if not downloaded.empty:
        try:
            _write_trends_cache(downloaded, cache_path)
        except OSError:
            # Streamlit's in-memory cache still prevents repeat calls during
            # this session if the deployment filesystem is read-only.
            pass

    return downloaded


def trends_between(trends_data, start_date, end_date):
    """Return a date slice without making another Google request."""
    if trends_data.empty:
        return pd.DataFrame()

    dates = pd.to_datetime(trends_data["date"])
    return trends_data.loc[
        dates.between(pd.Timestamp(start_date), pd.Timestamp(end_date))
    ].copy()

def plot_trends(trends_data, keywords, title):
    """Plot Trends data without exposing request errors to app visitors."""
    if trends_data.empty:
        st.caption(f"No Google Trends observations are available for {title}.")
        return

    y_cols = [k for k in keywords if k in trends_data.columns]
    if not y_cols:
        st.caption(f"No Google Trends observations are available for {title}.")
        return

    fig = px.line(
        trends_data,
        x="date",
        y=y_cols,
        title=title,
        labels={"value": "Search interest", "variable": "Search term"},
    )
    st.plotly_chart(fig, use_container_width=True)


# ---------------------------------------------------------------------------
# Google Trends - Fast Food Chains
# ---------------------------------------------------------------------------
st.header("Fast Food 🍔")

st.write(
    "Search interest began to increase on July 17, the same day Taylor Farms de Mexico "
    "announced that it was removing all iceberg lettuce sourced from central Mexico "
    "from the U.S. market. Taylor Farms supplied the shredded iceberg lettuce served "
    "at the Taco Bell locations associated with the outbreak."
)

keywords_fastfood = [
    "is taco bell lettuce safe",
    "is mcdonalds lettuce safe",
    "is burger king lettuce safe",
    "is chipotle lettuce safe"
]

fastfood_all = get_trends(
    keywords_fastfood,
    "2025-06-10 2026-08-10"
)

fastfood_2026 = trends_between(fastfood_all, "2026-06-10", "2026-08-10")

plot_trends(
    fastfood_2026,
    keywords_fastfood,
    "Fast Food Chain Google Trend Interest (2026)"
)

# ---------------------------------------------------------------------------
# Google Trends - Grocery Stores (Lettuce)
# ---------------------------------------------------------------------------

st.header("Grocery Stores 🛒")
st.write(
    "Compared with fast-food-related searches, search interest in lettuce safety at "
    "grocery stores was less persistent. One possible explanation is that grocery "
    "shoppers can choose among different lettuce brands or substitute another product, "
    "while fast-food customers have less control over the source of the lettuce they "
    "are served."
)

keywords_grocery_lettuce = [
    "is trader joes lettuce safe",
    "is costco lettuce safe",
    "is walmart lettuce safe",
    "is whole foods lettuce safe"
]
trends_grocery_all = get_trends(
    keywords_grocery_lettuce,
    "2025-06-01 2026-08-20"
)
trends_grocery_2026 = trends_between(
    trends_grocery_all,
    "2026-06-01",
    "2026-08-20"
)

plot_trends(
    trends_grocery_2026,
    keywords_grocery_lettuce,
    "Grocery Store Google Trend Interest (2026)"
)

keywords_grocery_lettuce_vs = [
    "is chipotle lettuce safe",
    "is walmart lettuce safe"
]

trends_grocery = get_trends(keywords_grocery_lettuce_vs, '2026-06-01 2026-08-20')
plot_trends(trends_grocery, keywords_grocery_lettuce_vs, "Fast Food vs. Grocery Store Interest (2026)")

# --------------------------------------------------
# Google Trends - Grocery Stores (Basil and Cilantro)
# --------------------------------------------------

st.write(
    "Past Cyclospora outbreaks have also been linked to fresh herbs such as basil "
    "and cilantro. Interestingly, Google Trends showed little to no measurable search "
    "interest in whether the basil or cilantro sold by these stores was safe."
)

keywords_grocery_basil = [
    "is trader joes basil safe",
    "is costco basil safe",
    "is walmart basil safe",
    "is whole foods basil safe"
]

basil_trends = get_trends(
    keywords_grocery_basil,
    "2025-07-01 2026-08-20"
)

if basil_trends.empty:
    st.write("Google Trends did not find enough basil data.")
else:
    basil_trends_2025 = trends_between(
        basil_trends,
        "2025-07-01",
        "2025-08-20"
    )

    basil_trends_2026 = trends_between(
        basil_trends,
        "2026-07-01",
        "2026-08-20"
    )

    plot_trends(
        basil_trends_2026,
        keywords_grocery_basil,
        "Grocery Store Basil Safety Searches (2026)"
    )

# --------------------------------------------------
# Cilantro searches
# --------------------------------------------------

keywords_grocery_cilantro = [
    "is trader joes cilantro safe",
    "is costco cilantro safe",
    "is walmart cilantro safe",
    "is whole foods cilantro safe"
]

cilantro_trends = get_trends(
    keywords_grocery_cilantro,
    "2025-07-01 2026-08-20"
)

if cilantro_trends.empty:
    st.write("Google Trends did not find enough cilantro data.")
else:
    cilantro_trends_2025 = trends_between(
        cilantro_trends,
        "2025-07-01",
        "2025-08-20"
    )

    cilantro_trends_2026 = trends_between(
        cilantro_trends,
        "2026-07-01",
        "2026-08-20"
    )

    plot_trends(
        cilantro_trends_2026,
        keywords_grocery_cilantro,
        "Grocery Store Cilantro Safety Searches (2026)"
    )

# ---------------------------------------------------------------------------
# Google Trends - Home Cooking Shift
# ---------------------------------------------------------------------------

st.header("Home Cooking 🍳")
st.write(
    "Although the outbreak was linked to iceberg lettuce, search interest suggested "
    "broader concern about produce safety. Searches for 'how to wash fruit' and "
    "'how to wash vegetables' were more persistent in 2026 than during the same "
    "period in 2025, while 'how to wash lettuce' also recorded greater interest. "
    "Search interest was relatively steady early in 2026 before rising sharply in "
    "mid-July, around the time the outbreak and recall received wider attention. "
    "These patterns may indicate increased public interest in produce-cleaning "
    "guidance, although search data alone cannot establish why people searched or "
    "whether they changed their behavior."
)

keywords_homecooking = [
    "how to wash fruit",
    "how to wash vegetables",
    "how to wash lettuce"
]

trends_homecooking_all = get_trends(
    keywords_homecooking,
    "2025-01-01 2026-08-20"
)
trends_homecooking_2026 = trends_between(
    trends_homecooking_all,
    "2026-01-01",
    "2026-08-20"
)
trends_homecooking_2025 = trends_between(
    trends_homecooking_all,
    "2025-01-01",
    "2025-08-20"
)

plot_trends(
    trends_homecooking_2026,
    keywords_homecooking,
    "Home Cooking Habits (2026)"
)
plot_trends(
    trends_homecooking_2025,
    keywords_homecooking,
    "Home Cooking Habits (2025)"
)

# ---------------------------------------------------------------------------
# Produce Prices
# ---------------------------------------------------------------------------

st.header("Produce Prices")
st.write(
    "Lastly, average wholesale lettuce prices fell by 73% during July. Although "
    "the outbreak was linked to iceberg lettuce, prices for other lettuce varieties "
    "also declined. Prices for broccoli, cabbage, and carrots decreased as well, "
    "but remained higher than lettuce prices during the selected period."
)

amc["report_date"] = pd.to_datetime(amc["report_date"])

foods = ["Lettuce, Iceberg", "Lettuce, Boston", "Lettuce, Green Leaf", "Lettuce, Red Leaf", "Lettuce, Romaine", "Carrots", "Cabbage", "Broccoli"]

selected = amc[
    amc["commodity"].isin(foods)
]

high = (
    selected.groupby(
        ["report_date", "commodity"],
        as_index=False
    )["high_price"]
    .mean()
    .sort_values("report_date")
)

fig1 = px.line(high, x="report_date", y="high_price", color="commodity", title="Produce High Price (2026)")
st.plotly_chart(fig1)

fig1.update_xaxes(
    range=["2026-01-01", "2026-08-01"]
)


low = (
    selected.groupby(
        ["report_date", "commodity"],
        as_index=False
    )["low_price"]
    .mean()
    .sort_values("report_date")
)

fig2 = px.line(low, x="report_date", y="low_price", color="commodity", title="Produce Low Price (2026)")
st.plotly_chart(fig2)

fig2.update_xaxes(
    range=["2026-01-01", "2026-08-01"]
)
