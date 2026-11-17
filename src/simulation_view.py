"""Stadium / court scenario visualization and distribution of Monte Carlo runs.

The animation is explicitly *illustrative*. It is not an actual replay,
tracking model, or play-by-play simulation (those would need licensed feeds).
"""
from __future__ import annotations

from html import escape
import streamlit as st

from .simulations import GameScenario, SimulationResult


def _scene(sport: str, away_name: str, home_name: str,
           away_mean: float, home_mean: float) -> str:
    away = escape(str(away_name)[:50])
    home = escape(str(home_name)[:50])
    if sport == "NFL":
        field = """
        <defs>
          <linearGradient id="grassTone" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0" stop-color="#236c57"/>
            <stop offset="1" stop-color="#143b33"/>
          </linearGradient>
        </defs>
        <polygon points="100,25 680,25 787,260 13,260" fill="url(#grassTone)"
                 stroke="#74d4a8" stroke-width="3"/>
        <path d="M100 25L13 260L94 260L160 25Z" fill="#183a76" opacity=".9"/>
        <path d="M620 25L680 25L787 260L706 260Z" fill="#432a75" opacity=".9"/>
        <g stroke="#dcffef" stroke-opacity=".60" stroke-width="1.5">
          <path d="M160 25L94 260M218 25L172 260M276 25L249 260
                   M334 25L326 260M392 25L403 260M450 25L480 260
                   M508 25L557 260M566 25L634 260M620 25L706 260"/>
          <path d="M80 83L718 83M56 144L744 144M34 206L765 206"
                stroke-opacity=".25"/>
        </g>
        <g fill="#e9fff5" fill-opacity=".8" font-size="15" font-weight="700">
           <text x="235" y="60">20</text><text x="320" y="60">40</text>
           <text x="399" y="60">50</text><text x="485" y="60">40</text>
           <text x="570" y="60">20</text>
        </g>
        <g class="sim-players" fill="#ffdf87" stroke="#051e21" stroke-width="3">
          <circle cx="263" cy="117" r="11"/><circle cx="285" cy="141" r="11"/>
          <circle cx="263" cy="171" r="11"/><circle cx="308" cy="111" r="11"/>
          <circle cx="331" cy="151" r="11"/>
        </g>
        <g class="sim-defense" fill="#a1a9ff" stroke="#0a122b" stroke-width="3">
          <circle cx="452" cy="120" r="11"/><circle cx="468" cy="153" r="11"/>
          <circle cx="452" cy="182" r="11"/><circle cx="489" cy="136" r="11"/>
        </g>
        <g class="sim-ball">
          <ellipse cx="316" cy="133" rx="10" ry="6" fill="#e8a16e"
                   stroke="#fff2df" stroke-width="2"/>
        </g>
        """
    else:
        field = """
        <defs>
          <linearGradient id="courtTone" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0" stop-color="#533d2d"/>
            <stop offset="1" stop-color="#8a6745"/>
          </linearGradient>
        </defs>
        <rect x="25" y="28" width="750" height="230" rx="10"
              fill="url(#courtTone)" stroke="#d8c5a4" stroke-width="3"/>
        <g stroke="#f5e3c0" fill="none" stroke-width="2">
          <path d="M400 28V258"/>
          <circle cx="400" cy="143" r="60"/>
          <path d="M25 73H172V213H25M775 73H628V213H775"/>
          <path d="M25 42C244 42 244 244 25 244
                   M775 42C556 42 556 244 775 244"/>
          <circle cx="115" cy="143" r="8"/>
          <circle cx="685" cy="143" r="8"/>
        </g>
        <g class="sim-players" fill="#ffdf87" stroke="#051e21" stroke-width="3">
          <circle cx="236" cy="94" r="13"/><circle cx="261" cy="191" r="13"/>
          <circle cx="353" cy="111" r="13"/><circle cx="327" cy="210" r="13"/>
          <circle cx="393" cy="160" r="13"/>
        </g>
        <g class="sim-defense" fill="#a1a9ff" stroke="#0a122b" stroke-width="3">
          <circle cx="484" cy="80" r="13"/><circle cx="489" cy="190" r="13"/>
          <circle cx="547" cy="116" r="13"/><circle cx="560" cy="200" r="13"/>
          <circle cx="424" cy="216" r="13"/>
        </g>
        <g class="sim-ball">
          <circle cx="360" cy="137" r="6" fill="#ea9d5d"
                  stroke="#fff" stroke-width="1.5"/>
        </g>
        """
    return f"""
<style>
.sim-stadium {{
 background:linear-gradient(145deg,#091d24,#061018 70%);
 border-radius:19px;border:1px solid #2e655c;
 box-shadow:0 14px 38px #0006;overflow:hidden;margin:.8rem 0;
}}
.sim-scoretop {{display:flex;justify-content:space-between;align-items:center;
 gap:1rem;padding:18px 24px;background:linear-gradient(90deg,#132833,#122b28);
 color:#eafff2;flex-wrap:wrap}}
.sim-name {{font-size:1rem;font-weight:800;letter-spacing:.03em}}
.sim-score {{font-size:1.4rem;color:#b9ffdf;font-weight:900}}
.sim-sub {{font-size:.72rem;letter-spacing:.12em;color:#8ccbbc}}
.sim-stage {{padding:18px 18px 10px;background:
 radial-gradient(ellipse at 50% 30%,#19473a 0%,#071b1f 75%);
 display:flex;justify-content:center;overflow:hidden}}
.sim-stage svg {{width:100%;max-width:800px;aspect-ratio:800/280;
 filter:drop-shadow(0 15px 12px #0007)}}
.sim-ball {{animation:ball-demo 4.6s ease-in-out infinite;
 transform-origin:center;transform-box:fill-box}}
.sim-players {{animation:attacking-demo 4.6s ease-in-out infinite}}
.sim-defense {{animation:defending-demo 4.6s ease-in-out infinite}}
.sim-footer {{padding:13px 20px;background:#0b2626;color:#b7ddcf;
 font-size:.74rem;border-top:1px solid #24554d}}
@keyframes ball-demo {{
 0%,100%{{transform:translate(0,0)}}
 35%{{transform:translate(40px,-35px)}}
 70%{{transform:translate(90px,8px)}}
}}
@keyframes attacking-demo {{
 0%,100%{{transform:translateX(0)}}45%{{transform:translateX(22px)}}
}}
@keyframes defending-demo {{
 0%,100%{{transform:translate(-0px,0px)}}
 55%{{transform:translate(-24px,-2px)}}
}}
@media(prefers-reduced-motion:reduce){{
 .sim-ball,.sim-players,.sim-defense{{animation:none}}
}}
</style>
<div class="sim-stadium">
  <div class="sim-scoretop">
    <div><div class="sim-sub">VISITANTE · MEDIA DEL ESCENARIO</div>
      <div class="sim-name">{away}</div><div class="sim-score">{away_mean:.1f}</div></div>
    <div class="sim-sub">◉ {sport} · LABORATORIO 10.000</div>
    <div><div class="sim-sub">LOCAL · MEDIA DEL ESCENARIO</div>
      <div class="sim-name">{home}</div><div class="sim-score">{home_mean:.1f}</div></div>
  </div>
  <div class="sim-stage">
    <svg viewBox="0 0 800 280" role="img"
         aria-label="Ilustración animada de {sport}, no una jugada real">
         {field}
    </svg>
  </div>
  <div class="sim-footer">
   VISUALIZACIÓN ILUSTRATIVA · No reproduce jugadas reales, rutas, lesiones,
   movimientos físicos ni datos de seguimiento de jugadores.
  </div>
</div>
"""


