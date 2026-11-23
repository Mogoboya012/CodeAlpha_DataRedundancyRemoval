import pytest
import app as svc


@pytest.fixture
def c(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "t.db"))
    return svc.app.test_client()


def post(c, *recs):
    return [r["status"] for r in c.post("/records", json=list(recs)).get_json()["results"]]


def test_unique_then_exact_and_normalized_duplicate(c):
    assert post(c, {"name": "Ann Lee", "email": "ann@x.com", "phone": "+27 82 123 4567"}) == ["unique"]
    assert post(c, {"name": " ann  LEE ", "email": "Ann+promo@x.com", "phone": "0821234567"}) == ["redundant"]
    assert len(c.get("/records").get_json()) == 1


def test_false_positives(c):
    assert post(c, {"name": "test", "email": "a@x.com"}, {"name": "Bo Li", "email": "nope"}) == ["false_positive"] * 2
    assert c.get("/records").get_json() == []


def test_near_duplicate(c):
    assert post(c, {"name": "Jonathan Smith", "email": "jsmith@x.com", "phone": "0821111111"},
                {"name": "Jonathon Smith", "email": "jon.smith@x.com", "phone": "0822222222"}) == ["unique", "redundant"]


def test_duplicate_inside_one_batch(c):
    r = {"name": "Bob Ray", "email": "bob@y.com"}
    assert post(c, r, r) == ["unique", "redundant"]
    assert c.get("/stats").get_json() == {"stored": 1, "rejected": {"redundant": 1}}
