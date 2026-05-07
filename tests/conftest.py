import pytest


@pytest.fixture
def tmp_run_dir(tmp_path):
    d = tmp_path / "runs" / "test-run"
    d.mkdir(parents=True)
    return d
