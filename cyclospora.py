# -- Introduction


# This EDA project explains how the 2026 Cyclospora outbreak affected
# public concern, food-safety behavior, and fresh-produce prices in the United States
# ---------------------------------------------------------------------------

import streamlit as st
import pandas as pd
import plotly.express as px
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

st.title("Cyclospora Outbreak 2026 EDA") 
st.text(
    "Cyclospora finds its way into our lettuce and berries every summer, causing people "
    "extreme stomach pains and fatigue. How did the 2026 Cyclospora outbreak affect "
    "consumer concern and behavior around produce?"
)
st.header("2026 Progression")

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

st.write("Note: The true number of people sick with cyclosporiasis is likely higher "
"than the number reported below. Some people recover without medical care and are "
"not tested for Cyclospora.")

# ---------------------------------------------------------------------------
# Google Trends helper (cached + retries + graceful failure)
# ---------------------------------------------------------------------------
@st.cache_data(ttl=3600, show_spinner="Fetching Google Trends data...")
def get_trends(keywords, timeframe, geo='US'):
    """
    Fetch Google Trends interest-over-time for a list of keywords.
    Cached for 1 hour so Streamlit reruns don't re-hit Google and
    trigger 429 (TooManyRequestsError).
    """
    try:
        pytrends = TrendReq(hl='en-US', tz=360, retries=3, backoff_factor=1.0)
        pytrends.build_payload(keywords, timeframe=timeframe, geo=geo)
        df = pytrends.interest_over_time()
        return df.reset_index()
    except Exception as e:
        st.warning(f"Google Trends request failed for {keywords}: {e}")
        return pd.DataFrame()


def plot_trends(trends_data, keywords, title):
    """Plot trends data if available, otherwise show a friendly message."""
    if trends_data.empty:
        st.info(f"Trends data unavailable right now for '{title}' — try again later.")
        return
    # isPartial column can exist and isn't something we want plotted
    y_cols = [k for k in keywords if k in trends_data.columns]
    fig = px.line(trends_data, x="date", y=y_cols, title=title, labels={"value": "Popularity"})
    st.plotly_chart(fig)


# ---------------------------------------------------------------------------
# Google Trends - Fast Food Chains
# ---------------------------------------------------------------------------
st.header("Fast Food 🍔")
st.write("Compared to 2025, the average of these keywords were up over 5,000% compared to 2025.")

keywords_fastfood = [
    "is taco bell lettuce safe",
    "is mcdonalds lettuce safe",
    "is burger king lettuce safe",
    "is chipotle lettuce safe"
]
trends_fastfood = get_trends(keywords_fastfood, '2026-05-01 2026-08-22')
plot_trends(trends_fastfood, keywords_fastfood, "Fast Food Chain Google Trend Interest (2026)")

trends_fastfood = get_trends(keywords_fastfood, '2025-01-01 2025-12-01')
plot_trends(trends_fastfood, keywords_fastfood, "Fast Food Chain Google Trend Interest (2025)")



# ---------------------------------------------------------------------------
# Google Trends - Grocery Stores
# ---------------------------------------------------------------------------

st.header("Grocery Stores 🛒")
st.write("Similar to fast food, the average of the keywords below were up over 5,000% compared to 2025.")

keywords_grocery_lettuce = [
    "is trader joes lettuce safe",
    "is costco lettuce safe",
    "is walmart lettuce safe",
    "is whole foods lettuce safe"
]
trends_grocery = get_trends(keywords_grocery_lettuce, '2026-07-01 2026-08-20')
plot_trends(trends_grocery, keywords_grocery_lettuce, "Grocery Stores 2026")


trends_grocery = get_trends(keywords_grocery_lettuce, '2025-05-01 2025-12-31')
plot_trends(trends_grocery, keywords_grocery_lettuce, "Grocery Stores 2025")

st.write("Unlike fast food chains, however, grocery stores carry berries and berries are the other "
         "type of produce that cyclospora spoils. Interestingly, people weren't searching if berries "
         "from these stores were safe or not. ")

keywords_grocery_berries = [
    "are trader joes berries safe",
    "are costco berries safe",
    "are walmart berries safe",
    "are whole foods berries safe"
]

# Get 2025 and 2026 data together
berry_trends = get_trends(
    keywords_grocery_berries,
    "2025-07-01 2026-08-20"
)

if berry_trends.empty:
    st.write("Google Trends did not find enough data.")
else:
    # Select July 1 through August 20, 2025
    berry_trends_2025 = berry_trends[
        (berry_trends["date"] >= "2025-07-01") &
        (berry_trends["date"] <= "2025-08-20")
    ]

    # Select July 1 through August 20, 2026
    berry_trends_2026 = berry_trends[
        (berry_trends["date"] >= "2026-07-01") &
        (berry_trends["date"] <= "2026-08-20")
    ]

    plot_trends(
        berry_trends_2026,
        keywords_grocery_berries,
        "Grocery Stores 2026"
    )

    plot_trends(
        berry_trends_2025,
        keywords_grocery_berries,
        "Grocery Stores 2025"
    )
    

# ---------------------------------------------------------------------------
# Google Trends - Home Cooking Shift
# ---------------------------------------------------------------------------
keywords_homecooking = [
    "how to wash fruit",
    "how to wash vegetables"
]

trends_homecooking = get_trends(keywords_homecooking, '2026-05-01 2026-08-13')
plot_trends(trends_homecooking, keywords_homecooking, "Home Cooking Habits 2026")

keywords_homecooking = [
    "how to wash fruit",
    "how to wash vegetables"
]
 
trends_homecooking = get_trends(keywords_homecooking, '2025-05-01 2025-09-01')
plot_trends(trends_homecooking, keywords_homecooking, "Home Cooking Habits 2025")


#Produce prices
st.header("Produce Prices")

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

fig1 = px.line(high, x="report_date", y="high_price", color="commodity", title="High Price 2026")
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

fig2 = px.line(low, x="report_date", y="low_price", color="commodity", title="Low Price 2026")
st.plotly_chart(fig2)

fig2.update_xaxes(
    range=["2026-01-01", "2026-08-01"]
)

