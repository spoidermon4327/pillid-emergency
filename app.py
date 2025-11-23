import streamlit as st
import google.generativeai as genai
from PIL import Image
import json
import os
import re
from datetime import datetime

# --- CONFIGURATION ---
st.set_page_config(page_title="PillID Emergency", page_icon="🚨", layout="centered")

# --- SESSION STATE ---
if 'history' not in st.session_state:
    st.session_state.history = []
if 'last_result' not in st.session_state:
    st.session_state.last_result = None

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
You are PillID Emergency — a hyper-conservative triage toxicologist.
Your #1 rule: NEVER say high confidence unless you are 100% certain.
Prioritize child safety above all else.

CRITICAL SAFETY RULES (set confidence low if ANY apply):
- Image is blurry, dark, or poor quality → confidence MAX 30
- Pill is broken, chewed, or damaged → confidence MAX 40
- Image is a screenshot of another screen → confidence MAX 20
- No pill visible in image → imprint_found = "None", confidence = 0
- Multiple pills or unclear which pill → confidence MAX 50
- Imprint is partially visible or unclear → confidence MAX 60

Your goal: Extract pill imprint, shape, and color from the image.
Return STRICT JSON only. No explanations. No apologies.

JSON Schema (must match exactly):
{
  "imprint_found": "string (exact text on pill, or 'None' if no pill/no imprint)",
  "shape": "string (round, oblong, oval, capsule, etc.)",
  "color": "string",
  "confidence": "integer (0-100, be VERY conservative)"
}
"""

# --- UI LAYOUT ---
st.title("🚨 PillID Emergency")
st.markdown("**3-Second Triage for Accidental Poisonings**")

# MODE SELECTION (Human or Pet)
user_mode = st.radio("Who was exposed?", ["👶 Human", "🐕 Pet"], horizontal=True)

# Input Options (Camera OR Upload)
input_method = st.radio("Choose input method:", ["📷 Take Photo", "📤 Upload Image"], horizontal=True)

img_file_buffer = None

if input_method == "📷 Take Photo":
    img_file_buffer = st.camera_input("Take a clear photo of the pill")
else:
    img_file_buffer = st.file_uploader("Upload a pill image", type=["jpg", "jpeg", "png", "webp"])

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
            is_pet_mode = (user_mode == "🐕 Pet")

            # Check against Local DB (improved matching - require substantial overlap)
            for pill in PILL_DB:
                pill_imprint = pill["imprint"].upper()
                # More strict matching: pill imprint must be IN the detected imprint
                # and must be at least 2 characters to avoid false matches
                if len(pill_imprint) >= 2 and pill_imprint in imprint and imprint != "NONE":
                    found_pill = pill
                    risk_level = pill["risk"]
                    break

            # PET MODE OVERRIDE - Check if pill is toxic to pets
            if is_pet_mode and found_pill and found_pill.get("pet_toxic"):
                risk_level = f"PET-TOXIC-{found_pill.get('pet_toxic')}"

            # NUCLEAR SAFETY OVERRIDES (order matters - most conservative first)

            # 1. Opioid Pattern Detection (ONLY if pill not in database)
            # This prevents false positives on known safe pills like "IBU 200"
            if not found_pill:
                opioid_patterns = [
                    r'\bM\d{2,4}\b',      # M30, M367, M523, etc.
                    r'\bA\d{2,4}\b',      # A215, A51, etc.
                    r'\bK\d{2,4}\b',      # K56, K9, etc.
                    r'\bIP\s?\d{2,4}\b',  # IP204, IP 101, etc.
                    r'\bRP\s?\d{1,4}\b',  # RP 10, RP30, etc.
                    r'^\d{3,4}$'          # ONLY pure numbers (224, 512) - not "IBU 200"
                ]
                for pattern in opioid_patterns:
                    if re.search(pattern, imprint):
                        risk_level = "HIGH - OPIOID PATTERN - POSSIBLE FENTANYL"
                        break

            # 2. No pill detected / no imprint
            if imprint == "NONE" or confidence == 0:
                risk_level = "HIGH - NO PILL DETECTED"

            # 3. Low confidence (blurry, dark, damaged, screenshot)
            elif confidence < 80:
                risk_level = "HIGH - LOW CONFIDENCE"
            
            # 5. Save to session state FIRST
            result_data = {
                'risk_level': risk_level,
                'found_pill': found_pill,
                'imprint': imprint,
                'confidence': confidence,
                'user_mode': user_mode
            }
            st.session_state.last_result = result_data

            # Save to history
            history_entry = {
                'timestamp': datetime.now().strftime("%H:%M:%S"),
                'pill_name': found_pill['name'] if found_pill else 'Unknown',
                'risk_level': risk_level,
                'imprint': imprint,
                'confidence': confidence
            }
            st.session_state.history.append(history_entry)

        except Exception as e:
            st.error(f"Error analyzing image: {e}")
            st.warning("Please retake the photo with better lighting.")

# Display last result (persists across input method changes)
if st.session_state.last_result is not None:
    result = st.session_state.last_result
    risk_level = result['risk_level']
    found_pill = result['found_pill']
    imprint = result['imprint']
    confidence = result['confidence']

    st.divider()

    # PET TOXICITY DISPLAY (Purple Screen)
    if "PET-TOXIC" in risk_level:
        toxicity_level = risk_level.split("-")[-1]  # Extract LETHAL, EXTREME, or High

        # Custom CSS for purple warning
        st.markdown("""
        <style>
        .pet-toxic-box {
            background-color: #8B00FF;
            padding: 20px;
            border-radius: 10px;
            border: 3px solid #FF00FF;
            color: white;
            text-align: center;
        }
        </style>
        """, unsafe_allow_html=True)

        if toxicity_level == "LETHAL":
            st.markdown('<div class="pet-toxic-box"><h1>💀 DEADLY TO PETS 💀</h1></div>', unsafe_allow_html=True)
        elif toxicity_level == "EXTREME":
            st.markdown('<div class="pet-toxic-box"><h1>🚨 EXTREMELY TOXIC TO PETS 🚨</h1></div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="pet-toxic-box"><h1>⚠️ TOXIC TO PETS ⚠️</h1></div>', unsafe_allow_html=True)

        st.error(f"**IDENTIFIED:** {found_pill['name']}")
        st.markdown(f"### {found_pill.get('pet_action', 'CALL VET EMERGENCY IMMEDIATELY')}")

        st.warning("**For Humans:** This medication is safe at normal doses")
        st.info(f"**Human Action:** {found_pill.get('action', 'N/A')}")

        col1, col2, col3 = st.columns(3)
        with col1:
            st.caption(f"**Shape:** {found_pill.get('shape', 'N/A')}")
        with col2:
            st.caption(f"**Color:** {found_pill.get('color', 'N/A')}")
        with col3:
            st.caption(f"**NDC:** {found_pill.get('ndc', 'N/A')}")
        st.caption(f"Confidence: {confidence}% | Imprint: {imprint}")

    elif risk_level == "Low" and found_pill:
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

        # Special handling for NO PILL DETECTED case
        if "NO PILL DETECTED" in risk_level:
            st.write("**⚠️ No Pill Visible in Image**")
            st.markdown("### If a child may have swallowed anything:")
            st.markdown("## 📞 CALL POISON CONTROL NOW")
            st.markdown("## [1-800-268-9017](tel:18002689017)")
            st.write("If the child is unconscious or having trouble breathing:")
            st.markdown("## 🚨 CALL 911 IMMEDIATELY")

        # Pill detected with database match
        elif found_pill:
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

        # Unknown pill or opioid pattern
        else:
            if "OPIOID PATTERN" in risk_level:
                st.write("**⚠️ OPIOID-LIKE IMPRINT DETECTED**")
                st.write(f"**Pattern:** {imprint}")
                st.markdown("### 🚨 EXTREME RISK - POSSIBLE COUNTERFEIT FENTANYL")
                st.markdown("## CALL 911 IMMEDIATELY")
                st.markdown("## [911](tel:911)")
            else:
                st.write("**Unknown Pill Detected**")
                st.write("Imprint not recognized or confidence too low.")
                st.markdown("### 📞 CALL POISON CONTROL NOW")
                st.markdown("### [1-800-268-9017](tel:18002689017)")

        st.caption(f"Risk Level: {risk_level}")
        st.caption(f"Confidence: {confidence}% | Imprint: {imprint}")

# --- SIDEBAR: SESSION HISTORY ---
with st.sidebar:
    st.markdown("## 📋 Session History")

    if len(st.session_state.history) > 0:
        st.caption(f"**{len(st.session_state.history)} pill(s) analyzed this session**")

        if st.button("🗑️ Clear History"):
            st.session_state.history = []
            st.rerun()

        st.markdown("---")

        for idx, entry in enumerate(reversed(st.session_state.history)):
            risk_color = "🟢" if "Low" in entry['risk_level'] else "🔴"
            st.markdown(f"**{risk_color} {entry['timestamp']}**")
            st.caption(f"{entry['pill_name']}")
            st.caption(f"Confidence: {entry['confidence']}%")
            st.markdown("---")
    else:
        st.info("No pills analyzed yet. Upload or scan a pill to start!")

st.markdown("---")
st.caption("⚠️ This is a Demo Tool. Always call professional medical help in emergencies.")


