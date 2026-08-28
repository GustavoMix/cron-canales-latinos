from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/check-and-publish.yml"


def test_github_workflow_runs_weekly_with_country_matrix_and_pages_deploy():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert 'cron: "0 8 * * 0"' in text
    assert "max-parallel: 5" in text
    assert "fail-fast: false" in text
    assert "BO" in text and "AR" in text and "ES" in text
    assert "python -m channelwatch run --country" in text
    assert "python -m channelwatch publish-index" in text
    assert "actions/upload-artifact@v4" in text
    assert "actions/download-artifact@v4" in text
    assert "actions/deploy-pages@v4" in text
    assert "github.repository_owner" in text


def test_github_workflow_has_no_interactive_inputs_for_scheduled_run():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "workflow_dispatch:" in text
    assert "inputs:" not in text
