"""Comprobaciones del prototipo visual inmersivo (sin red ni datos privados)."""
from html.parser import HTMLParser
from pathlib import Path
import unittest

HTML = Path(__file__).resolve().parents[1] / "web" / "brain_v2.html"


class Elements(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = set()
        self.neurons = []

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if "id" in values:
            self.ids.add(values["id"])
        if tag == "button" and "neuron" in values.get("class", "").split():
            self.neurons.append(values.get("data-page"))


class VisualDesignTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = HTML.read_text(encoding="utf-8")
        cls.elements = Elements()
        cls.elements.feed(cls.html)

    def test_essential_scenes_and_canvas_present(self):
        self.assertTrue(
            {"intro", "brain", "detail", "enter", "exit", "stage", "view"}.issubset(
                self.elements.ids
            )
        )

    def test_four_dedicated_neurons(self):
        self.assertEqual(
            self.elements.neurons,
            ["picks", "simulaciones", "calendario", "apuestas"],
        )

    def test_drag_touch_and_keyboard_navigation(self):
        self.assertIn("pointermove", self.html)
        self.assertIn("touch-action:none", self.html)
        self.assertIn("ArrowLeft", self.html)
        self.assertIn("data-page", self.html)

    def test_no_live_betting_claims(self):
        self.assertIn("FALTAN CUOTAS Y MODELO VALIDADO", self.html)
        self.assertIn("No es una recomendación de apuesta", self.html)
