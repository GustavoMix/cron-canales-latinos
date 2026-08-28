from pathlib import Path


def test_probar_local_bat_bootstraps_and_runs_channelwatch():
    path = Path("PROBAR_LOCAL.bat")
    assert path.exists(), "PROBAR_LOCAL.bat debe existir en la raíz"
    text = path.read_text(encoding="utf-8").lower()

    assert ".venv" in text
    assert "-m venv" in text
    assert "pip install -e" in text
    assert "validate-config" in text
    assert "list-countries" in text
    assert "set /p country" in text
    assert 'if /i "%country%"=="all"' in text
    assert "run --country %country%" in text
    assert "explorer" in text and "public\\data" in text
    assert "if errorlevel 1" in text
