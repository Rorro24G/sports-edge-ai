"""Auditoría de integridad y horarios del calendario de prueba."""
from collections import Counter
from datetime import date
import json
import unittest
from src.weekend import DEFAULT_FIXTURE, select_games


class WeekendTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture=json.loads(DEFAULT_FIXTURE.read_text(encoding='utf8'))

    def test_counts_friday_saturday(self):
        rows=select_games(self.fixture,date(2026,11,13),date(2026,11,14))
        c=Counter((row['fecha_et'],row['deporte']) for row in rows)
        self.assertEqual(len(rows),30)
        self.assertEqual(c[('2026-11-13','NBA')],9)
        self.assertEqual(c[('2026-11-14','NBA')],5)
        self.assertEqual(c[('2026-11-13','NHL')],2)
        self.assertEqual(c[('2026-11-14','NHL')],14)
        self.assertFalse(any(row['deporte']=='NFL' for row in rows))

    def test_nfl_is_sunday(self):
        sunday=select_games(self.fixture,date(2026,11,15),date(2026,11,15),{'NFL'})
        self.assertEqual(len(sunday),12)
        self.assertEqual(sunday[0]['fecha_monterrey'],'2026-11-15')

    def test_hour_conversion_monterrey(self):
        rows=select_games(self.fixture,date(2026,11,13),date(2026,11,13))
        knicks=next(r for r in rows if r['visitante']=='New York Knicks')
        self.assertEqual(knicks['hora_et'],'19:00')
        self.assertEqual(knicks['hora_monterrey'],'18:00')

    def test_all_rows_have_sources_and_no_fabricated_odds(self):
        rows=select_games(self.fixture,date(2026,11,13),date(2026,11,15))
        self.assertTrue(all(r['fuente'].startswith('https://') for r in rows))
        self.assertTrue(all(r['estado_modelo']=='SIN_MODELO_VALIDADO' for r in rows))
        self.assertTrue(all(r['estado_cuotas']=='SIN_CUOTAS_VERIFICADAS' for r in rows))

    def test_invalid_date_range_rejected(self):
        with self.assertRaises(ValueError):
            select_games(self.fixture,date(2026,11,15),date(2026,11,13))


if __name__=='__main__':
    unittest.main()
