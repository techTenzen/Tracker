import streamlit as st
import requests
from datetime import datetime, timedelta
import json
from collections import Counter
import altair as alt
import pandas as pd
from google import genai
from google.genai import types
from pydantic import BaseModel, Field

# ==========================================
# 1. PAGE SETUP & ADAPTIVE STYLING
# ==========================================
st.set_page_config(page_title="Pocket Health Tracker", page_icon="🥑", layout="centered")

# Set target thresholds globally
THRESHOLDS = {
    "Calories": {"low": 1400.0, "high": 1500.0, "reverse": False},
    "Carbs": {"low": 130.0, "high": 140.0, "reverse": False},
    "Fats": {"low": 40.0, "high": 45.0, "reverse": False},
    "Protein": {"low": 80.0, "high": 95.0, "reverse": True} # Reverse because more protein is positive
}

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
    
    html, body, [class*="css"], .stMarkdown {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    }
    
    /* Base Metric Layouts */
    div[data-testid="stMetric"] {
        background-color: var(--background-color);
        border: 2px solid var(--text-color);
        opacity: 0.9;
        padding: 14px;
        border-radius: 12px;
        box-shadow: 0px 4px 6px rgba(0,0,0,0.05);
    }
    
    div[data-testid="stMetric"] label, 
    div[data-testid="stMetric"] div[data-testid="stMetricValue"] {
        font-weight: 700;
    }

    /* Form and Accordion Styling */
    .stButton>button {
        width: 100%;
        border-radius: 8px;
        font-weight: 600;
        height: 3em;
        background-color: #2ecc71 !important;
        color: white !important;
        border: none;
    }
    
    .moment-badge {
        padding: 6px 12px;
        border-radius: 20px;
        font-size: 14px;
        font-weight: 600;
        margin-bottom: 6px;
        display: inline-block;
    }
    </style>
