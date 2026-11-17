"""Verifica flujo de Mi historial en Streamlit: crear bank y registrar por texto."""
import tempfile
from pathlib import Path
from streamlit.testing.v1 import AppTest
from src.ledger_store import read_ledger

with tempfile.TemporaryDirectory() as folder:
    path = str(Path(folder) / "historial.sqlite")
    app = AppTest.from_file("../app.py", default_timeout=50)
    app.secrets["LEDGER_ACCESS_PASSWORD"] = "test-password-only"
    app.secrets["LEDGER_DB_PATH"] = path
    app = app.run()
    assert not app.exception, [str(x.message) for x in app.exception]

    app.text_input(key="ledger_password").set_value("test-password-only")
    app.button(key="ledger_unlock").click()
    app = app.run()
    assert not app.exception, [str(x.message) for x in app.exception]

    app.button(key="FormSubmitter:initialize_bank-Crear historial").click()
    app = app.run()
    assert not app.exception, [str(x.message) for x in app.exception]
    ledger = read_ledger(path)
    assert ledger is not None and ledger["bets"] == []

    app.text_area(key="bet_command").set_value(
        "Voy a meter NBA, partido: Lakers vs Warriors; pick: Lakers ML; momio: -110; con $100"
    )
    app.button(key="bet_parse").click()
    app = app.run()
    assert not app.exception, [str(x.message) for x in app.exception]
    assert read_ledger(path)["bets"] == [], "El borrador se guardó sin confirmación"
    app.button(key="bet_save").click()
    app = app.run()
    assert not app.exception, [str(x.message) for x in app.exception]
    assert len(read_ledger(path)["bets"]) == 1
    assert read_ledger(path)["bets"][0]["stake"] == "100.00"
    print("STREAMLIT_LEDGER_UI_OK")
