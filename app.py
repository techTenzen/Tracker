import streamlit as st
import requests
from datetime import datetime
import json
from google import genai
from google.genai import types
from pydantic import BaseModel, Field

# Page Config
st.set_page_config(page_title="Pocket Health Tracker", page_icon="🥑", layout="centered")

# Custom UI Styling for clean mobile look
st.markdown("""
    <style>
    .stButton>button { width: 100%; border-radius: 8px; font-weight: bold; height: 3em; background-color: #4CAF50; color: white; }
    .stMetric { background-color: #f8f9fa; padding: 12px; border-radius: 8px; border: 1px solid #e9ecef; }
    </style>
""", unsafe_allow_html=True)

# Strict Schema for Gemini AI breakdown
class MacroData(BaseModel):
    calories: float = Field(description="Total energy value in kcal")
    protein: float = Field(description="Protein content in grams")
    carbs: float = Field(description="Carbohydrates content in grams")
    fats: float = Field(description="Fats content in grams")

# Airtable Configurations from Streamlit Secrets
AIRTABLE_TOKEN = st.secrets["AIRTABLE_TOKEN"]
BASE_ID = st.secrets["AIRTABLE_BASE_ID"]

headers = {
    "Authorization": f"Bearer {AIRTABLE_TOKEN}",
    "Content-Type": "application/json"
}

# Initialize modern Gemini client
client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
today_str = datetime.now().strftime("%Y-%m-%d")

st.title("🥑 Pocket Health Tracker")

# ------------------------------------
# 1. Fetch Daily Progress from Airtable
# ------------------------------------
try:
    url = f"https://api.airtable.com/v0/{BASE_ID}/Diet"
    response = requests.get(url, headers=headers).json()
    
    today_cal, today_protein, today_carbs, today_fats = 0.0, 0.0, 0.0, 0.0
    
    if "records" in response:
        for record in response["records"]:
            fields = record.get("fields", {})
            ts = fields.get("Timestamp", "")
            if ts.startswith(today_str):
                today_cal += float(fields.get("Calories", 0))
                today_protein += float(fields.get("Protein", 0))
                today_carbs += float(fields.get("Carbs", 0))
                today_fats += float(fields.get("Fats", 0))

    st.subheader("Today's Progress")
    col1, col2 = st.columns(2)
    with col1:
        st.metric("🔥 Calories", f"{today_cal:.1f} kcal")
        st.metric("🍞 Carbs", f"{today_carbs:.1f}g")
    with col2:
        st.metric("💪 Protein", f"{today_protein:.1f}g")
        st.metric("🥑 Fats", f"{today_fats:.1f}g")
except Exception:
    st.info("Log your meals below to view your daily total breakdowns!")

st.divider()

# ------------------------------------
# 2. Log Meal Form
# ------------------------------------
st.subheader("📝 Log Meal via AI")
with st.form("meal_form", clear_on_submit=True):
    meal_input = st.text_area("What did you eat?", placeholder="e.g., 2 eggs, 2 parathas, and a cup of black coffee")
    submit_meal = st.form_submit_button("Log Meal")
    
    if submit_meal and meal_input:
        with st.spinner("Gemini is calculating macros..."):
            try:
                res = client.models.generate_content(
                    model='gemini-2.5-flash',
                    contents=f"Analyze macros for this description: {meal_input}",
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
                            "Food Items": meal_input,
                            "Calories": float(macros["calories"]),
                            "Protein": float(macros["protein"]),
                            "Carbs": float(macros["carbs"]),
                            "Fats": float(macros["fats"])
                        }
                    }]
                }
                requests.post(f"https://api.airtable.com/v0/{BASE_ID}/Diet", headers=headers, json=data)
                st.success(f"Added {macros['calories']:.1f} kcal successfully!")
                st.rerun()
            except Exception as e:
                st.error(f"Error submitting meal: {e}")

# ------------------------------------
# 3. Log Weight Form
# ------------------------------------
st.subheader("⚖️ Log Weight")
with st.form("weight_form", clear_on_submit=True):
    weight_input = st.number_input("Weight (kg)", min_value=10.0, max_value=250.0, step=0.05, format="%.2f")
    submit_weight = st.form_submit_button("Log Weight")
    
    if submit_weight and weight_input > 10.0:
        try:
            current_time = datetime.now().strftime("%Y-%m-%d %I:%M %p")
            formatted_weight = float(weight_input)
            
            data = {
                "records": [{
                    "fields": {
                        "Timestamp": current_time,
                        "Weight": formatted_weight
                    }
                }]
            }
            
            res = requests.post(f"https://api.airtable.com/v0/{BASE_ID}/Weight", headers=headers, json=data)
            
            if res.status_code in [200, 201]:
                st.success(f"Logged weight: {formatted_weight:.2f} kg!")
                st.rerun()
            else:
                st.error(f"Airtable Error ({res.status_code}): {res.text}")
        except Exception as e:
            st.error(f"System Error: {e}")
