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

THRESHOLDS = {
    "Calories": {"low": 1400.0, "high": 1500.0, "reverse": False},
    "Carbs": {"low": 130.0, "high": 140.0, "reverse": False},
    "Fats": {"low": 40.0, "high": 45.0, "reverse": False},
    "Protein": {"low": 80.0, "high": 95.0, "reverse": True}
}

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
    html, body, [class*="css"], .stMarkdown { font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif; }
    
    /* Custom Bulletproof Metric Cards */
    .metric-card {
        padding: 16px;
        border-radius: 12px;
        margin: 8px 0px;
        box-shadow: 0px 4px 6px rgba(0,0,0,0.05);
        text-align: center;
    }
    .metric-label { font-size: 14px; font-weight: 600; margin-bottom: 4px; opacity: 0.85; }
    .metric-val { font-size: 24px; font-weight: 700; }
    
    .stButton>button { width: 100%; border-radius: 8px; font-weight: 600; height: 3em; background-color: #2ecc71 !important; color: white !important; border: none; }
    </style>
""", unsafe_allow_html=True)

class MacroData(BaseModel):
    calories: float = Field(description="Total energy value in kcal")
    protein: float = Field(description="Protein content in grams")
    carbs: float = Field(description="Carbohydrates content in grams")
    fats: float = Field(description="Fats content in grams")

AIRTABLE_TOKEN = st.secrets["AIRTABLE_TOKEN"]
BASE_ID = st.secrets["AIRTABLE_BASE_ID"]
headers = {"Authorization": f"Bearer {AIRTABLE_TOKEN}", "Content-Type": "application/json"}

client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
today_str = datetime.now().strftime("%Y-%m-%d")

st.title("🥑 Pocket Health Tracker")

# ==========================================
# 2. DATA ACQUISITION PIPELINE
# ==========================================
@st.cache_data(ttl=15)
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

today_cal, today_protein, today_carbs, today_fats = 0.0, 0.0, 0.0, 0.0
food_history_pool = []
logged_dates = set()

for record in diet_records:
    fields = record.get("fields", {})
    ts = fields.get("Timestamp", "")
    food_item = fields.get("Food Items", "")
    if food_item: food_history_pool.append(food_item.strip())
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
    if ts: logged_dates.add(ts.split(" ")[0])

streak = 0
check_date = datetime.now()
while check_date.strftime("%Y-%m-%d") in logged_dates:
    streak += 1
    check_date -= timedelta(days=1)

def get_status_color(val, low, high, reverse=False):
    if reverse:
        if val < low: return "#ff4b4b"     # Light-theme compatible Red
        if val <= high: return "#ffdd57"    # Clear Yellow
        return "#2ecc71"                   # Clean Green
    else:
        if val < low: return "#2ecc71"
        if val <= high: return "#ffdd57"
        return "#ff4b4b"

# ==========================================
# 3. MOTIVATION & HIGHLIGHTS DISPLAY
# ==========================================
st.subheader("Milestones & Highlights")
if streak > 0:
    st.markdown(f"🔥 **{streak} Day Consistency Streak!** Keep grinding.")

for record in moments_records:
    fields = record.get("fields", {})
    if fields.get("Show On Top") is True:
        m_date_str = fields.get("Date", "")
        m_text = fields.get("Moment", "")
        if m_date_str and m_text:
            try:
                days_since = (datetime.now() - datetime.strptime(m_date_str, "%Y-%m-%d")).days
                st.markdown(f"✨ **{m_text}:** {days_since} days ago. Keep it up!")
            except Exception: continue

st.divider()

# ==========================================
# 4. CUSTOM VISUAL METRIC DASHBOARD
# ==========================================
st.subheader("Today's Progress")

cal_color = get_status_color(today_cal, **THRESHOLDS["Calories"])
carb_color = get_status_color(today_carbs, **THRESHOLDS["Carbs"])
fat_color = get_status_color(today_fats, **THRESHOLDS["Fats"])
prot_color = get_status_color(today_protein, **THRESHOLDS["Protein"])

col1, col2 = st.columns(2)
with col1:
    st.markdown(f'<div class="metric-card" style="background-color: {cal_color}25; border: 2px solid {cal_color};"><div class="metric-label" style="color: {cal_color if cal_color!="#ffdd57" else "#bba000"};">🔥 Calories</div><div class="metric-val">{today_cal:.1f} kcal</div></div>', unsafe_allow_html=True)
    st.markdown(f'<div class="metric-card" style="background-color: {carb_color}25; border: 2px solid {carb_color};"><div class="metric-label" style="color: {carb_color if carb_color!="#ffdd57" else "#bba000"};">🍞 Carbs</div><div class="metric-val">{today_carbs:.1f}g</div></div>', unsafe_allow_html=True)
with col2:
    st.markdown(f'<div class="metric-card" style="background-color: {prot_color}25; border: 2px solid {prot_color};"><div class="metric-label" style="color: {prot_color if prot_color!="#ffdd57" else "#bba000"};">💪 Protein</div><div class="metric-val">{today_protein:.1f}g</div></div>', unsafe_allow_html=True)
    st.markdown(f'<div class="metric-card" style="background-color: {fat_color}25; border: 2px solid {fat_color};"><div class="metric-label" style="color: {fat_color if fat_color!="#ffdd57" else "#bba000"};">🥑 Fats</div><div class="metric-val">{today_fats:.1f}g</div></div>', unsafe_allow_html=True)

st.divider()

# ==========================================
# 5. INPUT DRAWERS WITH TIMESHIFT OPTION
# ==========================================
repeated_foods = [food for food, count in Counter(food_history_pool).items() if count >= 3]

with st.expander("📝 Log Food Entries", expanded=False):
    # Flexible Logging Target Config
    log_date_target = st.date_input("Logging for which day?", value=datetime.now(), key="diet_log_date")
    
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
                
                # Check if logging for today or backdating/late night formatting
                if log_date_target.strftime("%Y-%m-%d") == datetime.now().strftime("%Y-%m-%d"):
                    current_time = datetime.now().strftime("%Y-%m-%d %I:%M %p")
                else:
                    # Append 10:00 PM manually if choosing a custom date context
                    current_time = f"{log_date_target.strftime('%Y-%m-%d')} 10:00 PM"
                
                data = {"records": [{"fields": {
                    "Timestamp": current_time, "Food Items": clean_meal_text,
                    "Calories": float(macros["calories"]), "Protein": float(macros["protein"]),
                    "Carbs": float(macros["carbs"]), "Fats": float(macros["fats"])
                }}]}
                requests.post(f"https://api.airtable.com/v0/{BASE_ID}/Diet", headers=headers, json=data)
                if "meal_text_input" in st.session_state: del st.session_state["meal_text_input"]
                st.success(f"Logged for {log_date_target.strftime('%b %d')} successfully!")
                st.cache_data.clear()
                st.rerun()
            except Exception as e: st.error(f"Error: {e}")

with st.expander("⚖️ Log Weight Metric", expanded=False):
    with st.form("weight_form", clear_on_submit=True):
        weight_date_target = st.date_input("Logging for which day?", value=datetime.now(), key="weight_log_date")
        weight_input = st.number_input("Weight (kg)", min_value=10.0, max_value=250.0, step=0.05, format="%.2f")
        submit_weight = st.form_submit_button("Log Weight")
        
        if submit_weight and weight_input > 10.0:
            try:
                if weight_date_target.strftime("%Y-%m-%d") == datetime.now().strftime("%Y-%m-%d"):
                    current_time = datetime.now().strftime("%Y-%m-%d %I:%M %p")
                else:
                    current_time = f"{weight_date_target.strftime('%Y-%m-%d')} 10:00 PM"
                    
                data = {"records": [{"fields": {"Timestamp": current_time, "Weight": float(weight_input)}}]}
                requests.post(f"https://api.airtable.com/v0/{BASE_ID}/Weight", headers=headers, json=data)
                st.success("Weight saved!")
                st.cache_data.clear()
                st.rerun()
            except Exception as e: st.error(f"Error: {e}")

with st.expander("✨ Log A Milestone / Moment", expanded=False):
    with st.form("moments_form", clear_on_submit=True):
        moment_date = st.date_input("When did this happen?", value=datetime.now())
        moment_text = st.text_input("What did you achieve?", placeholder="e.g., Left Sugar, Started Ketosis")
        show_on_top_check = st.checkbox("Pin to top highlight banner?", value=True)
        submit_moment = st.form_submit_button("Save Moment")
        
        if submit_moment and moment_text:
            try:
                clean_moment = moment_text.strip().title()
                data = {"records": [{"fields": {
                    "Date": moment_date.strftime("%Y-%m-%d"), "Moment": clean_moment, "Show On Top": show_on_top_check
                }}]}
                requests.post(f"https://api.airtable.com/v0/{BASE_ID}/Moments", headers=headers, json=data)
                st.success(f"Saved: {clean_moment}")
                st.cache_data.clear()
                st.rerun()
            except Exception as e: st.error(f"Error saving milestone: {e}")

st.divider()

# ==========================================
# 6. STOCK-STYLE VISUALIZATION
# ==========================================
st.subheader("Analytics & Trends")

chart_diet_data = {}
for record in reversed(diet_records):
    fields = record.get("fields", {})
    ts = fields.get("Timestamp", "")
    if ts: chart_diet_data[ts.split(" ")[0]] = chart_diet_data.get(ts.split(" ")[0], 0.0) + float(fields.get("Calories", 0))

if chart_diet_data:
    st.caption("🔥 Calorie Intake Trend")
    df_cal = pd.DataFrame(list(chart_diet_data.items()), columns=["Date", "Calories"]).sort_values("Date")
    cal_line_color = get_status_color(today_cal, **THRESHOLDS["Calories"])
    cal_chart = alt.Chart(df_cal).mark_area(
        line={'color': cal_line_color, 'width': 2.5},
        color=alt.Gradient(gradient='linear', stops=[alt.GradientStop(color=cal_line_color, offset=0), alt.GradientStop(color='rgba(0,0,0,0)', offset=1)], x1=1, y1=1, x2=1, y2=0)
    ).encode(x=alt.X('Date:T', axis=alt.Axis(format='%b %d', labelAngle=-45, grid=False)), y=alt.Y('Calories:Q', scale=alt.Scale(zero=False))).properties(height=180).configure_view(strokeOpacity=0)
    st.altair_chart(cal_chart, use_container_width=True)

chart_weight_data = {}
for record in reversed(weight_records):
    fields = record.get("fields", {})
    ts = fields.get("Timestamp", "")
    if ts: chart_weight_data[ts.split(" ")[0]] = float(fields.get("Weight", 0))

if chart_weight_data:
    st.caption("⚖️ Body Weight Progression Trend (kg)")
    df_weight = pd.DataFrame(list(chart_weight_data.items()), columns=["Date", "Weight"]).sort_values("Date")
    trend_color = "#2ecc71" if len(df_weight) < 2 or df_weight["Weight"].iloc[-1] <= df_weight["Weight"].iloc[-2] else "#ff4b4b"
    weight_chart = alt.Chart(df_weight).mark_line(
        color=trend_color, point=alt.OverlayMarkDef(color=trend_color, size=40, filled=True), strokeWidth=3, interpolate='monotone'
    ).encode(x=alt.X('Date:T', axis=alt.Axis(format='%b %d', labelAngle=-45, grid=False)), y=alt.Y('Weight:Q', scale=alt.Scale(zero=False))).properties(height=180).configure_view(strokeOpacity=0)
    st.altair_chart(weight_chart, use_container_width=True)

st.divider()

# ==========================================
# 7. HISTORY VIEW WINDOW
# ==========================================
st.subheader("History Review")

if weight_records:
    st.info(f"**Last Logged Weight:** {weight_records[0].get('fields', {}).get('Weight', 'N/A')} kg ({weight_records[0].get('fields', {}).get('Timestamp', '')})")

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
