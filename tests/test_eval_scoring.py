from pathlib import Path

import yaml

from evals.scoring import Transcript, score


def test_score_passes_and_fails() -> None:
    t = Transcript(
        replies=["Ji, Class 1 ki fees ₹85,000 per year hai."], tools=["get_school_facts"]
    )
    expect = {
        "must_call": ["get_school_facts"],
        "must_not_call": ["escalate_to_counselor"],
        "escalate": False,
        "language": "hinglish",
        "contains_any": ["85,000"],
        "must_not_contain": ["98%"],
        "max_words": 60,
    }
    assert all(c.passed for c in score(expect, t))
    failing = score({"language": "hi", "escalate": True}, t)
    assert [c.passed for c in failing] == [False, False]


def test_scenario_files_are_valid() -> None:
    files = sorted(Path("evals/scenarios").glob("*.yaml"))
    scenarios = [s for f in files for s in yaml.safe_load(f.read_text())["scenarios"]]
    ids = [s["id"] for s in scenarios]
    assert len(ids) == len(set(ids))
    for s in scenarios:
        assert s["turns"] and "expect" in s, s["id"]
