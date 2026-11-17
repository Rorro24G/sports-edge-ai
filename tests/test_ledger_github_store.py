"""Tests offline GitHub private storage: confidentiality, versioning, fail-closed."""
import base64
import json
from unittest import TestCase
from unittest.mock import patch

from src.pick_ledger import LedgerError, add_bet, metrics, settle_bet
from src import ledger_github_store as remote


class FakePrivateGitHub:
    def __init__(self, private=True):
        self.private = private
        self.ledger = None
        self.sha = None
        self.writes = 0

    def call(self, url, token, *, data=None):
        if "/contents/" not in url:
            return {"private": self.private}
        if data is None:
            return ({"type": "file", "sha": self.sha,
                     "content": base64.b64encode(
                         json.dumps(self.ledger).encode("utf-8")).decode("ascii")}
                    if self.ledger is not None else None)
        if self.ledger is not None and data.get("sha") != self.sha:
            raise LedgerError("Conflicto de versiones")
        self.ledger = json.loads(base64.b64decode(data["content"]))
        self.writes += 1
        self.sha = "sha-" + str(self.writes)
        return {"content": {"sha": self.sha}}


class GithubLedgerTests(TestCase):
    def test_create_save_and_read_without_leaking_token(self):
        source = FakePrivateGitHub()
        with patch.object(remote, "_api", side_effect=source.call):
            repo = "owner/private-ledger"
            key = "test-token-this-is-not-real-1234"
            remote.initialize(repo, key, "1000.00")
            def append(doc):
                return add_bet(doc, sport="NBA", event="Lakers vs Warriors",
                               selection="Lakers ML", odds_american=-110, stake=100)
            bet = remote.transact(repo, key, append)
            self.assertEqual(len(remote.read_ledger(repo, key)["bets"]), 1)
            remote.transact(repo, key, lambda doc: settle_bet(doc, bet["id"], "ganado"))
            self.assertEqual(metrics(remote.read_ledger(repo, key))["wins"], 1)
            self.assertEqual(source.writes, 3)

    def test_refuses_public_repository_and_bad_paths(self):
        source = FakePrivateGitHub(private=False)
        with patch.object(remote, "_api", side_effect=source.call):
            with self.assertRaisesRegex(LedgerError, "PRIVADO"):
                remote.initialize("owner/public", "long-test-token-valid-123456", 100)
        with self.assertRaises(LedgerError):
            remote.read_ledger("owner/bad", "long-test-token-valid-123456",
                               path="../secrets.json")

    def test_no_overwrite_backup_existing(self):
        source = FakePrivateGitHub()
        key = "long-test-token-valid-123456"
        with patch.object(remote, "_api", side_effect=source.call):
            original = remote.initialize("owner/ledger", key, 100)
            with self.assertRaises(LedgerError):
                remote.restore_backup("owner/ledger", key, json.dumps(original).encode())

    def test_empty_repository_is_empty_ledger(self):
        source = FakePrivateGitHub()
        with patch.object(remote, "_api", side_effect=source.call):
            self.assertIsNone(remote.read_ledger("owner/ledger", "long-test-token-valid-123456"))
