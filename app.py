import streamlit as st
import google.generativeai as genai
import PyPDF2 as pdf
from PIL import Image
import json
import time
import io
import base64

# --- Page Config ---
st.set_page_config(page_title="ATS Scanner", layout="wide", initial_sidebar_state="expanded")

# --- CSS for PDF Preview & Clean UI ---
st.markdown("""
<style>
    .stProgress > div > div > div > div {
        background-color: #00FF00;
    }
    iframe {
        width: 100%;
        min-height: 800px;
        border: 1px solid #444;
        border-radius: 5px;
    }
</style>
""", unsafe_allow_html=True)

# --- API Handling ---
# Try secrets first, then sidebar
api_key = st.secrets.get("GOOGLE_API_KEY")

with st.sidebar:
    st.title("🔧 Configuration")
    if not api_key:
        api_key = st.text_input("Gemini API Key", type="password")
    
    model_name = st.selectbox("Model", ["gemini-2.5-flash-preview-09-2025", "gemini-1.5-flash", "gemini-1.5-pro"])
    n_matches = st.number_input("Top N Candidates", min_value=1, value=3)
    st.info("Supported: PDF, JPG, PNG")

# --- Helper Functions ---

def get_gemini_response(input_prompt, content, job_description, is_image=False):
    """
    Handles both Text (PDF) and Image (JPG/PNG) inputs for Gemini.
    """
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(model_name)
        
        # Structure the payload based on input type
        if is_image:
            # content is a PIL Image object
            prompt_parts = [input_prompt, "\n\n### JOB DESCRIPTION:\n", job_description, "\n\n### RESUME IMAGE:\n", content]
        else:
            # content is text string
            prompt_parts = [input_prompt, "\n\n### JOB DESCRIPTION:\n", job_description, "\n\n### RESUME TEXT:\n", content]
            
        response = model.generate_content(prompt_parts)
        return response.text
    except Exception as e:
        return f"Error: {e}"

def extract_pdf_text(uploaded_file):
    reader = pdf.PdfReader(uploaded_file)
    text = ""
    for page in reader.pages:
        text += page.extract_text()
    return text

def pdf_to_base64(uploaded_file):
    """Converts PDF to base64 for embedding in iframe"""
    bytes_data = uploaded_file.getvalue()
    base64_pdf = base64.b64encode(bytes_data).decode('utf-8')
    return f'<iframe src="data:application/pdf;base64,{base64_pdf}" type="application/pdf"></iframe>'

# --- Main Interface ---

st.header("ATS Resume Matcher & Viewer")

col_jd, col_upload = st.columns([1, 1])

with col_jd:
    jd = st.text_area("1. Job Description", height=200, placeholder="Paste JD here...")

with col_upload:
    uploaded_files = st.file_uploader("2. Upload Resumes", type=["pdf", "jpg", "jpeg", "png"], accept_multiple_files=True)

# --- Logic ---

if st.button("Analyze Resumes", type="primary"):
    if not api_key or not uploaded_files or not jd:
        st.error("Missing API Key, JD, or Resumes.")
    else:
        
        # Strict JSON Prompt
        input_prompt = """
        You are a high-precision ATS. Analyze the resume against the JD.
        Output ONLY raw JSON. No Markdown. No ```json.
        Structure:
        {
            "name": "Candidate Name",
            "match_score": 85,
            "summary": "Direct, brutal assessment of fit.",
            "missing_skills": ["skill1", "skill2"],
            "experience_years": 5
        }
        """
        
        results = []
        progress_text = st.empty()
        progress_bar = st.progress(0)
        
        # --- Queue Processing ---
        for idx, file in enumerate(uploaded_files):
            progress_text.text(f"Processing {idx+1}/{len(uploaded_files)}: {file.name}")
            progress_bar.progress((idx + 1) / len(uploaded_files))
            
            file_data = None
            is_image = False
            
            # Detect Type
            if file.type == "application/pdf":
                file_data = extract_pdf_text(file)
                is_image = False
            else:
                # Handle Images (JPG/PNG)
                file_data = Image.open(file)
                is_image = True
            
            # API Call with Retry
            for attempt in range(3):
                try:
                    resp = get_gemini_response(input_prompt, file_data, jd, is_image=is_image)
                    clean_json = resp.replace("```json", "").replace("```", "").strip()
                    data = json.loads(clean_json)
                    
                    # Attach file object for preview later
                    data['file_obj'] = file 
                    data['file_type'] = file.type
                    results.append(data)
                    break
                except Exception as e:
                    time.sleep(1)
            
            time.sleep(0.5) # Rate limit buffer

        progress_text.empty()
        progress_bar.empty()
        
        # --- Display Results ---
        
        # Sort by Score (High to Low)
        results.sort(key=lambda x: x.get('match_score', 0), reverse=True)
        top_n = results[:n_matches]
        
        st.divider()
        st.subheader(f"Top {len(top_n)} Candidates")
        
        for rank, cand in enumerate(top_n, 1):
            score = cand.get('match_score', 0)
            color = "green" if score > 75 else "orange" if score > 50 else "red"
            
            with st.expander(f"#{rank} | {cand.get('name')} | Match: {score}%", expanded=False):
                
                # Split View: Analysis vs Preview
                c1, c2 = st.columns([1, 1])
                
                with c1:
                    st.markdown(f"### Analysis")
                    st.markdown(f"**Score:** :{color}[{score}%]")
                    st.markdown(f"**Experience:** {cand.get('experience_years')} years")
                    st.error(f"**Missing:** {', '.join(cand.get('missing_skills', []))}")
                    st.info(f"**Summary:** {cand.get('summary')}")
                
                with c2:
                    st.markdown("### Document Preview")
                    f_obj = cand['file_obj']
                    f_type = cand['file_type']
                    
                    if f_type == "application/pdf":
                        # Embed PDF
                        st.markdown(pdf_to_base64(f_obj), unsafe_allow_html=True)
                    else:
                        # Display Image
                        st.image(f_obj, use_container_width=True)
