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

# Custom UI CSS supporting adaptive Light/Dark typography and styling
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
    
    /* Apply clean typography across components */
    html, body, [class*="css"], .stMarkdown {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    }
    
    /* High-contrast adaptive metric containers */
    div[data-testid="stMetric"] {
        background-color: var(--background-color);
        border: 1px solid var(--text-color);
        opacity: 0.85;
        padding: 14px;
        border-radius: 12px;
        box-shadow: 0px 2px 4px rgba(0,0,0,0.05);
    }
    
    /* Ensure metric values and labels explicitly reference theme text colors */
    div[data-testid="stMetric"] label, 
    div[data-testid="stMetric"] div[data-testid="stMetricValue"] {
        color: var(--text-color) !important;
        font-weight: 700;
    }
    
    /* Styled CTA Submit Buttons */
    .stButton>button {
        width: 100%;
        border-radius: 8px;
        font-weight: 600;
        height: 3em;
        background-color: #2ecc71 !important;
        color: white !important;
        border: none;
        transition: transform 0.1s ease;
    }
    .stButton>button:active { transform: scale(0.98); }
    
    /* Quick Log Button Pill Designs */
    div.stActionButton > button {
        border-radius: 20px !important;
        padding: 4px 12px !important;
        font-size: 13px !important;
    }
    </style>