""", unsafe_allow_html=True)

class MacroData(BaseModel):
    calories: float = Field(description="Total energy value in kcal")
    protein: float = Field(description="Protein content in grams")
    carbs: float = Field(description="Carbohydrates content in grams")
    fats: float = Field(description="Fats content in grams")

AIRTABLE_TOKEN = st.secrets["AIRTABLE_TOKEN"]
BASE_ID = st.secrets["AIRTABLE_BASE_ID"]
headers = {
    "Authorization": f"Bearer {AIRTABLE_TOKEN}",
    "Content-Type": "application/json"
}

client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
today_str = datetime.now().strftime("%Y-%m-%d")

st.title("🥑 Pocket Health Tracker")

# ==========================================
# 2. DATA ACQUISITION PIPELINE
# ==========================================
@st.cache_data(ttl=30)
def fetch_airtable_data(table_name):
    try:
        url = f"https://api.airtable.com/v0/{BASE_ID}/{table_name}?maxRecords=100"
        if table_name != "Moments":
            url += "&sort[0][field]=Timestamp&sort[0][direction]=desc"
        res = requests.get(url, headers=headers).json()
        return res.get("records", [])
    except Exception:
        return []

diet_records = fetch_airtable_data("Diet")
weight_records = fetch_airtable_data("Weight")
moments_records = fetch_airtable_data("Moments")

# Parse Diet History & Totals
today_cal, today_protein, today_carbs, today_fats = 0.0, 0.0, 0.0, 0.0
food_history_pool = []
logged_dates = set()

for record in diet_records:
    fields = record.get("fields", {})
    ts = fields.get("Timestamp", "")
    food_item = fields.get("Food Items", "")
    if food_item:
        food_history_pool.append(food_item.strip())
    if ts:
        date_part = ts.split(" ")[0]
        logged_dates.add(date_part)
        if ts.startswith(today_str):
            today_cal += float(fields.get("Calories", 0))
            today_protein += float(fields.get("Protein", 0))
            today_carbs += float(fields.get("Carbs", 0))
            today_fats += float(fields.get("Fats", 0))

for record in weight_records:
    fields = record.get("fields", {})
    ts = fields.get("Timestamp", "")
    if ts:
        logged_dates.add(ts.split(" ")[0])

# Calculate Streak
streak = 0
check_date = datetime.now()
while check_date.strftime("%Y-%m-%d") in logged_dates:
    streak += 1
    check_date -= timedelta(days=1)

# Helper function to assign color formatting states
def get_status_color(val, low, high, reverse=False):
    if reverse:
        if val < low: return "#e74c3c"    # Red (Under-target for protein)
        if val <= high: return "#f1c40f"   # Yellow
        return "#2ecc71"                   # Green (High protein)
    else:
        if val < low: return "#2ecc71"     # Green (Safe zone)
        if val <= high: return "#f1c40f"   # Yellow (Warning threshold)
        return "#e74c3c"                   # Red (Limit crossed)

# ==========================================
# 3. MOTIVATION & HIGHLIGHTS DISPLAY
# ==========================================
st.subheader("Milestones & Highlights")
if streak > 0:
    st.markdown(f"🔥 **{streak} Day Consistency Streak!** Keep grinding.")

# Parse and display pinned Dynamic Moments
for record in moments_records:
    fields = record.get("fields", {})
    if fields.get("Show On Top") is True:
        m_date_str = fields.get("Date", "")
        m_text = fields.get("Moment", "")
        if m_date_str and m_text:
            try:
                m_date = datetime.strptime(m_date_str, "%Y-%m-%d")
                days_since = (datetime.now() - m_date).days
                
                # Dynamic encouragement triggers
                msg = "Keep it up!" if days_since > 5 else "Good work!"
                st.markdown(f"✨ **{m_text}:** {days_since} days ago. {msg}")
            except Exception:
                continue

st.divider()

# ==========================================
# 4. COLOR-CODED METRIC BOXES
# ==========================================
st.subheader("Today's Progress")

cal_color = get_status_color(today_cal, **THRESHOLDS["Calories"])
carb_color = get_status_color(today_carbs, **THRESHOLDS["Carbs"])
fat_color = get_status_color(today_fats, **THRESHOLDS["Fats"])
prot_color = get_status_color(today_protein, **THRESHOLDS["Protein"])

# Force explicit background tint and text glow matching status criteria
st.markdown(f"""
    <style>
    /* Target the metric containers sequentially and force style states */
    div[data-testid="stMetricBlock"]:nth-of-type(1) {{
        background-color: {cal_color}22 !important; /* Adding '22' makes the background a light tint */
        border: 2px solid {cal_color} !important;
    }}
    div[data-testid="stMetricBlock"]:nth-of-type(2) {{
        background-color: {carb_color}22 !important;
        border: 2px solid {carb_color} !important;
    }}
    div[data-testid="stMetricBlock"]:nth-of-type(3) {{
        background-color: {prot_color}22 !important;
        border: 2px solid {prot_color} !important;
    }}
    div[data-testid="stMetricBlock"]:nth-of-type(4) {{
        background-color: {fat_color}22 !important;
        border: 2px solid {fat_color} !important;
    }}
    
    /* Make the metric labels and values high-contrast dark text over the tinted backgrounds */
    div[data-testid="stMetric"] label, 
    div[data-testid="stMetric"] div[data-testid="stMetricValue"] {{
        color: var(--text-color) !important;
        text-shadow: 0px 0px 1px rgba(0,0,0,0.1);
    }}
    </style>
