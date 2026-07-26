from app.config import Settings


def test_defaults():
    s = Settings(_env_file=None)
    assert s.namespace == "monitoring"
    assert s.poll_interval == 113
    assert s.ignore_info_jobs == []
    assert s.ignore_health_jobs == []


def test_csv_env_vars_are_split_and_stripped(monkeypatch):
    monkeypatch.setenv("VMTE_IGNORE_INFO_JOBS", "job-a, job-b,job-c")
    monkeypatch.setenv("VMTE_IGNORE_HEALTH_JOBS", "")
    s = Settings(_env_file=None)
    assert s.ignore_info_jobs == ["job-a", "job-b", "job-c"]
    assert s.ignore_health_jobs == []


def test_non_csv_env_vars_still_work(monkeypatch):
    monkeypatch.setenv("VMTE_NAMESPACE", "custom-ns")
    monkeypatch.setenv("VMTE_POLL_INTERVAL", "42")
    s = Settings(_env_file=None)
    assert s.namespace == "custom-ns"
    assert s.poll_interval == 42
