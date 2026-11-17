"""Six-node wireframe portal connected to real Streamlit sections."""
from pathlib import Path
import streamlit as st
import streamlit.components.v1 as components

SECTIONS = {"picks": "Picks", "parlays": "Parlays", "noticias": "Noticias",
            "simulaciones": "Simulaciones", "historial": "Mi historial", "calendario": "Calendario"}
portal = components.declare_component("sports_brain_portal", path=str(Path(__file__).resolve().parents[1] / "web" / "brain_portal"))


def render_navigation():
    section = st.session_state.get("brain_section")
    if section not in (*SECTIONS, "asistente", "estado"):
        value = portal(skip_intro=st.session_state.get("brain_entered", False),
                       key="brain_portal_" + str(st.session_state.get("brain_visit", 0)), default=None)
        if isinstance(value, dict) and value.get("page") in SECTIONS:
            st.session_state["brain_section"] = value["page"]
            st.session_state["brain_entered"] = True
            st.rerun()
        with st.expander("Navegación directa · sin animación"):
            choices = st.columns(3)
            for i, (key, label) in enumerate(SECTIONS.items()):
                if choices[i % 3].button(label, key="direct_" + key, use_container_width=True):
                    st.session_state["brain_section"] = key
                    st.session_state["brain_entered"] = True
                    st.rerun()
        st.stop()
    left, middle, right = st.columns([2, 6, 2])
    if left.button("← Cerebro", key="back_to_brain"):
        st.session_state["brain_section"] = None
        st.session_state["brain_visit"] = st.session_state.get("brain_visit", 0) + 1
        st.rerun()
    middle.markdown('<div class="section-brand">SPORTS EDGE AI <span>/ ' + SECTIONS.get(section, section.title()) + '</span></div>', unsafe_allow_html=True)
    if right.button("Asistente", key="open_assistant"):
        st.session_state["brain_section"] = "asistente"
        st.rerun()
    return section


def apply_theme():
    st.markdown('''<style>
    :root{--neon:#ff5365;--neon-light:#ff8a96}
    .stApp,[data-testid="stHeader"]{background:#050506!important;color:#f4f0f2!important}
    .block-container{max-width:1260px;padding-top:1.3rem;padding-bottom:2rem}
    h1,h2,h3,h4{color:#ff7184!important;letter-spacing:-.025em;text-shadow:0 0 7px #ff53657f,0 0 22px #ff53653d;animation:heading-glow 5.8s ease-in-out infinite}
    p,label,.stMarkdown{color:#f1ecee}a{color:#ff8a96!important}
    .section-brand{font-weight:900;letter-spacing:.14em;color:#ff7e90;font-size:15px;padding:10px 0;text-align:center;text-shadow:0 0 10px #ff5365b0,0 0 32px #ff53654d;animation:section-neon 5s ease-in-out infinite}
    .section-brand span{font-weight:400;color:#d2b7bd;letter-spacing:.04em}
    [data-testid="stMetric"]{background:#120a0d;border:1px solid #54252f;border-radius:12px;padding:1rem}
    [data-testid="stMetricValue"]{color:#fff}
    [data-testid="stForm"], [data-testid="stExpander"]{background:#0d080b;border-color:#49212b!important;border-radius:12px}
    [data-testid="stTextInput"] input,[data-testid="stTextArea"] textarea{background:#100b0d;color:#fff;caret-color:#ff6375}
    button[kind="primary"],div.stFormSubmitButton>button{background:#ff6375!important;color:#160609!important;border:0!important;border-radius:10px!important;box-shadow:0 0 13px #ff536544;animation:button-breathe 3.9s ease-in-out infinite;transition:transform .2s ease,box-shadow .2s ease}
    button[kind="secondary"]{border-color:#66303b!important;background:#11090d!important;color:#ff8a96!important;transition:transform .2s ease,box-shadow .2s ease}
    button[kind="primary"]:hover,div.stFormSubmitButton>button:hover,button[kind="secondary"]:hover{transform:translateY(-2px);box-shadow:0 0 20px #ff53658c}
    [data-testid="stDataFrame"]{border:1px solid #42232a;border-radius:10px}
    .odds-price{color:#76f5a6;font-variant-numeric:tabular-nums;font-weight:800}
    @keyframes section-arrive{from{opacity:0;transform:translateY(12px)}to{opacity:1;transform:translateY(0)}}
    @keyframes heading-glow{0%,100%{text-shadow:0 0 7px #ff53657f,0 0 22px #ff53653d}50%{text-shadow:0 0 12px #ff8195d1,0 0 32px #ff53657e}}
    @keyframes section-neon{0%,100%{transform:translateY(0);text-shadow:0 0 10px #ff5365b0,0 0 32px #ff53654d}50%{transform:translateY(-2px);text-shadow:0 0 14px #ffb4bd,0 0 42px #ff536592}}
    @keyframes button-breathe{0%,100%{box-shadow:0 0 13px #ff536544}50%{box-shadow:0 0 23px #ff53658c}}
    .block-container{animation:section-arrive .45s ease-out}
    @media(prefers-reduced-motion:reduce){.block-container,h1,h2,h3,h4,.section-brand,button[kind="primary"],div.stFormSubmitButton>button{animation:none!important}
      button[kind="primary"],div.stFormSubmitButton>button,button[kind="secondary"]{transition:none!important}}
    @media(max-width:640px){.section-brand{font-size:11px;letter-spacing:.05em}.section-brand span{display:block;font-size:10px}}
    </style>''', unsafe_allow_html=True)
