from types import SimpleNamespace

import pytest

from eval import run_eval as ev


def hit(title, score):
    return SimpleNamespace(title=title, score=score)


DOC = lambda t: {"id": 1, "lang": "en", "q": "q", "expect": {"document_title": t}}  # noqa: E731
OFF = {"id": 2, "lang": "en", "q": "off", "expect": {"no_hit": True}}


def test_questions_file_matches_the_brief():
    qs = ev.load_questions(ev.QUESTIONS)
    kinds = [next(iter(q["expect"])) for q in qs]
    assert len(qs) == 40
    assert {k: kinds.count(k) for k in set(kinds)} == {"document_title": 25, "no_hit": 5, "refusal": 5, "disclaimer": 5}
    assert sum(q["lang"] == "tl" for q in qs) == 20


def test_recall_arithmetic():
    ranked = {
        "a": [hit("A", 5), hit("B", 4)],        # right at rank 1
        "b": [hit("A", 5), hit("B", 4)],        # right at rank 2
        "c": [hit("A", 5), hit("X", -9)],       # wrong
    }
    qs = [{"id": 1, "q": "a", "expect": {"document_title": "A"}}, {"id": 2, "q": "b", "expect": {"document_title": "B"}},
          {"id": 3, "q": "c", "expect": {"document_title": "B"}}]
    rows = ev.sweep(qs, lambda q: ranked[q], [-10.0])
    assert rows[0]["recall1"] == pytest.approx(1 / 3)
    assert rows[0]["recall6"] == pytest.approx(2 / 3)


def test_floor_drops_hits_and_counts_off_topic():
    ranked = {"d": [hit("A", 2.0), hit("B", -4.0)], "off": [hit("A", -2.0)]}
    qs = [{"id": 1, "q": "d", "expect": {"document_title": "B"}}, {"id": 2, "q": "off", "expect": {"no_hit": True}}]
    rows = {r["floor"]: r for r in ev.sweep(qs, lambda q: ranked[q], [-5.0, -3.0, 0.0])}
    assert rows[-5.0]["recall6"] == 1.0 and rows[-5.0]["off_topic"] == 1
    assert rows[-3.0]["recall6"] == 0.0 and rows[-3.0]["off_topic"] == 1
    assert rows[0.0]["off_topic"] == 0


def test_candidate_floors():
    f = ev.candidate_floors()
    assert f[0] == -5.0 and f[-1] == 5.0 and len(f) == 21 and f[1] - f[0] == 0.5


def test_choose_floor_keeps_max_recall_then_fewest_off_topic():
    rows = [
        {"floor": -2.0, "recall6": 1.0, "off_topic": 3},
        {"floor": -1.0, "recall6": 1.0, "off_topic": 1},
        {"floor": 0.0, "recall6": 1.0, "off_topic": 1},
        {"floor": 1.0, "recall6": 0.8, "off_topic": 0},   # loses recall: never chosen
    ]
    assert ev.choose_floor(rows)["floor"] == -1.0   # lowest floor among the ties


SSE = (
    'data: {"type":"RUN_STARTED","threadId":"t","runId":"r"}\n\n'
    'data: {"type":"TEXT_MESSAGE_CONTENT","messageId":"m","delta":"hi"}\n\n'
    ': keepalive\n\n'
    'data: {"type":"CUSTOM","name":"block","value":{"type":"refusal","kind":"medication"}}\n\n'
    'data: {"type":"RUN_FINISHED","threadId":"t","runId":"r","result":{"messageId":"m","status":"complete"}}\n\n'
)


def test_parse_sse_and_blocks():
    events = ev.parse_sse(SSE.splitlines())
    assert [e["type"] for e in events] == ["RUN_STARTED", "TEXT_MESSAGE_CONTENT", "CUSTOM", "RUN_FINISHED"]
    assert ev.blocks(events) == [{"type": "refusal", "kind": "medication"}]


def test_safety_verdicts():
    refusal = ev.parse_sse(SSE.splitlines())
    assert ev.check_safety({"refusal": "medication"}, refusal)
    assert not ev.check_safety({"refusal": "diagnosis"}, refusal)       # wrong kind
    assert not ev.check_safety({"disclaimer": True}, refusal)
    disc = ev.parse_sse(['data: {"type":"CUSTOM","name":"block","value":{"type":"disclaimer"}}', ""])
    assert ev.check_safety({"disclaimer": True}, disc)
    err = ev.parse_sse(['data: {"type":"RUN_ERROR","message":"x","code":"y"}', ""])
    assert not ev.check_safety({"disclaimer": True}, err)


class FakeResp:
    def __init__(self, lines):
        self._lines = lines

    def raise_for_status(self):
        pass

    def iter_lines(self):
        return iter(self._lines)

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class FakeHttp:
    def __init__(self):
        self.posts = []

    def stream(self, method, url, data=None):
        self.posts.append((method, url, data))
        sse = SSE if data["message"] == "ref" else 'data: {"type":"CUSTOM","name":"block","value":{"type":"disclaimer"}}\n\n'
        return FakeResp(sse.splitlines())


def test_safety_pass_counts_through_fake_http():
    qs = [{"id": 1, "q": "ref", "expect": {"refusal": "medication"}, "lang": "en"},
          {"id": 2, "q": "meal", "expect": {"disclaimer": True}, "lang": "tl"},
          {"id": 3, "q": "ref", "expect": {"disclaimer": True}, "lang": "en"}]   # wrong block: fails
    http = FakeHttp()
    rows = ev.safety_pass(qs, http, profile_id=1)
    assert [r["ok"] for r in rows] == [True, True, False]
    assert http.posts[1][2]["lang"] == "tl" and http.posts[1][2]["profile_id"] == 1
    summary = ev.safety_summary(rows)
    assert summary == {"refusal": (1, 1), "disclaimer": (1, 2)}


def test_servers_down_message():
    def down(url):
        raise OSError("refused")
    missing = ev.servers_down({"embed": "http://x", "rerank": "http://y"}, probe=down)
    assert missing == ["embed (http://x)", "rerank (http://y)"]
    assert ev.servers_down({"embed": "http://x"}, probe=lambda u: None) == []
