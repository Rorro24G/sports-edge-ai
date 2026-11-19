"""Six-node brain portal and seamless navigation between live Streamlit sections."""
from pathlib import Path
import streamlit as st
import streamlit.components.v1 as components

from .section_design import inject_theme, render_hero

SECTIONS = {
    "picks": "Picks", "parlays": "Parlays", "noticias": "Noticias",
    "simulaciones": "Simulaciones", "historial": "Historial",
    "calendario": "Calendario",
}

# Portal itself remains versioned; this redesign changes Streamlit page chrome.
portal = components.declare_component(
    "sports_brain_portal_motion_v10",
    path=str(Path(__file__).resolve().parents[1] / "web" / "brain_portal"),
)


def _navigate(target: str | None) -> None:
    """A changed transition token restarts the CSS tunnel when switching tabs."""
    st.session_state["brain_section"] = target
    st.session_state["brain_entered"] = True
    st.session_state["brain_transition_seq"] = (
        st.session_state.get("brain_transition_seq", 0) + 1
    )
    if target is None:
        st.session_state["brain_visit"] = st.session_state.get("brain_visit", 0) + 1
    st.rerun()


def render_navigation():
    section = st.session_state.get("brain_section")
    if section not in (*SECTIONS, "asistente", "estado"):
        value = portal(
            skip_intro=st.session_state.get("brain_entered", False),
            key="brain_portal_motion_v10_" + str(st.session_state.get("brain_visit", 0)),
            default=None,
        )
        if isinstance(value, dict) and value.get("page") in SECTIONS:
            _navigate(value["page"])
        with st.expander("Explorar secciones", expanded=False):
            choices = st.columns(3)
            for i, (key, label) in enumerate(SECTIONS.items()):
                if choices[i % 3].button(
                    label, key="direct_" + key, use_container_width=True
                ):
                    _navigate(key)
        st.stop()

    seq = st.session_state.get("brain_transition_seq", 0)
    variant = "a" if seq % 2 == 0 else "b"
    # The old portal iframe flies toward the selected node; the following
    # Streamlit overlay finishes that same motion as the page is mounted.
    st.html(
        '<div class="brain-page-entry brain-page-entry--' + variant
        + '" data-transition="' + str(seq) + '" aria-hidden="true"></div>'
    )

    left, middle, right = st.columns([2.0, 5.5, 2.0], vertical_alignment="center")
    if left.button("← Cerebro", key="back_to_brain", use_container_width=True):
        _navigate(None)
    middle.markdown(
        '<div class="section-brand">◈ SPORTS EDGE AI'
        ' <span>/ ' + SECTIONS.get(section, section.title()) + '</span></div>',
        unsafe_allow_html=True,
    )
    if right.button("✦ Asistente", key="open_assistant", use_container_width=True):
        _navigate("asistente")

    # Direct navigation avoids returning to the six-node portal on every tab.
    buttons = st.columns(6, gap="small")
    for i, (key, label) in enumerate(SECTIONS.items()):
        if buttons[i].button(
            label, key="section_nav_" + key, use_container_width=True,
            type="primary" if section == key else "secondary",
        ) and section != key:
            _navigate(key)

    render_hero(section)
    return section


def apply_theme():
    inject_theme()