def render_results(scenario: GameScenario, result: SimulationResult, *,
                   away_name: str = "Visitante", home_name: str = "Local",
                   source_note: str = "Parámetros hipotéticos") -> None:
    st.markdown(_scene(scenario.sport, away_name, home_name,
                       scenario.away_mean, scenario.home_mean),
                unsafe_allow_html=True)
    st.caption(source_note + " · Distribución normal bivariada con truncamiento "
               "y redondeo; parámetros no calibrados frente a resultados.")
    a, b, c, d = st.columns(4)
    a.metric("Over simulado", f"{result.over_probability:.1%}")
    b.metric("Under simulado", f"{result.under_probability:.1%}")
    c.metric("Push simulado", f"{result.push_probability:.1%}")
    d.metric("Total medio", f"{result.simulated_mean_total:.1f}")
    st.markdown("**Distribución de los 10.000 marcadores simulados**")
    st.bar_chart(result.histogram, x="Puntos", y="Frecuencia",
                 use_container_width=True)
    st.caption(
        f"Percentiles del escenario: 10.º = {result.simulated_p10_total} puntos, "
        f"mediana = {result.simulated_median_total}, "
        f"90.º = {result.simulated_p90_total}. "
        f"Margen Monte Carlo de over (solo muestreo): "
        f"±{result.over_mc_margin_95:.1%}. "
        "NO es un intervalo de confianza de la predicción."
    )
    st.warning(
        "NO ES PICK VALIDADO: el simulador genera escenarios matemáticos, "
        "no probabilidades de apuestas calibradas ni garantías de resultado. "
        "No asigna stakes ni asume un momio del mercado."
    )
