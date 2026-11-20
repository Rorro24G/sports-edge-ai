"""Visual contract: six distinct pages, real transitions and reduced motion."""
from unittest import TestCase

from src.section_design import SECTION_INFO, PAGE_SUMMARY, THEME_CSS
from src.calendar_ui import _source_url, _status_label


class SectionDesignTests(TestCase):
    def test_all_six_public_sections_have_unique_visual_heroes(self):
        public = {"picks", "parlays", "noticias", "simulaciones", "historial", "calendario"}
        self.assertTrue(public.issubset(SECTION_INFO))
        headlines = [SECTION_INFO[section][1] for section in public]
        self.assertEqual(len(headlines), len(set(headlines)))
        for section in public:
            eyebrow, headline, description, labels, symbol = SECTION_INFO[section]
            self.assertTrue(eyebrow and headline and len(description) > 60)
            self.assertEqual(len(labels), 3)
            self.assertTrue(symbol)

    def test_one_clear_message_per_section_and_compact_hero(self):
        self.assertEqual(set(PAGE_SUMMARY), set(SECTION_INFO))
        for section, summary in PAGE_SUMMARY.items():
            self.assertTrue(15 <= len(summary) <= 100, section)
            self.assertLessEqual(summary.count("."), 2, section)
        self.assertIn("min-height:126px!important", THEME_CSS)
        self.assertIn(".se-hero-chips{display:none!important}", THEME_CSS)
        self.assertIn("max-width:740px", THEME_CSS)
        self.assertIn("font-size:clamp(25px,3vw,37px)", THEME_CSS)

    def test_page_enter_has_two_restartable_animations(self):
        self.assertIn("brain-page-entry--a", THEME_CSS)
        self.assertIn("brain-page-entry--b", THEME_CSS)
        self.assertIn("@keyframes se-portal-a", THEME_CSS)
        self.assertIn("@keyframes se-portal-b", THEME_CSS)
        self.assertIn("@keyframes se-portal-ring", THEME_CSS)
        self.assertIn("@keyframes se-hero-in", THEME_CSS)
        self.assertIn("prefers-reduced-motion:reduce", THEME_CSS)
        self.assertIn(".brain-page-entry{display:none!important}", THEME_CSS)

    def test_theme_has_responsive_cards_and_clear_input_focus(self):
        for marker in ("se-hero", "se-hero-graphic", "se-orbit-ring",
                       "max-width:540px", "focus-visible", "stMetric",
                       "stDataFrame", "stForm", "stChatMessage"):
            self.assertIn(marker, THEME_CSS)

    def test_calendar_sources_are_espn_only(self):
        self.assertEqual(
            _source_url("https://www.espn.com/nba/game/_/gameId/123"),
            "https://www.espn.com/nba/game/_/gameId/123",
        )
        for url in (
            "https://fake-espn.com/", "http://www.espn.com/",
            "https://www.espn.com.evil.org/", "javascript:alert(1)",
            "https://user:pass@www.espn.com/path", None,
        ):
            self.assertIsNone(_source_url(url))

    def test_calendar_labels_are_grounded_in_espn_state(self):
        self.assertIn("POR COMENZAR", _status_label("PRE"))
        self.assertIn("EN JUEGO", _status_label("IN"))
        self.assertIn("FINALIZADO", _status_label("POST"))
        self.assertIn("ESTADO ESPN", _status_label("unknown"))
