"""Pruebas del historial personal: resultados, 5% y persistencia."""
import tempfile
from pathlib import Path
from unittest import TestCase
from decimal import Decimal
from src.pick_ledger import (LedgerError, new_ledger, add_bet, settle_bet,
                             metrics)
from src.ledger_store import (initialize, read_ledger, transact,
                              export_json, restore_backup)
from src.ledger_text import parse_bet_message


class LedgerTests(TestCase):
    def test_profit_and_hit_rate_and_5pct(self):
        ledger = new_ledger(1000)
        a = add_bet(ledger, sport="NBA", event="Lakers vs Warriors",
                    selection="Lakers ML", odds_american="+150", stake="50")
        self.assertEqual(a["bank_percent_at_entry"], "5.00")
        self.assertEqual(metrics(ledger)["bank_available"], Decimal("950.00"))
        self.assertEqual(metrics(ledger)["suggested_stake_5pct"], Decimal("47.50"))
        settle_bet(ledger, a["id"], "ganado")
        m = metrics(ledger)
        self.assertEqual(m["net_profit"], Decimal("75.00"))
        self.assertEqual(m["bank_current"], Decimal("1075.00"))
        self.assertEqual(m["hit_rate"], Decimal("100.00"))
        self.assertEqual(m["roi"], Decimal("150.00"))
        self.assertEqual(m["pnl_pct_initial"], Decimal("7.50"))
        self.assertEqual(m["suggested_stake_5pct"], Decimal("53.75"))

    def test_losing_and_push_do_not_fake_success(self):
        ledger = new_ledger(1000)
        loss = add_bet(ledger, sport="NFL", event="A vs B", selection="A ML",
                       odds_american="-110", stake=100)
        push = add_bet(ledger, sport="NBA", event="C vs D", selection="over 200",
                       odds_american="-110", stake=25)
        settle_bet(ledger, loss["id"], "perdido")
        settle_bet(ledger, push["id"], "push")
        m = metrics(ledger)
        self.assertEqual(m["net_profit"], Decimal("-100.00"))
        self.assertEqual(m["bank_current"], Decimal("900.00"))
        self.assertEqual(m["hit_rate"], Decimal("0.00"))
        self.assertEqual(m["pushes"], 1)
        self.assertEqual(m["roi"], Decimal("-100.00"))

    def test_no_double_settle_or_exceed_bank(self):
        ledger = new_ledger(100)
        with self.assertRaises(LedgerError):
            add_bet(ledger, sport="NBA", event="A vs B", selection="A", odds_american=-110, stake=101)
        bet = add_bet(ledger, sport="NBA", event="A vs B", selection="A", odds_american=-110, stake=100)
        self.assertEqual(metrics(ledger)["bank_available"], Decimal("0.00"))
        with self.assertRaises(LedgerError):
            add_bet(ledger, sport="NBA", event="C vs D", selection="C", odds_american=-110, stake=1)
        settle_bet(ledger, bet["id"], "anulado")
        with self.assertRaises(LedgerError):
            settle_bet(ledger, bet["id"], "ganado")

    def test_text_draft_not_saved(self):
        example = ("Voy a meter NBA, partido: Lakers vs Warriors; "
                   "pick: Lakers ML; momio: -110; con $100")
        draft = parse_bet_message(example)
        self.assertEqual(draft["sport"], "NBA")
        self.assertEqual(draft["selection"], "Lakers ML")
        self.assertEqual(draft["event"], "Lakers vs Warriors")
        self.assertEqual(draft["odds_american"], -110)
        self.assertEqual(draft["stake"], "100.00")
        with self.assertRaises(LedgerError):
            parse_bet_message("Voy a meter Lakers")
        with self.assertRaises(LedgerError):
            parse_bet_message("Voy a meter NBA, partido: A vs B; pick: A; momio: -110")

    def test_sqlite_survives_reopen_and_backup(self):
        with tempfile.TemporaryDirectory() as home:
            path = str(Path(home) / "bank.sqlite")
            initialize(path, 2000, "MXN")
            bet = transact(path, lambda led: add_bet(
                led, sport="NHL", event="A @ B", selection="A ML",
                odds_american="+200", stake="100",
            ))
            transact(path, lambda led: settle_bet(led, bet["id"], "ganado"))
            restored = read_ledger(path)
            self.assertEqual(metrics(restored)["net_profit"], Decimal("200.00"))
            exported = export_json(restored)
            other = str(Path(home) / "backup.sqlite")
            restore_backup(other, exported)
            self.assertEqual(metrics(read_ledger(other))["net_profit"], Decimal("200.00"))
            with self.assertRaises(LedgerError):
                restore_backup(path, exported)

    def test_reject_invalid_momio(self):
        ledger = new_ledger(1000)
        with self.assertRaises(LedgerError):
            add_bet(ledger, sport="NBA", event="A @ B", selection="A",
                    odds_american="54%", stake=100)
