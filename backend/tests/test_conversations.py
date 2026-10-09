import json

from kapiling.chat import conversations
from tests.test_agui import run_data, sse


def get_conv(client, cid):
    r = client.get(f"/api/conversations/{cid}")
    assert r.status_code == 200, r.text
    return r.json()


def test_server_creates_conversation_and_reuses_it(client, lola_unlocked, echo_agent):
    first = sse(client.post("/api/runs", data=run_data(lola_unlocked, message="Ano ang gamot ko?")))
    tid = first[0]["threadId"]
    second = sse(client.post("/api/runs", data=run_data(lola_unlocked, message="Salamat", conversation_id=tid)))
    assert second[0]["threadId"] == tid and len(get_conv(client, tid)["messages"]) == 4
    conv = get_conv(client, tid)
    assert conv["title"] == "Ano ang gamot ko?"
    assert [m["role"] for m in conv["messages"]] == ["user", "assistant", "user", "assistant"]
    m = conv["messages"][1]
    assert {"id", "role", "content", "mode", "status", "blocks", "steps", "sources", "attachments", "created"} <= set(m)
    assert m["id"] == first[-1]["result"]["messageId"] and m["steps"] == ["check_profile"]


def test_title_is_first_user_text_trimmed(con, lola):
    # The brief asserted on create()'s return value, but create() returns the conversation id (the threadId),
    # so the title is read back from the row.
    cid = conversations.create(con, lola, "  Ano ang gamot ko sa BP? Kasi nakalimutan ko  ")
    title = con.execute("select title from conversations where id=?", (cid,)).fetchone()[0]
    assert title.startswith("Ano ang gamot ko sa BP?")


def test_title_is_cut_at_sentence_end_or_60_chars(con, lola):
    def title(text, **kw):
        cid = conversations.create(con, lola, text, **kw)
        return con.execute("select title from conversations where id=?", (cid,)).fetchone()[0]

    assert title("  Ano ang gamot ko sa BP? Kasi nakalimutan ko  ") == "Ano ang gamot ko sa BP?"
    assert title("Losartan 50.5 mg ba ito. Oo") == "Losartan 50.5 mg ba ito."
    long = "salita " * 20
    assert len(title(long)) <= 60 and title(long).startswith("salita salita")
    assert title("Usap tayo", mode="usap", lang="tl", today="2026-10-10") == "Usap noong 2026-10-10"
    assert title("anything", mode="usap", lang="en", today="2026-10-10") == "Talk on 2026-10-10"
    assert title("   ", lang="en") == "New chat"


def test_other_profiles_conversation_is_403(client, mika_unlocked, lola_conversation):
    assert client.get(f"/api/conversations/{lola_conversation}").status_code == 403
    assert client.patch(f"/api/conversations/{lola_conversation}", json={"title": "x"}).status_code == 403
    assert client.delete(f"/api/conversations/{lola_conversation}").status_code == 403


def test_conversation_routes_require_session(client, lola, lola_conversation):
    assert client.get(f"/api/conversations/{lola_conversation}").status_code == 401
    assert client.get(f"/api/profiles/{lola}/conversations").status_code == 401


def test_unknown_conversation_is_404(client, lola_unlocked):
    assert client.get("/api/conversations/nope").status_code == 404
    assert client.patch("/api/conversations/nope", json={"title": "x"}).status_code == 404
    assert client.delete("/api/conversations/nope").status_code == 404


def test_list_rename_delete(client, con, lola_unlocked, lola_conversation):
    r = client.get(f"/api/profiles/{lola_unlocked}/conversations")
    assert r.status_code == 200
    assert [set(c) for c in r.json()] == [{"id", "title", "updated"}]
    assert r.json()[0]["id"] == lola_conversation
    assert client.patch(f"/api/conversations/{lola_conversation}", json={"title": "  Mga gamot  "}).status_code == 204
    assert get_conv(client, lola_conversation)["title"] == "Mga gamot"
    assert client.patch(f"/api/conversations/{lola_conversation}", json={"title": "   "}).status_code == 400
    assert client.delete(f"/api/conversations/{lola_conversation}").status_code == 204
    assert client.get(f"/api/conversations/{lola_conversation}").status_code == 404
    assert con.execute("select count(*) from messages where conversation_id=?", (lola_conversation,)).fetchone()[0] == 0


def test_list_is_newest_first_and_per_profile(client, con, lola_unlocked, mika):
    a = conversations.create(con, lola_unlocked, "Una")
    b = conversations.create(con, lola_unlocked, "Pangalawa")
    conversations.create(con, mika, "Kay Mika")
    con.execute("update conversations set updated='2026-01-01 00:00:00' where id=?", (b,))
    con.execute("update conversations set updated='2026-02-01 00:00:00' where id=?", (a,))
    con.commit()
    assert [c["id"] for c in client.get(f"/api/profiles/{lola_unlocked}/conversations").json()] == [a, b]


def test_append_updates_conversation_and_stores_json(con, lola):
    cid = conversations.create(con, lola, "Hi")
    con.execute("update conversations set updated='2000-01-01 00:00:00' where id=?", (cid,))
    mid = conversations.append(con, cid, "assistant", "Ok", status="stopped", blocks=[{"type": "disclaimer"}],
                               steps=["search_records"], sources=[{"n": 1}], mode="voice")
    assert len(mid) == 32
    row = con.execute("select * from messages where id=?", (mid,)).fetchone()
    assert row["status"] == "stopped" and row["mode"] == "voice"
    assert json.loads(row["blocks"]) == [{"type": "disclaimer"}] and json.loads(row["steps"]) == ["search_records"]
    assert con.execute("select updated from conversations where id=?", (cid,)).fetchone()[0] != "2000-01-01 00:00:00"


def test_history_is_last_n_oldest_first(con, lola):
    cid = conversations.create(con, lola, "q0")
    for i in range(8):
        conversations.append(con, cid, "user", f"q{i}")
        conversations.append(con, cid, "assistant", f"a{i}")
    h = conversations.history(con, cid)
    assert len(h) == 12 and h[0] == {"role": "user", "content": "q2"} and h[-1] == {"role": "assistant", "content": "a7"}
    assert conversations.history(con, cid, limit=2) == [{"role": "user", "content": "q7"},
                                                        {"role": "assistant", "content": "a7"}]
