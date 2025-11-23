# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

PillID Emergency is a Streamlit-based medical triage application that identifies pills using Google Gemini 2.5 Flash Vision AI and provides risk assessment for accidental poisonings. Built for Sheridan Datathon 2025.

**Critical Safety Note:** This is a conservative medical triage tool where safety overrides accuracy. The system is designed to never produce false negatives - when in doubt, it always escalates to HIGH RISK.

## Development Commands

### Running the application
```bash
# Local development
streamlit run app.py

# The app will be available at http://localhost:8501
```

### Testing
```bash
# Run the triage logic test suite (10 judge test cases + opioid pattern detection)
python test_triage_logic.py
```

### Database Management
```bash
# Regenerate the pill database from scratch
python fetch_pill_data.py
# This creates pills_db_rich.json (rename to pills_db.json to use)
```

### Deployment
```bash
# Build Docker image
docker build -t pillid-emergency .

# Run Docker container locally
docker run -p 8080:8080 -e GEMINI_API_KEY=your_key pillid-emergency

# Deploy to Google Cloud Run (requires gcloud CLI)
# See cloudbuild.yaml for automated deployment configuration
```

## Architecture & Key Components

### Core Application Flow (app.py)
1. **Input capture**: Dual mode (camera capture OR image upload) via Streamlit
2. **AI Vision OCR**: Gemini 2.5 Flash extracts imprint, shape, color (3-second analysis)
3. **Database matching**: Cross-reference against pills_db.json (56 critical pills)
4. **Conservative triage logic**: Multi-layer safety overrides (order matters!)
5. **Risk display**: Color-coded UI with specific medical actions

### Conservative Safety Architecture (app.py:134-159)

The triage logic uses **cascading safety overrides** in specific order (most conservative first):

1. **Opioid pattern detection** (app.py:137-150): Auto-flags pills matching opioid imprint patterns (M30, A215, K56, etc.) as HIGH RISK even if not in database. Accounts for counterfeit fentanyl.

2. **No pill detected** (app.py:153-154): If Gemini returns "None" or confidence=0, flag as HIGH RISK.

3. **Low confidence override** (app.py:157-158): Any confidence <80% is HIGH RISK regardless of identification (handles blurry photos, screenshots, damaged pills).

**IMPORTANT**: When modifying triage logic, maintain this order. Earlier overrides must take precedence.

### Gemini Vision Integration (app.py:34-45, 58-81)

- **Model**: `gemini-2.5-flash` (latest fast model optimized for OCR)
- **Temperature**: 0.0 (deterministic output for medical safety)
- **Prompt engineering**: Conservative system prompt that instructs model to set low confidence for poor quality images
- **Output format**: Strict JSON schema with imprint, shape, color, confidence
- **Safety rules embedded in prompt**: Specific confidence caps for blurry/dark/damaged/screenshot images

### Pill Database Structure (pills_db.json)

Each pill entry contains:
- `imprint`: Exact text on pill (e.g., "M367", "IBU 200")
- `name`: Generic/brand name
- `ndc`: FDA National Drug Code (or "CAN-*" for Canadian drugs)
- `risk`: "High" | "Medium" | "Low"
- `shape`: round, oblong, oval, capsule, etc.
- `color`: Physical color description
- `description`: Medical context
- `action`: Specific instruction for parents/caregivers

**Database coverage** (56 pills total):
- 14 High-risk opioids (counterfeit fentanyl concern)
- 8 High-risk benzodiazepines
- 4 High-risk cardiovascular (deadly for children)
- 5 High-risk antipsychotics/muscle relaxants
- 13 Medium-risk monitoring pills
- 10 Low-risk OTC safe pills
- 2 Canadian generic brands

### Session State Management (app.py:13-16, 161-177)

- `st.session_state.last_result`: Persists latest analysis across input method switches
- `st.session_state.history`: Tracks all pills analyzed during session with timestamps

**Critical implementation detail**: Results are saved to session state BEFORE rendering (app.py:161-167) to ensure persistence when user switches between camera/upload modes.

### Configuration Requirements

The app requires a Gemini API key configured via one of:
1. `.streamlit/secrets.toml` (recommended for production)
2. `.env` file with `GEMINI_API_KEY` (local development fallback)

See app.py:18-30 for key loading logic with graceful fallbacks.

## Testing Philosophy

`test_triage_logic.py` simulates the complete triage logic without requiring actual images. It tests:
- Perfect identifications (high confidence matches)
- Edge cases (blurry, dark, damaged pills)
- Safety overrides (screenshots, no pill detected)
- Opioid pattern detection regex
- False positive prevention (Advil should not trigger opioid pattern)

**All tests must pass before deployment.** The test suite is designed to validate "judge-proof" behavior.

## Deployment Architecture

- **Platform**: Google Cloud Run (serverless, auto-scaling)
- **Container**: Python 3.10-slim with Streamlit
- **Port**: 8080 (Cloud Run standard)
- **Environment**: `GEMINI_API_KEY` injected via Cloud Build substitution (cloudbuild.yaml:28-29)
- **Build pipeline**: Automated via `cloudbuild.yaml`

## Critical Code Patterns

### Database Matching Logic (app.py:125-132)
Uses substring matching with minimum 2-character requirement:
```python
if len(pill_imprint) >= 2 and pill_imprint in imprint and imprint != "NONE":
```
This prevents false matches on single characters while allowing partial matches (e.g., "M367" in "M367 SOMETHING").

### Opioid Pattern Detection (app.py:137-150)
Regex patterns are designed to catch common opioid imprint formats:
- `\bM\d{2,4}\b`: M30, M367, M523 (Mallinckrodt generics)
- `\bA\d{2,4}\b`: A215, A51 (Actavis)
- `\b\d{3,4}\b`: Pure numbers (224=Dilaudid, 512=Percocet)

**Word boundaries** (`\b`) prevent false matches in longer strings.

### JSON Response Parsing (app.py:108-115)
Gemini sometimes wraps JSON in markdown code blocks. The parser strips ```json and ``` delimiters before parsing.

## Known Limitations

1. Database is limited to 56 pills (targets top 200 eventually)
2. Model accuracy degrades with poor lighting, blurry images, or damaged pills (this is intentional - triggers safety override)
3. Canadian pills may have different imprints than US equivalents
4. Counterfeit pills with correct imprints will be identified as legitimate (this is why opioid patterns auto-flag as HIGH RISK)

## Regulatory Context

This is a **hackathon prototype**, not a medical device. The conservative architecture is designed with a future Health Canada Class II Medical Device regulatory pathway in mind:
- Zero false negatives (never says "safe" incorrectly)
- Mandatory escalation to Poison Control for unknowns
- Deterministic AI behavior (temperature=0.0)
- Audit trail via session history
