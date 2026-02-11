"""Global CSS for the Fraud Investigation Dashboard."""


def get_app_css() -> str:
    """Return the full <style>...</style> markdown string for st.markdown(..., unsafe_allow_html=True)."""
    return """
<style>
  /* Base app background */
  .stApp {
    background: #0d1117;
    min-height: 100vh;
  }
  /* Right side (main content) – diagonal gradient + soft amber & rose orbs */
  main, [data-testid="stAppViewContainer"] > section, [data-testid="stAppViewContainer"] > div:last-child {
    background: radial-gradient(ellipse 100% 70% at 15% 20%, rgba(251, 191, 36, 0.07) 0%, transparent 50%),
                radial-gradient(ellipse 90% 60% at 90% 80%, rgba(244, 114, 182, 0.06) 0%, transparent 45%),
                linear-gradient(145deg, #0f1419 0%, #171a1f 35%, #1c1917 70%, #141a22 100%);
    min-height: 100vh;
  }
  /* Sidebar – previous colour: soft blue/green ambient gradient (as before right-side-only change) */
  [data-testid="stSidebar"] {
    background: radial-gradient(ellipse 90% 60% at 75% 15%, rgba(56, 139, 253, 0.035) 0%, transparent 50%),
                radial-gradient(ellipse 70% 50% at 15% 85%, rgba(46, 213, 115, 0.025) 0%, transparent 50%),
                linear-gradient(165deg, #0d1117 0%, #161b22 45%, #1c2128 100%);
    border-right: 1px solid rgba(48, 54, 61, 0.6);
  }
  [data-testid="stSidebar"] .stMarkdown { color: #e6edf3; }
  /* Cards – frosted feel, softer shadow, larger radius */
  .fraud-card {
    background: rgba(22, 27, 34, 0.88);
    border: 1px solid rgba(48, 54, 61, 0.7);
    border-radius: 16px;
    padding: 1.35rem 1.6rem;
    margin: 0.85rem 0;
    box-shadow: 0 4px 24px rgba(0, 0, 0, 0.25), 0 1px 0 rgba(255, 255, 255, 0.03) inset;
    transition: box-shadow 0.2s ease, border-color 0.2s ease;
  }
  .fraud-card:hover { box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3), 0 1px 0 rgba(255, 255, 255, 0.04) inset; }
  .fraud-card-title {
    font-size: 0.8rem; font-weight: 600; color: #8b949e;
    letter-spacing: 0.06em; text-transform: uppercase; margin-bottom: 0.5rem;
  }
  .fraud-metric-value { font-size: 1.75rem; font-weight: 700; letter-spacing: -0.02em; }
  /* Headers */
  h1, h2, h3 { color: #e6edf3 !important; font-weight: 600 !important; }
  .hero-title {
    font-size: 2rem; font-weight: 700; color: #e6edf3;
    letter-spacing: -0.03em; margin-top: 0; margin-bottom: 0.25rem !important;
    text-shadow: 0 1px 2px rgba(0, 0, 0, 0.2);
  }
  .hero-sub {
    font-size: 0.95rem; color: #8b949e; margin-top: 0; margin-bottom: 1.5rem !important;
    letter-spacing: 0.01em;
  }
  hr { border-color: rgba(48, 54, 61, 0.8) !important; opacity: 0.9; }
  /* Buttons – smooth radius, clear hover, no awkward wrap; action row buttons fill column */
  .stButton > button {
    border-radius: 12px;
    font-weight: 600;
    transition: transform 0.2s ease, box-shadow 0.2s ease, background 0.2s ease;
    white-space: nowrap;
    min-width: min(100%, 8rem);
    width: 100%;
  }
  .stButton > button:hover {
    transform: translateY(-2px);
    box-shadow: 0 6px 20px rgba(0, 0, 0, 0.35);
  }
  .stButton > button:active { transform: translateY(0); }
  /* Primary (e.g. Risk toggle) – slightly lifted */
  .stButton > button[kind="primary"] {
    box-shadow: 0 2px 12px rgba(0, 0, 0, 0.25);
  }
  /* Metrics */
  [data-testid="stMetricValue"] { font-size: 1.4rem !important; font-weight: 700 !important; color: #e6edf3 !important; }
  [data-testid="stMetricLabel"] { color: #8b949e !important; }
  /* Tabs – pill style, more padding/gap so labels aren't cramped */
  .stTabs [data-baseweb="tab-list"] {
    background: rgba(33, 38, 45, 0.9);
    border-radius: 12px;
    padding: 10px 14px;
    gap: 12px;
    border: 1px solid rgba(48, 54, 61, 0.5);
  }
  .stTabs [data-baseweb="tab"] {
    background: transparent;
    border-radius: 10px;
    color: #8b949e;
    padding: 8px 16px;
    min-height: 2.5rem;
    transition: background 0.2s ease, color 0.2s ease;
  }
  .stTabs [aria-selected="true"] {
    background: rgba(48, 54, 61, 0.8) !important;
    color: #e6edf3 !important;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.2);
  }
  /* Space between tab bar and tab content */
  .stTabs [data-baseweb="tab-panel"] {
    padding-top: 1.25rem;
  }
  /* Expanders */
  .streamlit-expanderHeader {
    background: rgba(33, 38, 45, 0.8);
    border-radius: 10px;
    border: 1px solid rgba(48, 54, 61, 0.4);
  }
  /* DataFrames */
  .stDataFrame {
    border-radius: 12px;
    overflow: hidden;
    border: 1px solid rgba(48, 54, 61, 0.6);
    box-shadow: 0 2px 12px rgba(0, 0, 0, 0.15);
  }
  /* Section labels – more space below so content isn't cramped */
  .section-label {
    font-size: 0.8rem; font-weight: 600; color: #8b949e;
    letter-spacing: 0.05em; text-transform: uppercase;
    margin-bottom: 0.85rem;
  }
  /* Selectbox / inputs – rounded, subtle border */
  .stSelectbox > div, [data-testid="stSelectbox"] > div {
    border-radius: 10px;
  }
  /* Block container – enough top padding so "Internal use" and hero are not cut off */
  .block-container { padding-top: 2.75rem; padding-bottom: 2rem; }
  /* Main content view – extra top space to avoid clipping */
  [data-testid="stAppViewContainer"] { padding-top: 0.75rem; }
</style>
"""
