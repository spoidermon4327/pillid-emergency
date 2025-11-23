import streamlit as st
import google.generativeai as genai
from PIL import Image
import json
import os

# --- CONFIGURATION ---
st.set_page_config(page_title="PillID Emergency", page_icon="🚨", layout="centered")

# --- SETUP GEMINI ---
# Try to get key from secrets, otherwise look for env var
try:
    api_key = st.secrets["general"]["GEMINI_API_KEY"]
except FileNotFoundError:
    try:
        # Fallback for local testing if secrets.toml isn't found
        from dotenv import load_dotenv
        load_dotenv()
        api_key = os.getenv("GEMINI_API_KEY")
    except:
        st.error("API Key not found. Please set GEMINI_API_KEY in secrets.toml")
        st.stop()

genai.configure(api_key=api_key)

# Model Configuration
generation_config = {
  "temperature": 0.0, # Deterministic for medical safety
  "top_p": 1,
  "top_k": 32,
  "max_output_tokens": 8192,
}

model = genai.GenerativeModel(
  model_name="gemini-2.5-flash", # Latest fast model for OCR
  generation_config=generation_config,
)

# --- LOAD DATABASE ---
def load_db():
    try:
        with open('pills_db.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return []

PILL_DB = load_db()

# --- PROMPT ENGINEERING ---
SYSTEM_PROMPT = """
You are a conservative medical triage assistant for emergency pill identification.
Your Goal: Identify the pill imprint, shape, and color from the image.
CRITICAL SAFETY RULE: If you are not 100% sure, or if the pill is blurry/damaged, you MUST classify as "Unknown".
Better to raise a false alarm than miss a dangerous pill.

Analyze the image and return valid JSON with this exact schema:
{
  "imprint_found": "string (text visible on pill, or 'None')",
  "shape": "string (round, oblong, oval, etc)",
  "color": "string",
  "confidence": "integer (0-100)"
}
"""

# --- UI LAYOUT ---
st.title("🚨 PillID Emergency")
st.markdown("**3-Second Triage for Accidental Poisonings**")

# Input Options (Camera OR Upload)
tab1, tab2 = st.tabs(["📷 Take Photo", "📤 Upload Image"])

img_file_buffer = None

with tab1:
    camera_image = st.camera_input("Take a clear photo of the pill")
    if camera_image is not None:
        img_file_buffer = camera_image

with tab2:
    uploaded_image = st.file_uploader("Upload a pill image", type=["jpg", "jpeg", "png", "webp"])
    if uploaded_image is not None:
        img_file_buffer = uploaded_image

if img_file_buffer is not None:
    # Show spinner while processing
    with st.spinner('Analyzing pill (Gemini Vision)...'):
        try:
            # 1. Process Image
            image = Image.open(img_file_buffer)
            
            # 2. Call Gemini
            response = model.generate_content([SYSTEM_PROMPT, image])
            
            # 3. Parse JSON
            # Gemini sometimes wraps JSON in ```json ... ```, we need to clean it
            text_response = response.text.strip()
            if text_response.startswith("```json"):
                text_response = text_response[7:]
            if text_response.endswith("```"):
                text_response = text_response[:-3]
            
            data = json.loads(text_response)
            
            # 4. Triage Logic
            imprint = data.get("imprint_found", "None").upper().strip()
            confidence = data.get("confidence", 0)
            
            risk_level = "UNKNOWN"
            found_pill = None
            
            # Check against Local DB
            for pill in PILL_DB:
                if pill["imprint"] in imprint and imprint != "NONE":
                    found_pill = pill
                    risk_level = pill["risk"]
                    break
            
            # Conservative Overrides
            if confidence < 80:
                risk_level = "HIGH - LOW CONFIDENCE"
            elif imprint == "NONE":
                risk_level = "HIGH - UNKNOWN"
            
            # 5. Display Results
            st.divider()
            
            if risk_level == "Low" and found_pill:
                st.success(f"✅ IDENTIFIED: {found_pill['name']}")
                st.info(f"**Status:** Safe to Monitor")
                st.markdown(f"**What to Do:** {found_pill.get('action', 'Monitor at home')}")
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.caption(f"**Shape:** {found_pill.get('shape', 'N/A')}")
                with col2:
                    st.caption(f"**Color:** {found_pill.get('color', 'N/A')}")
                with col3:
                    st.caption(f"**NDC:** {found_pill.get('ndc', 'N/A')}")
                st.caption(f"Confidence: {confidence}% | Imprint: {imprint}")

            else:
                st.error("🚨 HIGH RISK ALERT")
                if found_pill:
                    st.write(f"**Possible Match:** {found_pill['name']}")
                    st.write(f"**Description:** {found_pill.get('description', 'Unknown')}")
                    st.markdown(f"### ⚠️ ACTION REQUIRED")
                    st.markdown(f"## {found_pill.get('action', 'CALL POISON CONTROL 1-800-268-9017')}")
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.caption(f"**Shape:** {found_pill.get('shape', 'N/A')}")
                    with col2:
                        st.caption(f"**Color:** {found_pill.get('color', 'N/A')}")
                    with col3:
                        st.caption(f"**NDC:** {found_pill.get('ndc', 'N/A')}")
                else:
                    st.write("**Unknown Pill Detected**")
                    st.write("Imprint not recognized or confidence too low.")
                    st.markdown("### 📞 CALL POISON CONTROL NOW")
                    st.markdown("### [1-800-268-9017](tel:18002689017)")

                st.caption(f"Confidence: {confidence}% | Imprint: {imprint}")

        except Exception as e:
            st.error(f"Error analyzing image: {e}")
            st.warning("Please retake the photo with better lighting.")

st.markdown("---")
st.caption("⚠️ This is a Demo Tool. Always call professional medical help in emergencies.")