""", unsafe_allow_html=True)

col1, col2 = st.columns(2)
with col1:
    st.metric("🔥 Calories", f"{today_cal:.1f} kcal")
    st.metric("🍞 Carbs", f"{today_carbs:.1f}g")
with col2:
    st.metric("💪 Protein", f"{today_protein:.1f}g")
    st.metric("🥑 Fats", f"{today_fats:.1f}g")

# ==========================================
# 5. INPUT DRAWERS (MEALS / WEIGHT / MOMENTS)
# ==========================================
repeated_foods = [food for food, count in Counter(food_history_pool).items() if count >= 3]

with st.expander("📝 Log Food Entries", expanded=False):
    if repeated_foods:
        st.caption("⚡ Quick Log Favorites:")
        cols = st.columns(min(len(repeated_foods), 3))
        for idx, food in enumerate(repeated_foods[:6]):
            col_target = cols[idx % 3]
            if col_target.button(f"➕ {food[:20]}", key=f"btn_{idx}"):
                st.session_state["meal_text_input"] = food.strip().title()
                st.rerun()

    default_text = st.session_state.get("meal_text_input", "")
    meal_input = st.text_area("What did you eat?", value=default_text, placeholder="e.g., 1 Banana, 2 Roti, 2 Eggs")
    submit_meal = st.button("Log Meal Entry", key="main_meal_btn")
    
    if submit_meal and meal_input:
        with st.spinner("Calculating macros..."):
            try:
                clean_meal_text = meal_input.strip().title()
                res = client.models.generate_content(
                    model='gemini-2.5-flash',
                    contents=f"Analyze macros for this description: {clean_meal_text}",
                    config=types.GenerateContentConfig(response_mime_type="application/json", response_schema=MacroData, temperature=0.1),
                )
                macros = json.loads(res.text)
                current_time = datetime.now().strftime("%Y-%m-%d %I:%M %p")
                
                data = {"records": [{"fields": {
                    "Timestamp": current_time, "Food Items": clean_meal_text,
                    "Calories": float(macros["calories"]), "Protein": float(macros["protein"]),
                    "Carbs": float(macros["carbs"]), "Fats": float(macros["fats"])
                }}]}
                requests.post(f"https://api.airtable.com/v0/{BASE_ID}/Diet", headers=headers, json=data)
                if "meal_text_input" in st.session_state: del st.session_state["meal_text_input"]
                st.success("Logged successfully!")
                st.cache_data.clear()
                st.rerun()
            except Exception as e: st.error(f"Error: {e}")

with st.expander("⚖️ Log Weight Metric", expanded=False):
    with st.form("weight_form", clear_on_submit=True):
        weight_input = st.number_input("Weight (kg)", min_value=10.0, max_value=250.0, step=0.05, format="%.2f")
        submit_weight = st.form_submit_button("Log Weight")
        if submit_weight and weight_input > 10.0:
            try:
                current_time = datetime.now().strftime("%Y-%m-%d %I:%M %p")
                data = {"records": [{"fields": {"Timestamp": current_time, "Weight": float(weight_input)}}]}
                requests.post(f"https://api.airtable.com/v0/{BASE_ID}/Weight", headers=headers, json=data)
                st.success("Weight saved!")
                st.cache_data.clear()
                st.rerun()
            except Exception as e: st.error(f"Error: {e}")

# NEW: Moments Logging Drawer
with st.expander("✨ Log A Milestone / Moment", expanded=False):
    with st.form("moments_form", clear_on_submit=True):
        moment_date = st.date_input("When did this happen?", value=datetime.now())
        moment_text = st.text_input("What did you achieve?", placeholder="e.g., Left Sugar, Started Ketosis, Hit Gym")
        show_on_top_check = st.checkbox("Pin to top highlight banner?", value=True)
        submit_moment = st.form_submit_button("Save Moment")
        
        if submit_moment and moment_text:
            try:
                clean_moment = moment_text.strip().title()
                data = {"records": [{"fields": {
                    "Date": moment_date.strftime("%Y-%m-%d"),
                    "Moment": clean_moment,
                    "Show On Top": show_on_top_check
                }}]}
                requests.post(f"https://api.airtable.com/v0/{BASE_ID}/Moments", headers=headers, json=data)
                st.success(f"Saved: {clean_moment}")
                st.cache_data.clear()
                st.rerun()
            except Exception as e: st.error(f"Error saving milestone: {e}")

st.divider()

# ==========================================
# 6. STOCK-STYLE FINANCIAL VISUALIZATION
# ==========================================
st.subheader("Analytics & Trends")

# Process Calories
chart_diet_data = {}
for record in reversed(diet_records):
    fields = record.get("fields", {})
    ts = fields.get("Timestamp", "")
    if ts:
        d_str = ts.split(" ")[0]
        chart_diet_data[d_str] = chart_diet_data.get(d_str, 0.0) + float(fields.get("Calories", 0))

if chart_diet_data:
    st.caption("🔥 Calorie Intake Trend")
    df_cal = pd.DataFrame(list(chart_diet_data.items()), columns=["Date", "Calories"]).sort_values("Date")
    
    # Check current status coloring for chart line matching today's metric state
    cal_line_color = get_status_color(today_cal, **THRESHOLDS["Calories"])
    
    cal_chart = alt.Chart(df_cal).mark_area(
        line={'color': cal_line_color, 'width': 2.5},
        color=alt.Gradient(
            gradient='linear',
            stops=[alt.GradientStop(color=cal_line_color, offset=0), alt.GradientStop(color='rgba(0,0,0,0)', offset=1)],
            x1=1, y1=1, x2=1, y2=0
        )
    ).encode(
        x=alt.X('Date:T', axis=alt.Axis(format='%b %d', labelAngle=-45, grid=False)),
        y=alt.Y('Calories:Q', scale=alt.Scale(zero=False))
    ).properties(height=180).configure_view(strokeOpacity=0)
    st.altair_chart(cal_chart, use_container_width=True)

# Process Weight
chart_weight_data = {}
for record in reversed(weight_records):
    fields = record.get("fields", {})
    ts = fields.get("Timestamp", "")
    if ts: chart_weight_data[ts.split(" ")[0]] = float(fields.get("Weight", 0))

if chart_weight_data:
    st.caption("⚖️ Body Weight Progression Trend (kg)")
    df_weight = pd.DataFrame(list(chart_weight_data.items()), columns=["Date", "Weight"]).sort_values("Date")
    
    if len(df_weight) >= 2:
        trend_color = "#2ecc71" if df_weight["Weight"].iloc[-1] <= df_weight["Weight"].iloc[-2] else "#e74c3c"
    else:
        trend_color = "#2ecc71"
        
    weight_chart = alt.Chart(df_weight).mark_line(
        color=trend_color, point=alt.OverlayMarkDef(color=trend_color, size=40, filled=True),
        strokeWidth=3, interpolate='monotone'
    ).encode(
        x=alt.X('Date:T', axis=alt.Axis(format='%b %d', labelAngle=-45, grid=False)),
        y=alt.Y('Weight:Q', scale=alt.Scale(zero=False))
    ).properties(height=180).configure_view(strokeOpacity=0)
    st.altair_chart(weight_chart, use_container_width=True)

st.divider()

# ==========================================
# 7. HISTORY VIEW WINDOW
# ==========================================
st.subheader("History Review")

if weight_records:
    latest_w = weight_records[0].get("fields", {}).get("Weight", "N/A")
    latest_w_ts = weight_records[0].get("fields", {}).get("Timestamp", "")
    st.info(f"**Last Logged Weight:** {latest_w} kg ({latest_w_ts})")

st.caption("📋 Recent Diet Entries (Last 3 Days)")
three_days_ago = (datetime.now() - timedelta(days=3)).strftime("%Y-%m-%d")

recent_entries = []
for record in diet_records:
    fields = record.get("fields", {})
    ts = fields.get("Timestamp", "")
    if ts and ts.split(" ")[0] >= three_days_ago:
        recent_entries.append({
            "Time": ts, "Food": fields.get("Food Items", ""),
            "Cals": f"{float(fields.get('Calories', 0)):.1f}",
            "P": f"{float(fields.get('Protein', 0)):.1f}g",
            "C": f"{float(fields.get('Carbs', 0)):.1f}g",
            "F": f"{float(fields.get('Fats', 0)):.1f}g"
        })

if recent_entries: st.dataframe(recent_entries, use_container_width=True, hide_index=True)
