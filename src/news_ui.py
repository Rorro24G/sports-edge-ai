"""Live headlines with timestamps and a direct reading link."""
from datetime import datetime
from zoneinfo import ZoneInfo
import streamlit as st
from .content_feed import fetch_news, NewsError


@st.cache_data(ttl=300, show_spinner=False)
def cached_news(league):
    return fetch_news(league)


def render():
    st.subheader("Noticias y actualidad")
    league = st.selectbox("Liga de noticias", ["NBA", "NFL", "NHL"], key="news_league")
    search = st.text_input("Filtrar por equipo o jugador", key="news_search")
    if st.button("Actualizar noticias", key="refresh_news"):
        cached_news.clear()
    try:
        with st.spinner("Actualizando titulares..."):
            feed = cached_news(league)
    except NewsError as exc:
        st.warning(str(exc))
        return
    st.caption("Últimas 72 horas · consulta " + feed["checked_at_utc"] + " UTC")
    articles = [a for a in feed["articles"] if search.casefold() in a["headline"].casefold()]
    if not articles:
        st.info("No hay titulares recientes para este filtro. Prueba otro equipo o liga.")
    for item in articles:
        with st.container(border=True):
            st.write(item["headline"])
            published = datetime.fromisoformat(item["published_utc"]).astimezone(ZoneInfo("America/Mexico_City"))
            st.caption(published.strftime("%d/%m/%Y · %H:%M CDMX"))
            st.link_button("Leer noticia", item["url"])
    st.caption("Un titular no confirma una baja ni una alineación. Consulta el reporte del partido para disponibilidad.")
