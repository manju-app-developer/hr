import streamlit as st
import google.generativeai as genai
import PyPDF2 as pdf
import json
import time

# --- Page Config (Must be first) ---
st.set_page_config(page_title="Resume Matcher Pro", page_icon="", layout="wide")

# --- 🎨 Apple-Style Custom CSS ---
st.markdown("""
<style>
    /* Main Background */
    .stApp {
        background-color: #F5F5F7; /* Apple Light Grey */
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    }

    /* Card Styling */
    .css-1r6slb0, .stMarkdown, .stText {
        color: #1D1D1F;
    }
    
    div.stButton > button {
        background-color: #0071e3;
        color: white;
        border-radius: 18px;
        padding: 0.5rem 1rem;
        border: none;
        box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        transition: all 0.3s ease;
        font-weight: 500;
        width: 100%;
    }
    
    div.stButton > button:hover {
        background-color: #0077ED;
        transform: scale(1.02);
        box-shadow: 0 4px 8px rgba(0,0,0,0.15);
    }

    /* Custom Card for Results */
    .candidate-card {
        background-color: white;
        padding: 20px;
        border-radius: 16px;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
        margin-bottom: 15px;
        border: 1px solid #E5E5EA;
    }
    
    .match-score {
        font-size: 24px;
        font-weight: 700;
        color: #0071e3;
    }

    /* Input Fields Polish */
    .stTextInput > div > div > input, .stTextArea > div > div > textarea {
        background-color: white;
        border-radius: 12px;
        border: 1px solid #D2D2D7;
    }
    
    /* Remove default Streamlit chrome */
    header {visibility: hidden;}
    footer {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

# --- Logic: Secure API Handling ---
# Try to get API key from Streamlit Secrets first, otherwise ask in Sidebar
try:
    api_key = st.secrets["GOOGLE_API_KEY"]
    has_secret_key = True
except FileNotFoundError:
    api_key = None
    has_secret_key = False

# --- Sidebar ---
with st.sidebar:
    st.title("⚙️ Settings")
    
    if not has_secret_key:
        api_key = st.text_input("Enter Gemini API Key", type="password")
        st.caption("Get your key from Google AI Studio")
    else:
        st.success("✅ API Key loaded securely")

    st.divider()
    model_options = ["gemini-2.5-flash-preview-09-2025", "gemini-1.5-flash"]
    model_name = st.selectbox("Model", model_options)
    n_matches = st.slider("Candidates to find", 1, 20, 3)

# --- Helper Functions ---
def get_gemini_response(input_prompt, pdf_content, job_description):
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(model_name)
        combined_prompt = f"{input_prompt}\n\n### JOB DESCRIPTION:\n{job_description}\n\n### RESUME:\n{pdf_content}"
        response = model.generate_content(combined_prompt)
        return response.text
    except Exception as e:
        return f"Error: {e}"

def input_pdf_text(uploaded_file):
    reader = pdf.PdfReader(uploaded_file)
    text = ""
    for page in reader.pages:
        text += page.extract_text()
    return text

# --- Main UI ---
st.markdown("<h1 style='text-align: center; color: #1D1D1F;'>Resume Matcher Pro</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center; color: #86868b; margin-bottom: 40px;'>Intelligent candidate screening powered by Gemini 2.5</p>", unsafe_allow_html=True)

col1, col2 = st.columns([1, 1], gap="large")

with col1:
    st.markdown("### Job Description")
    jd = st.text_area("Paste JD here", height=300, label_visibility="collapsed", placeholder="Paste the job description here...")

with col2:
    st.markdown("### Upload Resumes")
    uploaded_files = st.file_uploader("Drop PDF files", type=["pdf"], accept_multiple_files=True, label_visibility="collapsed")

# --- Processing ---
if st.button("Analyze Candidates"):
    if not api_key:
        st.error("⚠️ Please provide an API Key.")
    elif not uploaded_files or not jd:
        st.warning("⚠️ Please provide both a JD and Resumes.")
    else:
        
        # Prompt
        input_prompt = """
        You are a strict Technical Recruiter. Evaluate the resume against the JD.
        Return ONLY valid JSON:
        {
            "name": "Candidate Name",
            "score": 85,
            "reason": "Short summary of fit",
            "skills_missing": ["skill1", "skill2"]
        }
        """
        
        results = []
        progress_text = st.empty()
        bar = st.progress(0)
        
        for i, file in enumerate(uploaded_files):
            progress_text.text(f"Analyzing {file.name}...")
            bar.progress((i+1)/len(uploaded_files))
            
            text = input_pdf_text(file)
            
            # Retry logic
            for _ in range(3):
                try:
                    resp = get_gemini_response(input_prompt, text, jd)
                    clean_json = resp.replace("```json", "").replace("```", "").strip()
                    data = json.loads(clean_json)
                    data['file'] = file.name
                    results.append(data)
                    break
                except:
                    time.sleep(1)
            time.sleep(0.5) # Queue throttle

        bar.empty()
        progress_text.empty()
        
        # Sorting
        top_candidates = sorted(results, key=lambda x: x.get('score', 0), reverse=True)[:n_matches]
        
        # --- Results Display (Custom Cards) ---
        st.markdown("---")
        st.markdown(f"<h3 style='text-align: center;'>Top {len(top_candidates)} Matches</h3>", unsafe_allow_html=True)
        
        for rank, cand in enumerate(top_candidates, 1):
            score_color = "#34C759" if cand['score'] >= 80 else "#FF9500" if cand['score'] >= 50 else "#FF3B30"
            
            # HTML Injection for Apple-like Card
            st.markdown(f"""
            <div class="candidate-card">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <div>
                        <h2 style="margin: 0; font-size: 22px;">#{rank} {cand.get('name', 'Unknown')}</h2>
                        <p style="color: #86868b; margin: 4px 0 0 0;">File: {cand.get('file')}</p>
                    </div>
                    <div style="text-align: right;">
                        <span style="font-size: 32px; font-weight: 800; color: {score_color};">{cand.get('score')}%</span>
                        <div style="font-size: 12px; color: #86868b; text-transform: uppercase; letter-spacing: 1px;">Match</div>
                    </div>
                </div>
                <hr style="margin: 15px 0; border: 0; border-top: 1px solid #E5E5EA;">
                <p style="font-size: 15px; line-height: 1.5;"><strong>Analysis:</strong> {cand.get('reason')}</p>
                <p style="font-size: 14px; color: #FF3B30; margin-top: 10px;"><strong>Missing:</strong> {', '.join(cand.get('skills_missing', []))}</p>
            </div>
            """, unsafe_allow_html=True)