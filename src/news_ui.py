"""Editorial, source-linked news desk with honest freshness information."""
from datetime import datetime
from zoneinfo import ZoneInfo
import streamlit as st

from .content_feed import fetch_news, NewsError

MX = ZoneInfo("America/Mexico_City")


@st.cache_data(ttl=300, show_spinner=False)
def cached_news(league):
    return fetch_news(league)


def _article_card(item: dict, *, featured: bool = False, index: int = 1) -> None:
    published = datetime.fromisoformat(item["published_utc"]).astimezone(MX)
    with st.container(border=True):
        st.caption(
            ("◉ PORTADA  /  ESPN" if featured else f"◈ NOTICIA {index:02d}  /  ESPN")
            + "   ·   " + published.strftime("%d %b · %H:%M CDMX")
        )
        # Streamlit Markdown escapes raw HTML by default. Headlines come
        # from the verified ESPN news endpoint and do not become custom HTML.
        headline = str(item["headline"])
        st.markdown(("### " if featured else "#### ") + headline)
        if featured:
            st.caption(
                "Cobertura reciente. Abre el artículo para consultar "
                "el contexto original y verificar los detalles."
            )
        if str(item["url"]).startswith("https://www.espn.com/"):
            st.link_button(
                "Leer noticia completa", item["url"],
                use_container_width=not featured,
            )
        elif str(item["url"]).startswith("https://"):
            st.link_button("Abrir artículo ESPN", item["url"])


def render():
    st.markdown("### Sala de noticias")
    st.caption(
        "Una selección editorial de titulares publicados durante las últimas "
        "72 horas. Todas las notas se abren desde su fuente original."
    )
    league_col, filter_col, refresh_col = st.columns([1.2, 2.5, 1.1],
                                                    vertical_alignment="bottom")
    with league_col:
        league = st.selectbox(
            "Liga de noticias", ["NBA", "NFL", "NHL"], key="news_league"
        )
    with filter_col:
        search = st.text_input(
            "Filtrar por equipo o jugador", key="news_search",
            placeholder="Ej. Lakers, Mahomes, Boston…",
        )
    with refresh_col:
        if st.button(
            "↻ Actualizar noticias", key="refresh_news", use_container_width=True
        ):
            cached_news.clear()
    try:
        with st.spinner("Consultando la redacción de ESPN..."):
            feed = cached_news(league)
    except NewsError as exc:
        st.warning(str(exc))
        return

    articles = [
        a for a in feed["articles"]
        if search.casefold() in a["headline"].casefold()
    ]
    a, b, c = st.columns(3)
    a.metric("Titulares encontrados", str(len(articles)))
    b.metric("Cobertura", league)
    c.metric("Ventana informativa", "72 h")
    st.caption(
        "Fuente ESPN · Última consulta: " + feed["checked_at_utc"] + " UTC"
    )

    if not articles:
        st.info(
            "No hay titulares recientes para este filtro. Prueba otro equipo o liga."
        )
        return

    st.markdown("#### En portada")
    _article_card(articles[0], featured=True)
    if len(articles) > 1:
        st.markdown("#### Más historias")
        for offset in range(1, len(articles), 2):
            columns = st.columns(2, gap="medium")
            for j, article in enumerate(articles[offset:offset + 2]):
                with columns[j]:
                    _article_card(article, index=offset+j+1)
    st.caption(
        "Los titulares no confirman lesiones ni alineaciones. "
        "Consulta el reporte oficial antes de atribuir bajas a un equipo."
    )
