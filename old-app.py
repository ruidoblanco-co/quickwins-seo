import streamlit as st
import time
from datetime import datetime
import os
import requests
from bs4 import BeautifulSoup
import google.generativeai as genai

# ===========================
# 🎨 PAGE CONFIGURATION
# ===========================
st.set_page_config(
    page_title="Claudio - Professional SEO Auditor",
    page_icon="👔",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ===========================
# 🔑 API CONFIGURATION
# ===========================
try:
    GEMINI_API_KEY = st.secrets["GOOGLE_API_KEY"]
    genai.configure(api_key=GEMINI_API_KEY)
    GEMINI_AVAILABLE = True
except Exception as e:
    GEMINI_AVAILABLE = False
    st.error(f"⚠️ Gemini API not configured: {e}")

try:
    CLAUDE_API_KEY = st.secrets.get("ANTHROPIC_API_KEY", "")
    CLAUDE_AVAILABLE = bool(CLAUDE_API_KEY)
except:
    CLAUDE_AVAILABLE = False

try:
    AHREFS_API_KEY = st.secrets.get("AHREFS_API_KEY", "")
    AHREFS_AVAILABLE = bool(AHREFS_API_KEY)
except:
    AHREFS_AVAILABLE = False

# ===========================
# 🎨 CUSTOM CSS
# ===========================
st.markdown("""
<style>
    /* Professional dark gray background */
    .stApp {
        background: linear-gradient(135deg, #2b2d42 0%, #1a1b26 100%);
    }
    
    /* Sidebar dark */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #1a1b26 0%, #121318 100%);
    }
    
    /* Metric cards */
    [data-testid="stMetricValue"] {
        font-size: 24px;
        color: #60a5fa;
        font-weight: 600;
    }
    
    [data-testid="stMetricLabel"] {
        color: #94a3b8;
        font-size: 13px;
        font-weight: 500;
    }
    
    /* Custom buttons */
    .stButton>button {
        width: 100%;
        background: linear-gradient(90deg, #60a5fa 0%, #3b82f6 100%);
        color: white;
        font-weight: 600;
        border: none;
        padding: 10px 20px;
        border-radius: 6px;
        font-size: 15px;
        transition: all 0.3s ease;
    }
    
    .stButton>button:hover {
        transform: translateY(-1px);
        box-shadow: 0 6px 12px rgba(96, 165, 250, 0.3);
    }
    
    /* Inputs */
    .stTextInput>div>div>input {
        background-color: rgba(255, 255, 255, 0.05);
        color: white;
        border: 1px solid rgba(96, 165, 250, 0.3);
        border-radius: 6px;
        padding: 8px;
        font-size: 14px;
    }
    
    .stTextInput>div>div>input:focus {
        border-color: #60a5fa;
        box-shadow: 0 0 0 2px rgba(96, 165, 250, 0.2);
    }
    
    /* Selectbox */
    .stSelectbox>div>div>div {
        background-color: rgba(255, 255, 255, 0.05);
        color: white;
        border-radius: 6px;
        font-size: 14px;
    }
    
    /* Radio buttons */
    .stRadio>div {
        background-color: rgba(255, 255, 255, 0.03);
        padding: 12px;
        border-radius: 6px;
        border: 1px solid rgba(96, 165, 250, 0.2);
    }
    
    /* Info boxes */
    .stAlert {
        background-color: rgba(96, 165, 250, 0.1);
        border-left: 3px solid #60a5fa;
        border-radius: 4px;
    }
    
    /* Titles */
    h1 {
        color: #60a5fa;
        font-weight: 700;
    }
    
    h2, h3 {
        color: #e2e8f0;
    }
    
    /* Header logo and title */
    .claudio-header {
        text-align: center;
        padding: 20px 0 30px 0;
        margin-bottom: 30px;
        border-bottom: 2px solid rgba(96, 165, 250, 0.2);
    }
    
    .claudio-avatar-large {
        width: 100px;
        height: 100px;
        border-radius: 50%;
        background: linear-gradient(135deg, #8B4513 0%, #654321 100%);
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 50px;
        margin: 0 auto 15px;
        border: 4px solid #60a5fa;
        box-shadow: 0 4px 12px rgba(96, 165, 250, 0.3);
    }
    
    .claudio-title {
        font-size: 42px;
        font-weight: 700;
        color: #60a5fa;
        margin: 10px 0 5px 0;
        letter-spacing: -1px;
    }
    
    .claudio-subtitle {
        font-size: 18px;
        color: #94a3b8;
        font-weight: 400;
    }
    
    /* Status badges */
    .status-badge {
        display: inline-block;
        padding: 4px 12px;
        border-radius: 12px;
        font-size: 12px;
        font-weight: 600;
        margin: 4px;
    }
    
    .status-connected {
        background-color: rgba(34, 197, 94, 0.2);
        color: #22c55e;
        border: 1px solid #22c55e;
    }
    
    .status-disconnected {
        background-color: rgba(239, 68, 68, 0.2);
        color: #ef4444;
        border: 1px solid #ef4444;
    }
    
    .status-optional {
        background-color: rgba(251, 191, 36, 0.2);
        color: #fbbf24;
        border: 1px solid #fbbf24;
    }
    
    /* Audit report styling */
    .audit-report {
        background-color: rgba(255, 255, 255, 0.03);
        padding: 30px;
        border-radius: 8px;
        border: 1px solid rgba(96, 165, 250, 0.2);
        line-height: 1.8;
    }
    
    .audit-report h1 {
        color: #60a5fa;
        border-bottom: 2px solid rgba(96, 165, 250, 0.3);
        padding-bottom: 10px;
        margin-bottom: 20px;
    }
    
    .audit-report h2 {
        color: #93c5fd;
        margin-top: 30px;
        margin-bottom: 15px;
    }
    
    .audit-report h3 {
        color: #bfdbfe;
        margin-top: 20px;
        margin-bottom: 10px;
    }
    
    .audit-report ul, .audit-report ol {
        margin-left: 20px;
    }
    
    .audit-report li {
        margin-bottom: 8px;
    }
    
    .audit-report hr {
        border: none;
        border-top: 1px solid rgba(96, 165, 250, 0.2);
        margin: 25px 0;
    }
    
    .audit-report strong {
        color: #dbeafe;
    }
    
    /* Labels more subtle */
    .stRadio label, .stSelectbox label {
        font-size: 13px;
        color: #94a3b8;
        font-weight: 500;
    }
</style>
""", unsafe_allow_html=True)

# ===========================
# 🔍 WEB ANALYSIS FUNCTIONS
# ===========================
def analyze_basic_site(url):
    """Analyzes the website extracting basic information from HTML"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Extract information
        analysis = {
            'url': url,
            'status_code': response.status_code,
            'title': soup.title.string if soup.title else 'No title found',
            'meta_description': '',
            'h1_tags': [],
            'h2_tags': [],
            'images_without_alt': 0,
            'total_images': 0,
            'internal_links': 0,
            'external_links': 0,
            'word_count': 0
        }
        
        # Meta description
        meta_desc = soup.find('meta', attrs={'name': 'description'})
        if meta_desc:
            analysis['meta_description'] = meta_desc.get('content', '')
        
        # H1 and H2
        analysis['h1_tags'] = [h1.get_text().strip() for h1 in soup.find_all('h1')]
        analysis['h2_tags'] = [h2.get_text().strip() for h2 in soup.find_all('h2')][:5]  # First 5
        
        # Images
        images = soup.find_all('img')
        analysis['total_images'] = len(images)
        analysis['images_without_alt'] = len([img for img in images if not img.get('alt')])
        
        # Links
        links = soup.find_all('a', href=True)
        for link in links:
            href = link['href']
            if href.startswith('http') and url not in href:
                analysis['external_links'] += 1
            elif href.startswith('/') or url in href:
                analysis['internal_links'] += 1
        
        # Word count
        text = soup.get_text()
        analysis['word_count'] = len(text.split())
        
        return analysis
        
    except Exception as e:
        return {'error': str(e)}

# ===========================
# 🤖 AI FUNCTIONS
# ===========================
def generate_audit_with_gemini(url, site_data, audit_type):
    """Generates audit using Gemini"""
    
    try:
        model = genai.GenerativeModel("gemini-2.0-flash-exp")
        
        # Prepare prompt according to type
        if audit_type == "Basic":
            prompt = f"""
You are Claudio, an expert professional SEO auditor. Analyze the following website and generate a complete and professional BASIC SEO audit.

**SITE DATA:**
URL: {site_data.get('url', url)}
Title: {site_data.get('title', 'N/A')}
Meta Description: {site_data.get('meta_description', 'No meta description found')}
H1 Tags: {', '.join(site_data.get('h1_tags', [])) if site_data.get('h1_tags') else 'None found'}
H2 Tags (first 5): {', '.join(site_data.get('h2_tags', []))}
Total Images: {site_data.get('total_images', 0)}
Images without ALT: {site_data.get('images_without_alt', 0)}
Internal Links: {site_data.get('internal_links', 0)}
External Links: {site_data.get('external_links', 0)}
Total Words: {site_data.get('word_count', 0)}

**INSTRUCTIONS:**
Generate a professional SEO audit report following EXACTLY this structure:

# 📊 Basic SEO Audit - [Site Name]

## 🎯 Executive Summary

**Overall Score**: [X]/100

[2-3 paragraph summary about the general state of the site]

### Key Findings:
- ✅ **Strengths**: [List 2-3 strong points]
- ⚠️ **Opportunities**: [List 2-3 areas for improvement]
- 🔴 **Critical**: [List 1-2 urgent issues]

---

## 🔍 Technical SEO Analysis

### Meta Tags
- **Title Tag**: [Analysis of title - length, keywords, optimization]
- **Meta Description**: [Analysis - exists, length, call to action]
- **Open Graph**: [If detected or recommend implementation]

### Content Structure
- **H1**: [Analysis of found H1s]
- **H2-H6**: [Hierarchy analysis]
- **Content Density**: [Analysis based on word count]

### Image Optimization
- Total images: {site_data.get('total_images', 0)}
- Without ALT attribute: {site_data.get('images_without_alt', 0)}
- [Specific recommendations]

### Link Architecture
- Internal links: {site_data.get('internal_links', 0)}
- External links: {site_data.get('external_links', 0)}
- [Linking strategy analysis]

---

## 📋 Prioritized Action Plan

### 🔴 CRITICAL (Do immediately)
1. **[Action Title]**
   - Description: [What to do]
   - Effort: [X] hours
   - Impact: High/Medium/Low
   - Action: [Specific steps]

[Continue with 2-3 more critical actions]

### 🟡 HIGH PRIORITY (Next 1-2 weeks)
[List 3-4 high priority actions with same format]

### 🟢 MEDIUM PRIORITY (Month 1-2)
[List 2-3 medium priority actions]

---

## 🎯 Strategic Recommendations

[2-3 paragraphs with general strategic recommendations based on the analysis]

---

**Analysis Type**: Basic (Visual)
**Generated by**: Gemini 2.0 Flash
**Date**: {datetime.now().strftime("%m/%d/%Y %H:%M")}

IMPORTANT: 
- Be specific and professional
- Base EVERYTHING on the provided data
- If something is missing, indicate it as an improvement opportunity
- Number all actions
- Use emojis only where indicated in the structure
- Generate the ENTIRE audit in ENGLISH language
"""
        else:  # Full
            prompt = f"""
You are Claudio, an expert professional SEO auditor. Generate an ultra-professional COMPLETE SEO audit.

**BASIC SITE DATA:**
{site_data}

**NOTE**: This is a FULL audit but we don't have Ahrefs API data yet. 
For now, generate the audit with available data and add sections that SHOULD include Ahrefs data
clearly indicating that this data will be added when the API is connected.

Follow the same structure as Basic but add these sections:

## 📊 Authority Metrics (Pending Ahrefs API)
[Explain what metrics will be shown here: DR, backlinks, referring domains, etc.]

## 🔗 Backlink Profile (Pending Ahrefs API)
[Explain what analysis will be done here]

## 📈 Organic Performance (Pending Ahrefs API)
[Explain what keyword and traffic data will be shown]

Generate the rest of the analysis based on available data.

**Date**: {datetime.now().strftime("%m/%d/%Y %H:%M")}

IMPORTANT: Generate the ENTIRE audit in ENGLISH language.
"""
        
        # Generate content
        response = model.generate_content(prompt)
        return response.text
        
    except Exception as e:
        return f"❌ Error generating audit with Gemini: {str(e)}"

# ===========================
# 🎨 SIDEBAR - STATUS
# ===========================
with st.sidebar:
    st.markdown("### 🏢 System Status")
    
    if GEMINI_AVAILABLE:
        st.markdown('<span class="status-badge status-connected">🟢 Gemini Connected</span>', unsafe_allow_html=True)
    else:
        st.markdown('<span class="status-badge status-disconnected">🔴 Gemini Offline</span>', unsafe_allow_html=True)
    
    if CLAUDE_AVAILABLE:
        st.markdown('<span class="status-badge status-connected">🟢 Claude Connected</span>', unsafe_allow_html=True)
    else:
        st.markdown('<span class="status-badge status-disconnected">🔴 Claude Offline</span>', unsafe_allow_html=True)
    
    if AHREFS_AVAILABLE:
        st.markdown('<span class="status-badge status-connected">🟢 Ahrefs Connected</span>', unsafe_allow_html=True)
    else:
        st.markdown('<span class="status-badge status-optional">⚠️ Ahrefs Optional</span>', unsafe_allow_html=True)
    
    st.markdown("---")
    
    st.markdown("### ℹ️ About")
    st.markdown("""
    **Claudio** generates professional SEO audits in seconds.
    
    **Features**:
    - 🔍 Basic visual analysis
    - 💎 Full analysis with Ahrefs
    - 🤖 Multiple AI models
    - 📄 Professional reports
    """)
    
    st.markdown("---")
    st.caption("v2.0 - Professional Edition")

# ===========================
# 🎯 MAIN INTERFACE
# ===========================

# Header with logo
st.markdown("""
<div class="claudio-header">
    <div class="claudio-avatar-large">👔</div>
    <div class="claudio-title">CLAUDIO</div>
    <div class="claudio-subtitle">Professional SEO Auditor</div>
</div>
""", unsafe_allow_html=True)

# ===========================
# 🎛️ CONFIGURATION
# ===========================

col1, col2 = st.columns([2, 1])

with col1:
    audit_type = st.radio(
        "Audit Type",
        ["🔍 Basic (Visual Analysis)", "💎 Full (With Ahrefs Data)"],
        help="Basic: Quick visual analysis\nFull: Complete analysis with Ahrefs metrics"
    )

with col2:
    if "Full" in audit_type:
        st.info("**Full Audit**\n\n✓ Domain Rating\n✓ Backlinks\n✓ Keywords\n✓ Traffic data")
    else:
        st.info("**Basic Audit**\n\n✓ Technical SEO\n✓ On-page analysis\n✓ Content review")

st.markdown("---")

# AI Model selector (compact)
col1, col2 = st.columns([3, 1])

with col1:
    # Filter models according to availability
    available_models = []
    
    if GEMINI_AVAILABLE:
        available_models.append("⚡ Gemini 2.0 Flash")
    
    if CLAUDE_AVAILABLE:
        available_models.extend([
            "🎯 Claude Sonnet 4.5",
            "👑 Claude Opus 4.5"
        ])
    
    if not available_models:
        st.error("❌ No AI models configured. Please add API keys in Streamlit Secrets.")
        st.stop()
    
    selected_model = st.selectbox(
        "AI Model",
        available_models,
        help="Choose the AI model for analysis"
    )

st.markdown("---")

# URL Input (compact)
url_input = st.text_input(
    "Website URL",
    placeholder="https://example.com",
    help="Enter the full URL including https://"
)

# Confirmation for Full Audit
if "Full" in audit_type:
    if AHREFS_AVAILABLE:
        st.warning("⚠️ Full Audit will use Ahrefs API credits")
        confirm_ahrefs = st.checkbox("✓ Confirm Ahrefs API usage", value=False)
    else:
        st.warning("⚠️ Ahrefs API not configured. Full audit will generate report structure without Ahrefs data.")
        confirm_ahrefs = True
else:
    confirm_ahrefs = True

st.markdown("---")

# ===========================
# 🚀 AUDIT BUTTON
# ===========================

col1, col2, col3 = st.columns([1, 2, 1])

with col2:
    button_disabled = not url_input or not confirm_ahrefs
    
    if st.button("🚀 Generate Audit", disabled=button_disabled, use_container_width=True):
        
        if not url_input:
            st.error("❌ Please enter a URL")
        elif "Full" in audit_type and AHREFS_AVAILABLE and not confirm_ahrefs:
            st.error("❌ Please confirm Ahrefs API usage")
        else:
            st.markdown("---")
            
            # Progress bar
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            # Step 1: Analyze site
            status_text.text("🔍 Analyzing website...")
            progress_bar.progress(30)
            site_data = analyze_basic_site(url_input)
            time.sleep(1)
            
            if 'error' in site_data:
                st.error(f"❌ Error analyzing website: {site_data['error']}")
                st.stop()
            
            # Step 2: Generate with AI
            status_text.text("🤖 Generating audit with AI...")
            progress_bar.progress(60)
            
            type_audit = "Basic" if "Basic" in audit_type else "Full"
            
            # For now only Gemini is implemented
            if "Gemini" in selected_model:
                result = generate_audit_with_gemini(url_input, site_data, type_audit)
            else:
                st.warning("⚠️ Claude implementation coming soon. Using Gemini for now.")
                result = generate_audit_with_gemini(url_input, site_data, type_audit)
            
            progress_bar.progress(100)
            status_text.text("✅ Audit completed!")
            time.sleep(0.5)
            
            progress_bar.empty()
            status_text.empty()
            
            # Show result
            st.markdown("---")
            st.success("✅ Audit completed successfully!")
            
            # Tabs to organize results
            tab1, tab2 = st.tabs(["📄 Full Report", "📥 Download"])
            
            with tab1:
                st.markdown('<div class="audit-report">', unsafe_allow_html=True)
                st.markdown(result)
                st.markdown('</div>', unsafe_allow_html=True)
            
            with tab2:
                st.markdown("### Download Options")
                
                col1, col2 = st.columns(2)
                
                with col1:
                    st.markdown("#### 📄 Word Document")
                    st.info("""
                    **Includes**:
                    - Executive Summary
                    - Complete Analysis
                    - Recommendations
                    - Professional Format
                    """)
                    st.button("📥 Download .docx", disabled=True, help="Coming soon!")
                
                with col2:
                    st.markdown("#### 📊 Excel Spreadsheet")
                    st.info("""
                    **Includes**:
                    - Prioritized Tasks
                    - Technical Issues
                    - SEO Opportunities
                    - Tracking Checkboxes
                    """)
                    st.button("📥 Download .xlsx", disabled=True, help="Coming soon!")
                
                st.markdown("---")
                st.caption("*Document generation will be enabled soon*")

# ===========================
# 📊 FOOTER
# ===========================

st.markdown("---")
col1, col2, col3 = st.columns(3)

with col1:
    st.markdown("**Claudio SEO Auditor**")
    st.caption("Professional audits in seconds")

with col2:
    st.markdown("**Powered by**")
    st.caption("Anthropic • Google • Ahrefs")

with col3:
    st.markdown("**Need help?**")
    st.caption("[Documentation](#) • [Support](#)")
