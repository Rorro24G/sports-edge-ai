"""Visual system for the Sports Edge AI Streamlit sections.

HTML in the hero is fixed, internal text only. Dynamic ESPN/user content is
rendered through Streamlit widgets, not interpolated into raw HTML.
"""
from __future__ import annotations

import html
import streamlit as st

SECTION_INFO = {
    "picks": (
        "01 / INTELLIGENCE DESK", "Decisiones con evidencia.",
        "El cerebro analiza los partidos por sí mismo. ESPN aporta resultados; "
        "Covers únicamente sirve para consultar momios.",
        ("ANÁLISIS PROPIO", "NBA · NFL · NHL", "SIN PICKS FORZADOS"),
        "◈",
    ),
    "parlays": (
        "02 / COMBINATION STUDIO", "Combina con criterio.",
        "Explora escenarios y sus riesgos antes de combinar selecciones. "
        "Las propuestas son borradores para revisar, no apuestas automáticas.",
        ("PROPUESTAS", "COMPARACIÓN", "RIESGO VISIBLE"),
        "◇",
    ),
    "noticias": (
        "03 / NEWS INTELLIGENCE", "El juego no se detiene.",
        "Titulares recientes de ESPN, organizados para que encuentres "
        "rápido lo que importa alrededor de los equipos y jugadores.",
        ("ESPN", "NBA · NFL · NHL", "FUENTES DIRECTAS"),
        "◎",
    ),
    "simulaciones": (
        "04 / SCENARIO LAB", "Explora 10,000 futuros.",
        "Simula marcadores con el historial real disponible, compara "
        "distribuciones y descubre la incertidumbre detrás de cada escenario.",
        ("MONTE CARLO", "HISTORIAL ESPN", "MODELO EXPERIMENTAL"),
        "⬡",
    ),
    "historial": (
        "05 / PRIVATE LEDGER", "Tu registro. Tus decisiones.",
        "Revisa tu actividad privada, resultados confirmados y métricas "
        "personales con acceso protegido y trazabilidad.",
        ("ACCESO PRIVADO", "RESULTADOS", "REGISTRO PERSONAL"),
        "▣",
    ),
    "calendario": (
        "06 / LIVE SCHEDULE", "Cada partido, en contexto.",
        "Calendario de NBA, NFL y NHL con horarios de Ciudad de México, "
        "estado del encuentro y enlaces verificables a ESPN.",
        ("AGENDA", "HORARIO CDMX", "ESTADOS ESPN"),
        "◷",
    ),
    "asistente": (
        "07 / ANALYSIS CHAT", "Pregunta. Contrasta. Decide.",
        "Habla con el motor de análisis. Te muestra qué datos encontró, "
        "dónde existen dudas y cuándo no puede emitir una conclusión.",
        ("CONSULTA LIBRE", "FUENTES ESPN", "SIN RESPUESTAS INVENTADAS"),
        "✳",
    ),
    "estado": (
        "08 / SYSTEM MONITOR", "Todo conectado. Todo claro.",
        "Revisa qué fuentes están disponibles y qué servicios del "
        "laboratorio siguen necesitando configuración.",
        ("FUENTES", "SEGURIDAD", "ESTADO"),
        "⏣",
    ),
}

