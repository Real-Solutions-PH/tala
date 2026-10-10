"""The agent loop (Task 12), driven by a scripted fake LLM through the `agent._llm_stream` seam."""

import asyncio
import base64
import json

import httpx
import pytest

from kapiling.chat import agent, conversations, runs, safety
from kapiling.chat.agent import RunCtx, stream_run


# --- OpenAI-style chunks ------------------------------------------------------------

def text(s: str) -> dict:
    return {"choices": [{"index": 0, "delta": {"content": s}}]}


def tool_call(name: str, args: dict, call_id: str = "c1", index: int = 0) -> dict:
    return {"choices": [{"index": 0, "delta": {"tool_calls": [
        {"index": index, "id": call_id, "type": "function", "function": {"name": name, "arguments": json.dumps(args)}}]}}]}


def tool_call_split(name: str, args: dict, call_id: str = "c1") -> list[dict]:
    """The same call, its arguments split over three deltas (as llama-server streams them)."""
    a = json.dumps(args)
    third = max(1, len(a) // 3)
    parts = [a[:third], a[third:2 * third], a[2 * third:]]
    first = {"choices": [{"index": 0, "delta": {"tool_calls": [
        {"index": 0, "id": call_id, "type": "function", "function": {"name": name, "arguments": parts[0]}}]}}]}
    rest = [{"choices": [{"index": 0, "delta": {"tool_calls": [{"index": 0, "function": {"arguments": p}}]}}]}
            for p in parts[1:]]
    return [first, *rest]


class FakeLLM:
    """Each call to the seam plays the next scripted step. Records every request payload."""

    def __init__(self):
        self.steps: list[list[dict]] = []
        self.payloads: list[dict] = []
        self.closed = 0
        self.delay = 0.0

    def script(self, *steps):
        self.steps = [list(s) for s in steps]

    async def stream(self, payload):
        self.payloads.append(json.loads(json.dumps(payload)))
        step = self.steps.pop(0) if self.steps else [text("")]
        try:
            for chunk in step:
                if self.delay:
                    await asyncio.sleep(self.delay)
                yield chunk
        finally:
            self.closed += 1


@pytest.fixture
def fake_llm(monkeypatch):
    f = FakeLLM()
    monkeypatch.setattr(agent, "_llm_stream", f.stream)
    return f


@pytest.fixture
def slow_fake_llm(fake_llm):
    fake_llm.delay = 0.03
    fake_llm.script([text(f"w{i} ") for i in range(50)])
    return fake_llm


@pytest.fixture
def down_llm(monkeypatch):
    async def down(payload):
        raise agent.LLMUnavailable("ConnectError")
        yield  # pragma: no cover - makes this an async generator

    monkeypatch.setattr(agent, "_llm_stream", down)


@pytest.fixture
def fake_tts(monkeypatch):
    from kapiling.voice import tts

    spoken = []

    def speak(s, lang):
        spoken.append((s, lang))
        return f"WAV:{s}".encode()

    monkeypatch.setattr(tts, "speak", speak)
    return spoken


@pytest.fixture
def ctx_factory(con, lola):
    def make(user_text: str, *, lang: str = "tl", speak: bool = False, images=None) -> RunCtx:
        cid = conversations.create(con, lola, user_text)
        conversations.append(con, cid, "user", user_text)
        return RunCtx(con=con, run=runs.Run(profile_id=lola), profile_id=lola, conversation_id=cid, lang=lang,
                      mode="text", speak=speak, user_text=user_text, images=images or [], audio=None,
                      message_id="m-test")
    return make


def collect(ctx) -> list[dict]:
    async def go():
        return [e async for e in stream_run(ctx)]
    return asyncio.run(go())


def blocks_of(ev) -> list[dict]:
    return [e["value"] for e in ev if e["type"] == "CUSTOM" and e["name"] == "block"]


def answer(ev) -> str:
    return "".join(e["delta"] for e in ev if e["type"] == "TEXT_MESSAGE_CONTENT")


# --- the brief's tests -----------------------------------------------------------------

def test_plain_answer_streams_tokens_in_order(ctx_factory, fake_llm):
    fake_llm.script([text("Losartan "), text("po.")])
    ev = collect(ctx_factory("ano gamot ko"))
    assert answer(ev) == "Losartan po."
    types = [e["type"] for e in ev]
    assert types[0] == "TEXT_MESSAGE_START" and types[-1] == "TEXT_MESSAGE_END"
    assert {e["messageId"] for e in ev if e["type"].startswith("TEXT_MESSAGE")} == {"m-test"}  # server-side id


def test_tool_call_emits_step_and_block(ctx_factory, fake_llm):
    fake_llm.script([tool_call("get_medications", {})], [text("Tatlo po.")])
    ev = collect(ctx_factory("mga gamot ko"))
    kinds = [(e["type"], e.get("stepName") or e.get("name") or e.get("toolCallName")) for e in ev]
    assert ("STEP_STARTED", "check_meds") in kinds and ("CUSTOM", "block") in kinds
    assert kinds.index(("STEP_STARTED", "check_meds")) < kinds.index(("STEP_FINISHED", "check_meds"))
    assert ("TOOL_CALL_START", "get_medications") in kinds
    assert blocks_of(ev)[0]["type"] == "med_list"
    assert answer(ev) == "Tatlo po."
    # The second request carries the assistant tool call and the tool result.
    msgs = fake_llm.payloads[1]["messages"]
    assert msgs[-2]["role"] == "assistant" and msgs[-2]["tool_calls"][0]["function"]["name"] == "get_medications"
    assert msgs[-1]["role"] == "tool" and msgs[-1]["tool_call_id"] == "c1"
    assert "Metformin" in msgs[-1]["content"]


def test_tool_call_arguments_split_over_deltas(ctx_factory, fake_llm):
    fake_llm.script(tool_call_split("get_profile", {"fields": ["blood_type"]}), [text("O+ po.")])
    ev = collect(ctx_factory("blood type ko"))
    assert blocks_of(ev) == [{"type": "profile_fields", "fields": [{"key": "blood_type", "value": "O+"}]}]


def test_meal_plan_always_gets_disclaimer_even_if_model_forgets(ctx_factory, fake_llm):
    fake_llm.script([tool_call("plan_meals", {"days": 3})], [text("Heto po ang plano.")])
    ev = collect(ctx_factory("gawan mo ako ng meal plan"))
    assert {"type": "disclaimer"} in blocks_of(ev)
    assert ("STEP_STARTED", "planning_meals") in [(e["type"], e.get("stepName")) for e in ev]


def test_activities_always_get_disclaimer(ctx_factory, fake_llm):
    fake_llm.script([tool_call("suggest_activities", {})], [text("Maglakad po.")])
    ev = collect(ctx_factory("anong ehersisyo"))
    assert {"type": "disclaimer"} in blocks_of(ev)


def test_disclaimer_is_not_repeated(ctx_factory, fake_llm):
    fake_llm.script([tool_call("plan_meals", {}, "c1"), tool_call("suggest_activities", {}, "c2", index=1)],
                    [text("Heto po.")])
    ev = collect(ctx_factory("pagkain at ehersisyo"))
    assert blocks_of(ev).count({"type": "disclaimer"}) == 1


def test_cancel_stops_and_closes_upstream(ctx_factory, slow_fake_llm):
    ctx = ctx_factory("mahabang sagot")

    async def go():
        out = []
        async for e in stream_run(ctx):
            out.append(e)
            if e["type"] == "TEXT_MESSAGE_CONTENT" and len(out) == 4:
                ctx.run.cancel.set()
        return out

    ev = asyncio.run(go())
    assert len(answer(ev).split()) < 10  # stopped early
    assert ev[-1]["type"] == "TEXT_MESSAGE_END"
    assert slow_fake_llm.closed == 1  # the upstream stream was closed, which stops llama-server generating


def test_llm_down_is_run_error_with_key(ctx_factory, down_llm):
    ev = collect(ctx_factory("kumusta"))
    assert ev[-1]["type"] == "RUN_ERROR" and ev[-1]["message"] == "errors.llm_unavailable"
    assert ev[-1]["code"] == "llm_unavailable"


def test_llm_down_mid_answer_closes_text_before_error(ctx_factory, monkeypatch):
    async def flaky(payload):
        yield text("Kal")
        raise httpx.ReadError("gone")

    monkeypatch.setattr(agent, "_llm_stream", flaky)
    ev = collect(ctx_factory("kumusta"))
    assert [e["type"] for e in ev[-2:]] == ["TEXT_MESSAGE_END", "RUN_ERROR"]


def test_speak_emits_audio_in_sentence_order(ctx_factory, fake_llm, fake_tts):
    fake_llm.script([text("Una po ito. "), text("Pangalawa po. "), text("Huli po")])
    ev = collect(ctx_factory("magsalita ka", speak=True))
    audio = [e["value"] for e in ev if e.get("name") == "audio"]
    assert [a["seq"] for a in audio] == [0, 1, 2]
    assert [base64.b64decode(a["wav_b64"]).decode() for a in audio] == [
        "WAV:Una po ito.", "WAV:Pangalawa po.", "WAV:Huli po"]
    assert all(lang == "tl" for _, lang in fake_tts)


def test_no_audio_without_speak(ctx_factory, fake_llm, fake_tts):
    fake_llm.script([text("Una po ito. ")])
    ev = collect(ctx_factory("tahimik"))
    assert not [e for e in ev if e.get("name") == "audio"] and fake_tts == []


def test_tts_failure_does_not_break_the_answer(ctx_factory, fake_llm, monkeypatch):
    from kapiling.voice import tts

    def broken(s, lang):
        raise RuntimeError("no model")

    monkeypatch.setattr(tts, "speak", broken)
    fake_llm.script([text("Una po ito. "), text("Dalawa po.")])
    ev = collect(ctx_factory("x", speak=True))
    assert answer(ev) == "Una po ito. Dalawa po." and ev[-1]["type"] == "TEXT_MESSAGE_END"


def test_unknown_tool_is_reported_to_model_not_crash(ctx_factory, fake_llm):
    fake_llm.script([tool_call("launch_rockets", {})], [text("Hindi ko po kaya iyon.")])
    ev = collect(ctx_factory("x"))
    assert answer(ev) == "Hindi ko po kaya iyon."
    tool_msg = fake_llm.payloads[1]["messages"][-1]
    assert tool_msg["role"] == "tool" and json.loads(tool_msg["content"])["error"] == "unknown_tool"


def test_bad_tool_arguments_are_reported_to_model(ctx_factory, fake_llm):
    bad = {"choices": [{"index": 0, "delta": {"tool_calls": [
        {"index": 0, "id": "c1", "function": {"name": "get_lab_results", "arguments": "{not json"}}]}}]}
    fake_llm.script([bad], [text("Pasensya po.")])
    ev = collect(ctx_factory("x"))
    assert json.loads(fake_llm.payloads[1]["messages"][-1]["content"])["error"] == "bad_arguments"
    assert answer(ev) == "Pasensya po."


def test_loop_stops_after_five_steps(ctx_factory, fake_llm):
    fake_llm.script(*[[tool_call("get_medications", {}, f"c{i}")] for i in range(8)])
    ev = collect(ctx_factory("x"))
    assert len(fake_llm.payloads) == agent.MAX_STEPS == 5
    assert ev  # finished without crashing


def test_request_shape(ctx_factory, fake_llm):
    fake_llm.script([text("Opo.")])
    collect(ctx_factory("Ano ang maintenance ko?"))
    p = fake_llm.payloads[0]
    assert p["stream"] is True and p["temperature"] == 0.2
    names = {t["function"]["name"] for t in p["tools"]}
    assert {"get_profile", "get_medications", "get_lab_results", "show_card", "get_vaccines", "search_records",
            "answer_form", "plan_meals", "suggest_activities", "decline_medical_advice"} <= names
    msgs = p["messages"]
    assert msgs[0]["role"] == "system" and "Metformin" in msgs[0]["content"]  # the essential summary
    # history() already includes the current user message: it is sent exactly once.
    assert [m["content"] for m in msgs if m["role"] == "user"] == ["Ano ang maintenance ko?"]


def test_history_is_sent(con, ctx_factory, fake_llm):
    ctx = ctx_factory("una")
    conversations.append(con, ctx.conversation_id, "assistant", "sagot")
    conversations.append(con, ctx.conversation_id, "user", "pangalawa")
    fake_llm.script([text("Opo.")])
    collect(ctx)
    assert [(m["role"], m["content"]) for m in fake_llm.payloads[0]["messages"][1:]] == [
        ("user", "una"), ("assistant", "sagot"), ("user", "pangalawa")]


def test_images_go_to_the_model_with_the_user_message(ctx_factory, fake_llm):
    png = b"\x89PNG\r\n\x1a\n" + b"0" * 10
    fake_llm.script([text("Nakita ko po.")])
    collect(ctx_factory("ano ito", images=[png]))
    last = fake_llm.payloads[0]["messages"][-1]
    assert last["role"] == "user" and isinstance(last["content"], list)
    kinds = [p["type"] for p in last["content"]]
    assert kinds == ["text", "image_url"]
    assert last["content"][1]["image_url"]["url"].startswith("data:image/png;base64,")


# --- safety ---------------------------------------------------------------------------

def test_decline_tool_emits_refusal(ctx_factory, fake_llm):
    fake_llm.script([tool_call("decline_medical_advice", {"kind": "diagnosis"})], [text("Magtanong po sa doktor.")])
    ev = collect(ctx_factory("ano kaya ito"))
    assert {"type": "refusal", "kind": "diagnosis"} in blocks_of(ev)


@pytest.mark.parametrize("question,kind", [
    ("Puwede ko bang itigil ang Metformin?", "medication"),
    ("Pwede bang ihinto ko na ang Losartan", "medication"),
    ("Doblehin ko ba ang gamot?", "medication"),
    ("Can I stop taking Amlodipine?", "medication"),
    ("Should I double my Metformin?", "medication"),
    ("Can I increase my dose?", "medication"),
    ("Ano ang sakit ko?", "diagnosis"),
    ("Can you diagnose this rash?", "diagnosis"),
])
def test_precheck_forces_refusal_even_if_model_ignores_it(ctx_factory, fake_llm, question, kind):
    # The model answers as if it had never been told: no tool call, plain (bad) advice.
    fake_llm.script([text("Sige po, itigil na ninyo.")])
    ev = collect(ctx_factory(question))
    assert blocks_of(ev).count({"type": "refusal", "kind": kind}) == 1
    # The model was told a fixed refusal is shown.
    msgs = fake_llm.payloads[0]["messages"]
    assert f"fixed {kind} refusal card is already shown" in msgs[-1]["content"] and msgs[-1]["role"] == "user"
    assert "already shown" not in msgs[0]["content"]  # the system prompt (a cached prefix) is unchanged


def test_precheck_and_tool_give_one_refusal(ctx_factory, fake_llm):
    fake_llm.script([tool_call("decline_medical_advice", {"kind": "medication"})], [text("Doktor po.")])
    ev = collect(ctx_factory("Puwede ko bang itigil ang Metformin?"))
    assert blocks_of(ev).count({"type": "refusal", "kind": "medication"}) == 1


def test_precheck_leaves_ordinary_questions_alone():
    assert safety.precheck("Ano ang maintenance ko?") is None
    assert safety.precheck("Show my PhilHealth") is None
    assert safety.precheck("Kumusta ang blood sugar ko?") is None
    assert safety.precheck("Puwede ko bang ITIGIL ang Metformin?") == "medication"


@pytest.mark.parametrize("question", ["Do I have allergies?", "May allergy ba ako?", "Ano ang mga gamot ko?",
                                      "When was I diagnosed with diabetes?", "Kailan itinigil ang Amlodipine?"])
def test_precheck_ignores_record_lookups(question):
    assert safety.precheck(question) is None


def test_record_lookup_gets_no_refusal_block(ctx_factory, fake_llm):
    fake_llm.script([text("Penicillin at shrimp po.")])
    ev = collect(ctx_factory("Do I have allergies?"))
    assert not [b for b in blocks_of(ev) if b["type"] == "refusal"]
    assert "already shown" not in fake_llm.payloads[0]["messages"][-1]["content"]


def test_bad_refusal_kind_is_normalised(ctx_factory, fake_llm):
    fake_llm.script([tool_call("decline_medical_advice", {"kind": "surgery"})], [text("Doktor po.")])
    ev = collect(ctx_factory("x"))
    assert {"type": "refusal", "kind": "medication"} in blocks_of(ev)


# --- search failure ----------------------------------------------------------------------

@pytest.mark.parametrize("exc", ["embed", "rerank"])
def test_search_unavailable_is_a_tool_result_not_a_crash(ctx_factory, fake_llm, monkeypatch, exc):
    from kapiling.docs import ingest, retrieve

    def boom(*a, **k):
        raise (ingest.EmbedUnavailable if exc == "embed" else retrieve.RerankUnavailable)("down")

    monkeypatch.setattr(retrieve, "search", boom)
    fake_llm.script([tool_call("search_records", {"query": "blood sugar"})], [text("Hindi ko po ma-search.")])
    ev = collect(ctx_factory("blood sugar"))
    result = json.loads(fake_llm.payloads[1]["messages"][-1]["content"])
    assert result["error"] == "search_unavailable" and "unavailable" in result["message"]
    assert answer(ev) == "Hindi ko po ma-search."
    assert not [e for e in ev if e["type"] == "RUN_ERROR"]


def test_search_records_emits_sources_and_document_blocks(con, lola, ctx_factory, fake_llm, monkeypatch):
    from kapiling.docs import retrieve

    did = con.execute("insert into documents (profile_id, title, kind, date, file_path, mime, sha256, status) "
                      "values (?,?,?,?,?,?,?, 'indexed')",
                      (lola, "FBS and HbA1c", "lab", "2026-03-02", "x/1.jpg", "image/jpeg", "s1")).lastrowid
    con.commit()
    hit = retrieve.Hit(chunk_id=7, document_id=did, title="FBS and HbA1c", headings=[], page=1, bbox=None,
                       text="Fasting blood sugar 130 mg/dL.", score=2.0)
    monkeypatch.setattr(retrieve, "search", lambda c, pid, q, k=6: [hit, hit])
    fake_llm.script([tool_call("search_records", {"query": "blood sugar"})], [text("130 po [1].")])
    ev = collect(ctx_factory("blood sugar"))
    sources = [e["value"] for e in ev if e.get("name") == "sources"]
    assert sources and sources[0][0]["n"] == 1 and sources[0][0]["document_id"] == did
    docs = [b for b in blocks_of(ev) if b["type"] == "document"]
    assert docs == [{"type": "document", "document_id": did, "title": "FBS and HbA1c", "date": "2026-03-02",
                     "thumb_url": f"/api/documents/{did}/page/1.png"}]  # one block per distinct document
    result = json.loads(fake_llm.payloads[1]["messages"][-1]["content"])
    assert "_sources" not in result and result["passages"][0]["n"] == 1


def test_timer_stamps_first_token(ctx_factory, fake_llm):
    from kapiling.voice.timing import TurnTimer

    ctx = ctx_factory("x")
    ctx.timer = TurnTimer()
    fake_llm.script([text("Opo.")])
    ev = collect(ctx)
    assert "first_token" in ctx.timer.as_dict()
    timing = [e["value"] for e in ev if e.get("name") == "timing"]
    assert timing and "first_token" in timing[0]


def test_sagutan_ang_form_with_photo_gives_form_answers_block(ctx_factory, fake_llm, monkeypatch):
    from kapiling.chat import form

    def fake_answer_form(con, pid, image, mime, lang, on_step=None):
        on_step("reading_form")
        on_step("answering_form")
        return {"answered": 1, "total": 1}, [{"type": "form_answers", "items": [{"field": "Name", "answer": "Lola", "source": "profile"}]}]

    monkeypatch.setattr(form, "answer_form", fake_answer_form)
    fake_llm.script([tool_call("answer_form", {})], [text("Tapos na po.")])
    ev = collect(ctx_factory("sagutan ang form", images=[b"\x89PNG fake"]))
    assert [b["type"] for b in blocks_of(ev)] == ["form_answers"]
    steps = [e["stepName"] for e in ev if e["type"] == "STEP_STARTED"]
    assert steps == ["reading_form", "answering_form"]


def test_form_without_photo_asks_for_one(ctx_factory, fake_llm):
    fake_llm.script([tool_call("answer_form", {})], [text("Kuhanan po ng litrato.")])
    ev = collect(ctx_factory("sagutan ang form"))
    assert blocks_of(ev) == []
    assert "no_form_photo" in fake_llm.payloads[1]["messages"][-1]["content"]