""", unsafe_allow_html=True)

# Schema for Gemini AI structural mapping
class MacroData(BaseModel):
    calories: float = Field(description="Total energy value in kcal")
    protein: float = Field(description="Protein content in grams")
    carbs: float = Field(description="Carbohydrates content in grams")
    fats: float = Field(description="Fats content in grams")

# Fetch Core Airtable Secrets
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
# 2. DATA ACQUISITION & PROCESSING PIPELINE
# ==========================================
@st.cache_data(ttl=60)
def fetch_airtable_data(table_name):
    try:
        url = f"https://api.airtable.com/v0/{BASE_ID}/{table_name}?maxRecords=100&sort[0][field]=Timestamp&sort[0][direction]=desc"
        res = requests.get(url, headers=headers).json()
        return res.get("records", [])
    except Exception:
        return []

diet_records = fetch_airtable_data("Diet")
weight_records = fetch_airtable_data("Weight")

# Parse Daily Metric Totals
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
        try:
            date_part = ts.split(" ")[0]
            logged_dates.add(date_part)
            if ts.startswith(today_str):
                today_cal += float(fields.get("Calories", 0))
                today_protein += float(fields.get("Protein", 0))
                today_carbs += float(fields.get("Carbs", 0))
                today_fats += float(fields.get("Fats", 0))
        except ValueError:
            continue

for record in weight_records:
    fields = record.get("fields", {})
    ts = fields.get("Timestamp", "")
    if ts:
        logged_dates.add(ts.split(" ")[0])

# Calculate Consistency Streak Counters
streak = 0
check_date = datetime.now()
while check_date.strftime("%Y-%m-%d") in logged_dates:
    streak += 1
    check_date -= timedelta(days=1)

# Display Streak Badge
if streak > 0:
    st.markdown(f"🔥 **{streak} Day Consistency Streak!** Keep grinding.")

# ==========================================
# 3. METRIC DASHBOARD OVERVIEW
# ==========================================
st.subheader("Today's Progress")
col1, col2 = st.columns(2)
with col1:
    st.metric("🔥 Calories", f"{today_cal:.1f} kcal")
    st.metric("🍞 Carbs", f"{today_carbs:.1f}g")
with col2:
    st.metric("💪 Protein", f"{today_protein:.1f}g")
    st.metric("🥑 Fats", f"{today_fats:.1f}g")

st.divider()

# ==========================================
# 4. COLLAPSIBLE DATA CAPTURE DRAWERS
# ==========================================

# Dynamic Quick Logs Evaluation
repeated_foods = [food for food, count in Counter(food_history_pool).items() if count >= 3]

with st.expander("📝 Log Meal via AI", expanded=False):
    if repeated_foods:
        st.caption("⚡ Quick Log Favorites:")
        cols = st.columns(min(len(repeated_foods), 3))
        for idx, food in enumerate(repeated_foods[:6]):
            col_target = cols[idx % 3]
            # Keeps display compact but ensures value is parsed properly
            if col_target.button(f"➕ {food[:20]}", key=f"btn_{idx}"):
                st.session_state["meal_text_input"] = food.strip().capitalize()
                st.rerun()

    default_text = st.session_state.get("meal_text_input", "")
    meal_input = st.text_area("What did you eat?", value=default_text, placeholder="e.g., 2 eggs, 2 parathas, and a cup of black coffee")
    submit_meal = st.button("Log Meal", key="main_meal_btn")
    
    if submit_meal and meal_input:
        with st.spinner("Gemini is calculating macros..."):
            try:
                # ENFORCE FORMATTING: First letter capital, rest small
                clean_meal_text = meal_input.strip().title()
                
                res = client.models.generate_content(
                    model='gemini-2.5-flash',
                    contents=f"Analyze macros for this description: {clean_meal_text}",
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_schema=MacroData,
                        temperature=0.1
                    ),
                )
                macros = json.loads(res.text)
                current_time = datetime.now().strftime("%Y-%m-%d %I:%M %p")
                
                data = {
                    "records": [{
                        "fields": {
                            "Timestamp": current_time,
                            "Food Items": clean_meal_text,
                            "Calories": float(macros["calories"]),
                            "Protein": float(macros["protein"]),
                            "Carbs": float(macros["carbs"]),
                            "Fats": float(macros["fats"])
                        }
                    }]
                }
                requests.post(f"https://api.airtable.com/v0/{BASE_ID}/Diet", headers=headers, json=data)
                if "meal_text_input" in st.session_state:
                    del st.session_state["meal_text_input"]
                st.success(f"Added {macros['calories']:.1f} kcal successfully!")
                st.cache_data.clear()
                st.rerun()
            except Exception as e:
                st.error(f"Error parsing entry: {e}")

with st.expander("⚖️ Log Weight Metric", expanded=False):
    with st.form("weight_form", clear_on_submit=True):
        weight_input = st.number_input("Weight (kg)", min_value=10.0, max_value=250.0, step=0.05, format="%.2f")
        submit_weight = st.form_submit_button("Log Weight")
        
        if submit_weight and weight_input > 10.0:
            try:
                current_time = datetime.now().strftime("%Y-%m-%d %I:%M %p")
                data = {
                    "records": [{
                        "fields": {
                            "Timestamp": current_time,
                            "Weight": float(weight_input)
                        }
                    }]
                }
                requests.post(f"https://api.airtable.com/v0/{BASE_ID}/Weight", headers=headers, json=data)
                st.success(f"Logged weight: {weight_input:.2f} kg!")
                st.cache_data.clear()
                st.rerun()
            except Exception as e:
                st.error(f"System Error: {e}")

st.divider()

# ==========================================
# 5. DATA VISUALIZATION TREND CHARTS
# ==========================================
st.subheader("Analytics & Trends")

# ---- 1. Process Calorie Data ----
chart_diet_data = {}
for record in reversed(diet_records):
    fields = record.get("fields", {})
    ts = fields.get("Timestamp", "")
    if ts:
        d_str = ts.split(" ")[0]
        chart_diet_data[d_str] = chart_diet_data.get(d_str, 0.0) + float(fields.get("Calories", 0))

if chart_diet_data:
    st.caption("🔥 Calorie Intake Trend (Daily Totals)")
    df_cal = pd.DataFrame(list(chart_diet_data.items()), columns=["Date", "Calories"]).sort_values("Date")
    
    cal_chart = alt.Chart(df_cal).mark_area(
        line={'color':'#2ecc71', 'width': 2.5},
        color=alt.Gradient(
            gradient='linear',
            stops=[alt.GradientStop(color='#2ecc71', offset=0),
                   alt.GradientStop(color='rgba(46, 204, 113, 0)', offset=1)],
            x1=1, y1=1, x2=1, y2=0
        )
    ).encode(
        x=alt.X('Date:T', axis=alt.Axis(format='%b %d', labelAngle=-45, grid=False)),
        y=alt.Y('Calories:Q', title="kcal", scale=alt.Scale(zero=False))
    ).properties(height=200).configure_view(strokeOpacity=0)
    
    st.altair_chart(cal_chart, use_container_width=True)

# ---- 2. Process Weight Data (Conditional Green/Red Stock Style) ----
chart_weight_data = {}
for record in reversed(weight_records):
    fields = record.get("fields", {})
    ts = fields.get("Timestamp", "")
    if ts:
        w_str = ts.split(" ")[0]
        chart_weight_data[w_str] = float(fields.get("Weight", 0))

if chart_weight_data:
    st.caption("⚖️ Body Weight Progression Trend (kg)")
    df_weight = pd.DataFrame(list(chart_weight_data.items()), columns=["Date", "Weight"]).sort_values("Date")
    
    if len(df_weight) >= 2:
        latest_w = df_weight["Weight"].iloc[-1]
        previous_w = df_weight["Weight"].iloc[-2]
        # Stock market logic: Dropping/maintaining weight is Green, increasing is Red
        trend_color = "#2ecc71" if latest_w <= previous_w else "#e74c3c"
    else:
        trend_color = "#2ecc71"
        
    weight_chart = alt.Chart(df_weight).mark_line(
        color=trend_color,
        point=alt.OverlayMarkDef(color=trend_color, size=40, filled=True),
        strokeWidth=3,
        interpolate='monotone'
    ).encode(
        x=alt.X('Date:T', axis=alt.Axis(format='%b %d', labelAngle=-45, grid=False)),
        y=alt.Y('Weight:Q', title="kg", scale=alt.Scale(zero=False))
    ).properties(height=200).configure_view(strokeOpacity=0)
    
    st.altair_chart(weight_chart, use_container_width=True)

st.divider()

# ==========================================
# 6. HISTORICAL LOGS REVIEW (PAST 3 DAYS)
# ==========================================
st.subheader("History Review")

if weight_records:
    latest_w = weight_records[0].get("fields", {}).get("Weight", "N/A")
    latest_w_ts = weight_records[0].get("fields", {}).get("Timestamp", "")
    st.info(f"**Last Logged Weight:** {latest_w} kg ({latest_w_ts})")

st.caption("📋 Diet Entries (Last 3 Days Tracking Window)")
three_days_ago = (datetime.now() - timedelta(days=3)).strftime("%Y-%m-%d")

recent_entries = []
for record in diet_records:
    fields = record.get("fields", {})
    ts = fields.get("Timestamp", "")
    if ts and ts.split(" ")[0] >= three_days_ago:
        recent_entries.append({
            "Time": ts,
            "Food": fields.get("Food Items", ""),
            "Cals": f"{float(fields.get('Calories', 0)):.1f}",
            "P": f"{float(fields.get('Protein', 0)):.1f}g",
            "C": f"{float(fields.get('Carbs', 0)):.1f}g",
            "F": f"{float(fields.get('Fats', 0)):.1f}g"
        })

if recent_entries:
    st.dataframe(recent_entries, use_container_width=True, hide_index=True)
else:
    st.write("No meals tracked within the last 3 days.")