THEME_CSS = r"""
<style id="seai-design-system-v7">
:root {
  --se-bg:#06080d; --se-panel:#10141d; --se-panel-hi:#1c1923;
  --se-line:#393440; --se-soft:#a8a9b6; --se-ink:#f6f5f7;
  --se-red:#ff4d6d; --se-pink:#ff93a5; --se-cyan:#78d9e8;
  --se-radius:20px;
}
.stApp {
  color:var(--se-ink)!important;
  background:
    radial-gradient(ellipse 60% 43% at 77% -13%,#4b15304f,transparent 80%),
    radial-gradient(ellipse 53% 60% at -14% 61%,#18273a83,transparent 77%),
    linear-gradient(155deg,#080b12 0%,#09090d 60%,#05070a 100%) fixed!important;
  font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
}
.stApp::before {
  content:"";position:fixed;inset:0;z-index:0;pointer-events:none;opacity:.21;
  background-image:
   linear-gradient(#667c9517 1px,transparent 1px),
   linear-gradient(90deg,#667c9517 1px,transparent 1px);
  background-size:55px 55px;
  mask-image:linear-gradient(90deg,transparent,#000 20%,#000 80%,transparent);
  animation:se-grid-shift 28s linear infinite;
}
.stApp::after {
  content:"";position:fixed;top:0;left:0;right:0;height:2px;z-index:1000;pointer-events:none;
  background:linear-gradient(90deg,transparent 0%,#b51f48 20%,#ff7996 51%,#902c62 82%,transparent 100%);
  box-shadow:0 0 18px #ff4d6d66;
}
[data-testid="stHeader"] {background:#080a100e!important}
[data-testid="stMain"] {position:relative;z-index:1}
.block-container {max-width:1380px!important;padding:1.15rem 2.2rem 4.8rem!important}
[data-testid="stMarkdownContainer"] h1,
[data-testid="stMarkdownContainer"] h2,
[data-testid="stMarkdownContainer"] h3,
[data-testid="stMarkdownContainer"] h4 {
  color:#f8f4f7!important;text-shadow:none!important;letter-spacing:-.035em;
  font-weight:770;line-height:1.2;
}
[data-testid="stMarkdownContainer"] h2{font-size:clamp(1.35rem,2.1vw,1.8rem)!important}
[data-testid="stMarkdownContainer"] h3{font-size:clamp(1.16rem,1.6vw,1.42rem)!important}
[data-testid="stMarkdownContainer"] p{line-height:1.65;color:#d8d7df}
.stCaption,[data-testid="stCaptionContainer"]{color:#aaa7b7!important}
a {color:#ff9eaf!important}
hr {border-color:#46333e!important}
[data-testid="stMetric"] {
  background:linear-gradient(145deg,#1d1b27e8,#10151df2)!important;
  border:1px solid #45404d;border-radius:18px;padding:1.1rem;
  box-shadow:0 14px 30px #00000035,inset 0 1px #ffffff07;
  transition:transform .22s ease,border-color .22s ease,box-shadow .22s ease;
}
[data-testid="stMetric"]:hover{transform:translateY(-3px);border-color:#d35e79;
  box-shadow:0 14px 35px #0009,0 0 25px #ff395512}
[data-testid="stMetricLabel"]{color:#bcb4c1!important}
[data-testid="stMetricValue"]{color:#fdf5f7!important;letter-spacing:-.035em}
[data-testid="stForm"],[data-testid="stExpander"] {
  background:linear-gradient(150deg,#161923f2,#0d1016ed)!important;
  border:1px solid #473b47!important;border-radius:20px!important;
  box-shadow:0 14px 35px #00000030;
}
[data-testid="stVerticalBlockBorderWrapper"] > div {
  border:1px solid #4b3b48!important;border-radius:20px!important;
  background:linear-gradient(145deg,#1b1c27e8,#0e1219ec)!important;
  box-shadow:0 16px 40px #0005,inset 0 1px #ffffff0a;
  transition:border-color .22s ease,transform .22s ease,box-shadow .22s ease;
}
[data-testid="stVerticalBlockBorderWrapper"] > div:hover{
  border-color:#8a485c!important;box-shadow:0 20px 45px #0009,0 0 30px #ff3e6111;
}
[data-testid="stTextInput"] input,[data-testid="stTextArea"] textarea,
[data-testid="stNumberInput"] input {
  background:#0b1018!important;color:#fff!important;
  border:1px solid #473b47!important;border-radius:13px!important;caret-color:#ff7d96;
}
[data-testid="stTextInput"] input:focus,[data-testid="stTextArea"] textarea:focus,
[data-testid="stNumberInput"] input:focus{
  border-color:#f46a86!important;box-shadow:0 0 0 2px #ed567328!important;
}
[data-testid="stSelectbox"] [data-baseweb="select"]>div,
[data-testid="stMultiSelect"] [data-baseweb="select"]>div {
  background:#10141c!important;border:1px solid #54404e!important;
  border-radius:13px!important;
}
button[kind="primary"],div.stFormSubmitButton>button {
  color:#240710!important;border:0!important;border-radius:13px!important;
  font-weight:770!important;background:linear-gradient(135deg,#ffb0bb,#ff536f 65%,#ea3158)!important;
  box-shadow:0 7px 25px #ff466c32!important;
  transition:transform .2s ease,box-shadow .2s ease,filter .2s ease!important;
}
button[kind="secondary"] {
  color:#f3d9df!important;border:1px solid #614052!important;
  background:linear-gradient(145deg,#211a24,#11131b)!important;
  border-radius:12px!important;transition:transform .2s ease,border-color .2s ease!important;
}
button[kind="primary"]:hover,div.stFormSubmitButton>button:hover,
button[kind="secondary"]:hover{
  transform:translateY(-2px)!important;filter:brightness(1.12);
  box-shadow:0 12px 31px #ff456c3f!important;border-color:#ff6f89!important;
}
button:focus-visible,a:focus-visible {outline:2px solid #ffb3c2!important;outline-offset:3px}
[data-testid="stDataFrame"]{
  border:1px solid #52404b!important;border-radius:17px!important;overflow:hidden;
  box-shadow:0 16px 36px #0005;
}
[data-testid="stDataFrame"] [role="columnheader"]{background:#26212c!important}
a[data-testid="stLinkButton"]{
  color:#ffcad3!important;border:1px solid #8b445c!important;
  border-radius:12px!important;background:#2a1822!important;
}
a[data-testid="stLinkButton"]:hover{border-color:#ff8099!important;background:#392030!important}
[data-testid="stAlert"],div[data-testid="stNotification"]{border-radius:16px!important}
[data-testid="stChatMessage"]{border:1px solid #453745;border-radius:20px;padding:1rem;background:#15151edb}
[data-testid="stProgressBar"]>div{border-radius:999px}
.section-brand {
  color:#fce5ec;font-size:clamp(12px,1.2vw,15px);font-weight:900;
  letter-spacing:.17em;text-align:center;padding:10px 0 3px;
}
.section-brand span{font-weight:560;color:#d993a7;letter-spacing:.04em}
.se-hero {
  --accent:#ff657e;
  position:relative;display:grid;grid-template-columns:minmax(0,1fr) minmax(160px,250px);
  align-items:center;min-height:245px;padding:31px clamp(22px,4vw,52px);
  overflow:hidden;isolation:isolate;border:1px solid #7b4252;border-radius:28px;
  background:
    radial-gradient(ellipse at 85% 25%,#d83d6640,transparent 52%),
    radial-gradient(ellipse at 9% 78%,#1e41504f,transparent 60%),
    linear-gradient(125deg,#201724 0%,#131521 48%,#0d101a 100%);
  box-shadow:0 20px 65px #0009,inset 0 1px #ffffff16;
  animation:se-hero-in .78s cubic-bezier(.2,.78,.2,1) both;
}
.se-hero::after{
  content:"";position:absolute;inset:0;z-index:-1;pointer-events:none;
  background:linear-gradient(115deg,transparent 40%,#ff658012 50%,transparent 60%);
  background-size:200% 100%;animation:se-sweep 9s linear infinite;
}
.se-hero-eyebrow{display:flex;gap:9px;align-items:center;letter-spacing:.19em;
  text-transform:uppercase;font-size:10px;font-weight:850;color:#ff9bb0!important;margin-bottom:13px}
.se-hero-eyebrow::before{content:"";width:19px;height:2px;background:#ff637b;box-shadow:0 0 12px #ff5365}
.se-hero h1{color:#fff!important;margin:0 0 10px;font-weight:850;
  letter-spacing:-.055em;line-height:1.07;font-size:clamp(33px,4.6vw,59px);
  text-shadow:0 6px 28px #0008!important}
.se-hero p{color:#cfc5d1!important;max-width:620px;line-height:1.6;margin:0;font-size:clamp(12px,1.2vw,15px)}
.se-hero-chips{display:flex;gap:8px;flex-wrap:wrap;margin-top:19px}
.se-hero-chips span{font-size:9px;letter-spacing:.12em;font-weight:800;border:1px solid #75445a;
  border-radius:999px;background:#ff75900d;color:#e5b4c3;padding:8px 11px}
.se-hero-graphic{position:relative;width:195px;height:195px;margin:auto;
  display:grid;place-items:center;animation:se-orbit-sway 6s ease-in-out infinite}
.se-orbit-ring{position:absolute;inset:9%;border:1px solid #e84a8173;border-radius:50%;
  box-shadow:inset 0 0 18px #ff456c22,0 0 22px #ff456c33;
  transform:rotateX(65deg) rotateZ(-25deg);
  animation:se-orbit-spin 14s linear infinite}
.se-orbit-ring:nth-child(2){inset:20%;border-color:#62d5ed86;
  transform:rotateX(60deg) rotateZ(43deg);animation-duration:9s;animation-direction:reverse}
.se-orbit-core{width:82px;height:82px;border-radius:24px;display:grid;place-items:center;
  font-size:43px;line-height:1;background:radial-gradient(circle at 30% 25%,#ff9aab,#6d1a43 75%,#24152c);
  color:#fff;box-shadow:0 0 27px #ff557a77,inset 0 0 12px #fff5;transform:rotate(-9deg)}
.se-hero-graphic::after{content:"";position:absolute;inset:36%;border-radius:50%;
  background:#ff608455;filter:blur(35px);z-index:-1}
.se-hud{display:flex;gap:10px;flex-wrap:wrap;margin-top:9px;color:#b7a9b5}
.se-hud span{display:flex;gap:7px;align-items:center;font-size:11px}
.se-hud b{width:5px;height:5px;background:#8bf5d6;border-radius:50%;box-shadow:0 0 10px #8bf5d6}
.se-section-heading{margin-top:1.3rem!important;margin-bottom:.2rem!important}
.se-page-bottom{margin:36px 0 10px;padding-top:16px;border-top:1px solid #523846;
  color:#847f90;font-size:10px;letter-spacing:.14em;text-align:center}
.se-mini-kpi{padding:17px 19px;border:1px solid #544352;border-radius:18px;
  background:linear-gradient(140deg,#24202c,#11141e);text-align:center}
.se-mini-kpi strong{display:block;font-size:26px;font-weight:850;color:#fff}
.se-mini-kpi span{font-size:10px;letter-spacing:.13em;color:#c4abb8}
@keyframes se-grid-shift{to{background-position:55px 55px}}
@keyframes se-hero-in{from{opacity:0;transform:translateY(24px) scale(.975);filter:blur(8px)}
  to{opacity:1;transform:translateY(0) scale(1);filter:blur(0)}}
@keyframes se-sweep{0%{background-position:200% 0}100%{background-position:-200% 0}}
@keyframes se-orbit-sway{0%,100%{transform:translateY(0)}50%{transform:translateY(-10px)}}
@keyframes se-orbit-spin{0%{transform:rotateX(63deg) rotateZ(0)}100%{transform:rotateX(63deg) rotateZ(360deg)}}
/* The page transition changes animation-name on each navigation event, so
   the browser starts a fresh pass even when Streamlit reuses the DOM node. */
.brain-page-entry{position:fixed;inset:0;z-index:99999;pointer-events:none;
  background:radial-gradient(circle at 50% 52%,#ffd1dbb5 0,#fa3c7299 5%,#4a12267e 16%,#070910ef 55%,transparent 72%);
  opacity:0;transform:scale(9);filter:blur(12px)}
.brain-page-entry::before,.brain-page-entry::after{content:"";position:absolute;
  inset:30%;border:2px solid #ff7e9ac2;border-radius:50%;box-shadow:0 0 44px #ff4774aa;
  animation:se-portal-ring .9s ease-out both}
.brain-page-entry::after{animation-delay:.12s;border-color:#7bdceb99}
.brain-page-entry--a{animation:se-portal-a .91s cubic-bezier(.2,.7,.19,1) forwards}
.brain-page-entry--b{animation:se-portal-b .91s cubic-bezier(.2,.7,.19,1) forwards}
@keyframes se-portal-a{0%{opacity:.95;transform:scale(.17);filter:blur(0)}
  38%{opacity:.88;transform:scale(1.55)}
  100%{opacity:0;transform:scale(8);filter:blur(18px)}}
@keyframes se-portal-b{0%{opacity:.95;transform:scale(.17);filter:blur(0)}
  38%{opacity:.88;transform:scale(1.55)}
  100%{opacity:0;transform:scale(8);filter:blur(18px)}}
@keyframes se-portal-ring{0%{transform:scale(.2);opacity:.95}
  100%{transform:scale(6);opacity:0}}
@media(max-width:860px){
 .block-container{padding:1.1rem 1.1rem 3.3rem!important}
 .se-hero{grid-template-columns:minmax(0,1fr) 135px;min-height:218px;padding:24px}
 .se-hero-graphic{width:130px;height:130px}
 .se-orbit-core{width:62px;height:62px;font-size:33px}
}
@media(max-width:540px){
 .block-container{padding:.8rem .7rem 2.4rem!important}
 .se-hero{grid-template-columns:minmax(0,1fr);border-radius:19px;padding:23px 20px}
 .se-hero-graphic{position:absolute;right:-23px;top:-28px;width:145px;height:145px;
   opacity:.22;pointer-events:none;z-index:-1}
 .se-hero h1{font-size:clamp(31px,8vw,45px)}
 .se-hero-chips span{font-size:8px}
 .section-brand{font-size:11px;letter-spacing:.06em}
 .section-brand span{display:block;font-size:10px}
}
@media(prefers-reduced-motion:reduce){
 .stApp::before,.se-hero,.se-hero::after,.se-hero-graphic,.se-orbit-ring,
 .brain-page-entry,.brain-page-entry::before,.brain-page-entry::after{
   animation:none!important;transition:none!important;
 }
 .brain-page-entry{display:none!important}
 [data-testid="stMetric"],button{transition:none!important}
}
</style>
"""


def inject_theme() -> None:
    st.markdown(THEME_CSS, unsafe_allow_html=True)


def render_hero(section: str) -> None:
    if section not in SECTION_INFO:
        return
    eyebrow, headline, description, labels, symbol = SECTION_INFO[section]
    chips = "".join("<span>" + html.escape(label) + "</span>" for label in labels)
    st.html(
        '<section class="se-hero" aria-label="Presentación de '
        + html.escape(section) + '"><div class="se-hero-copy">'
        + '<div class="se-hero-eyebrow">' + html.escape(eyebrow) + '</div>'
        + '<h1>' + html.escape(headline) + '</h1>'
        + '<p>' + html.escape(description) + '</p>'
        + '<div class="se-hero-chips">' + chips + '</div>'
        + '</div><div class="se-hero-graphic" aria-hidden="true">'
        + '<div class="se-orbit-ring"></div><div class="se-orbit-ring"></div>'
        + '<div class="se-orbit-core">' + html.escape(symbol) + '</div>'
        + '</div></section>'
    )


def render_footer() -> None:
    st.html(
        '<footer class="se-page-bottom">SPORTS EDGE AI &nbsp; / &nbsp; '
        'MODELOS EXPERIMENTALES &nbsp; / &nbsp; DATOS CON FUENTE &nbsp; / &nbsp; '
        'NO SE EJECUTAN APUESTAS</footer>'
    )
