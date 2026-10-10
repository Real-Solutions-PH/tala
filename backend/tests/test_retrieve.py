import asyncio
import re

import httpx
import pytest
from langchain_core.documents import Document

from kapiling import config
from kapiling.docs import index, ingest, retrieve
from kapiling.docs.ingest import embed_text
from kapiling.docs.retrieve import RERANK_FLOOR, fts_query, rrf, search, to_sources

# Three hand-written chunks. Each topic has its own direction in the 1024-dim space, so the fake embedder can place
# a query near the chunks that share its topic words.
TOPICS = {"sugar": 0, "fbs": 0, "glucose": 0, "pancit": 1, "noodles": 1, "vaccine": 2, "flu": 2}

LOLA_FBS = ("Clinical Chemistry. Fasting blood sugar (FBS) 130 mg/dL, reference 70-100 mg/dL. "
            "HbA1c 7.2 percent, above the 5.6 limit. Please repeat the test after three months of diet changes.")
LOLA_PANCIT = "Lola's pancit recipe. Boil the noodles for five minutes. Add soy sauce and calamansi to taste."
MIKA_FBS = "Mika school clinic note. Random blood sugar 95 mg/dL, normal. Flu vaccine given on the same day."


def _vector(text: str) -> list[float]:
    v = [0.0] * index.DIM
    v[1023] = 0.01  # never the zero vector, which has no cosine distance
    for tok in re.findall(r"[^\W_]+", text.lower()):
        if tok in TOPICS:
            v[TOPICS[tok]] += 1.0
    return v


class FakeModels:
    def __init__(self):
        self.embed_inputs: list[str] = []
        self.rerank_payloads: list[dict] = []
        self.scores: dict[str, float] = {}  # a word in the document -> fixed rerank score

    async def embed_post(self, payload):
        self.embed_inputs.extend(payload["input"])
        return {"data": [{"index": i, "embedding": _vector(t)} for i, t in enumerate(payload["input"])]}

    def rerank_post(self, payload):
        self.rerank_payloads.append(payload)
        q = set(re.findall(r"[^\W_]+", payload["query"].lower()))
        results = []
        for i, doc in enumerate(payload["documents"]):
            fixed = [s for w, s in self.scores.items() if w in doc.lower()]
            score = fixed[0] if fixed else float(len(q & set(re.findall(r"[^\W_]+", doc.lower()))))
            results.append({"index": i, "relevance_score": score})
        return {"results": results[::-1]}  # llama-server does not promise order


@pytest.fixture
def models(monkeypatch):
    fm = FakeModels()
    monkeypatch.setattr(ingest, "_embed_post", fm.embed_post)
    monkeypatch.setattr(retrieve, "_rerank_post", fm.rerank_post)
    return fm


def _doc(con, pid, title, text, sha):
    did = con.execute("insert into documents (profile_id, title, kind, file_path, mime, sha256, status) "
                      "values (?,?,?,?,?,?, 'indexed')", (pid, title, "lab", f"x/{sha}.md", "text/markdown", sha)).lastrowid
    d = Document(page_content=text, metadata={"title": title, "headings": ["Results"], "page": 1, "bbox": [1, 2, 3, 4]})
    index.write_chunks(con, did, pid, [d], [_vector(text)])
    con.commit()
    return did


@pytest.fixture
def indexed_chunks(con, lola, mika):
    return {
        "lola_fbs": _doc(con, lola, "FBS 2026-03-02", LOLA_FBS, "a"),
        "lola_pancit": _doc(con, lola, "Pancit", LOLA_PANCIT, "b"),
        "mika_fbs": _doc(con, mika, "Clinic note", MIKA_FBS, "c"),
    }


# --- search -------------------------------------------------------------------

def test_profile_isolation_is_inside_the_query(con, lola, mika, indexed_chunks, models):
    mika_docs = {indexed_chunks["mika_fbs"]}
    hits = search(con, mika, "blood sugar")
    assert hits and all(h.document_id in mika_docs for h in hits)
    # Lola's chunks never reached the reranker, so isolation is not a post-filter.
    assert all("Lola" not in d for p in models.rerank_payloads for d in p["documents"])


def test_lola_blood_sugar_ranks_fbs_first(con, lola, indexed_chunks, models):
    hits = search(con, lola, "blood sugar")
    assert hits[0].document_id == indexed_chunks["lola_fbs"]
    assert hits[0].title == "FBS 2026-03-02" and hits[0].page == 1 and hits[0].bbox == [1, 2, 3, 4]
    assert hits[0].text == LOLA_FBS
    assert hits == sorted(hits, key=lambda h: -h.score)


def test_floor_drops_irrelevant(con, lola, indexed_chunks, models):
    assert RERANK_FLOOR == -3.0  # provisional (Task 12); -5 is still below it
    models.scores = {"pancit": -5.0}
    hits = search(con, lola, "pancit noodles blood sugar")
    ids = {h.document_id for h in hits}
    assert indexed_chunks["lola_fbs"] in ids
    assert indexed_chunks["lola_pancit"] not in ids  # it was a candidate (FTS + vector) but scored -5


def test_query_embedding_has_instruction_prefix_and_no_title(con, lola, indexed_chunks, models):
    search(con, lola, "blood sugar")
    assert models.embed_inputs == [
        "Instruct: Given a question about a person's health records, retrieve the passages that answer it\n"
        "Query: blood sugar"]


def test_rerank_payload_is_query_and_bare_chunk_texts(con, lola, indexed_chunks, models):
    search(con, lola, "blood sugar")
    (p,) = models.rerank_payloads
    assert p["query"] == "blood sugar"
    assert set(p["documents"]) <= {LOLA_FBS, LOLA_PANCIT} and LOLA_FBS in p["documents"]


def test_k_limits_hits(con, lola, indexed_chunks, models):
    assert len(search(con, lola, "blood sugar pancit", k=1)) == 1


def test_empty_index_returns_empty_not_error(con, lola):
    assert search(con, lola, "x") == []


@pytest.mark.parametrize("q", ["", "   ", "?!\"()*", "( ) - ^ :"])
def test_query_without_tokens_returns_empty(con, lola, indexed_chunks, models, q):
    assert search(con, lola, q) == []
    assert models.embed_inputs == [] and models.rerank_payloads == []


def test_vector_only_candidates_are_found(con, lola, indexed_chunks, models):
    # "glucose" is not in any chunk text, so FTS finds nothing; the vector side still finds the FBS chunk.
    models.scores = {"glucose": 0.0, "fasting": 3.0}
    hits = search(con, lola, "glucose")
    assert models.rerank_payloads and LOLA_FBS in models.rerank_payloads[0]["documents"]
    assert hits[0].document_id == indexed_chunks["lola_fbs"]


# --- fts_query / rrf ------------------------------------------------------------

def test_fts_query_neutralises_syntax():
    assert fts_query('FBS" OR 1 NEAR(') == '"FBS" OR "OR" OR "1" OR "NEAR"'


def test_fts_query_empty():
    assert fts_query("") == "" and fts_query(" *()\"^ ") == ""


def test_fts_query_is_valid_fts5_for_hostile_input(con, lola, indexed_chunks):
    for q in ['x"', "a AND", "NOT x", "col:val", "x*", "(a OR", "^start", "café ñ"]:
        con.execute("select count(*) from chunks_fts where chunks_fts match ?", (fts_query(q),)).fetchone()


def test_rrf_fuses_two_rankings():
    assert rrf([1, 2, 3], [3, 4], k=60)[0] == 3
    assert set(rrf([1, 2], [3], k=60)) == {1, 2, 3}


# --- to_sources -----------------------------------------------------------------

def _hit(text, cid=7, did=3):
    return retrieve.Hit(chunk_id=cid, document_id=did, title="T", headings=[], page=2, bbox=None, text=text, score=1.0)


def test_sources_carry_before_match_after_strings():
    text = LOLA_FBS
    (s,) = to_sources([_hit(text)], "what was my blood sugar")
    assert s.n == 1 and s.chunk_id == 7 and s.document_id == 3 and s.page == 2 and s.title == "T"
    assert s.match == "Fasting blood sugar (FBS) 130 mg/dL, reference 70-100 mg/dL."
    assert s.before == "Clinical Chemistry. "
    assert s.after == text[len(s.before) + len(s.match):][:80]
    assert len(s.after) == 80
    assert s.before + s.match + s.after in text


def test_sources_number_from_one_in_hit_order():
    srcs = to_sources([_hit(LOLA_FBS, 1), _hit(LOLA_PANCIT, 2), _hit(MIKA_FBS, 3)], "noodles")
    assert [s.n for s in srcs] == [1, 2, 3] and [s.chunk_id for s in srcs] == [1, 2, 3]


def test_sources_fall_back_to_first_160_chars_without_overlap():
    text = "x" * 50 + ". " + "y" * 300
    (s,) = to_sources([_hit(text)], "pancit")
    assert s.match == text[:160] and s.before == "" and s.after == text[160:240]
    assert s.before + s.match + s.after in text


def test_sources_before_is_capped_at_80_and_spans_are_contiguous():
    text = "Filler sentence number one is here. " * 5 + "The FBS was 130 mg/dL today. " + "Tail words go here. " * 6
    for q in ["FBS", "tail words", "filler", "zzz", "130"]:
        (s,) = to_sources([_hit(text)], q)
        assert len(s.before) <= 80 and len(s.after) <= 80
        assert s.before + s.match + s.after in text
    (s,) = to_sources([_hit(text)], "FBS")
    assert s.match == "The FBS was 130 mg/dL today." and len(s.before) == 80


def test_sources_pick_most_overlapping_sentence_across_lines():
    text = "| Test | Result |\n| FBS | 130 mg/dL |\nHbA1c 7.2 percent.\nRepeat in three months."
    (s,) = to_sources([_hit(text)], "HbA1c percent")
    assert s.match == "HbA1c 7.2 percent."
    assert s.before + s.match + s.after in text


# --- live: real embedding and reranking servers ------------------------------------

def _up(url):
    try:
        return httpx.get(f"{url}/health", timeout=1.0).is_success
    except Exception:
        return False


@pytest.mark.skipif(not (_up(config.settings.embed_url) and _up(config.settings.rerank_url)),
                    reason="embedding and reranking servers are not running")
def test_live_blood_sugar_ranks_fbs_document_first(con, lola):
    docs = {
        "FBS and HbA1c": "# Clinical Chemistry\n\n## Results\n\n| Test | Result | Reference |\n|---|---|---|\n"
                         "| Fasting Blood Sugar (FBS) | 130 mg/dL | 70-100 |\n| HbA1c | 7.2 % | 4.0-5.6 |\n",
        "Chest X-ray": "# Radiology Report\n\n## Findings\n\nThe lungs are clear. The heart is not enlarged. "
                       "No pleural effusion.\n",
    }
    ids = {}
    for i, (title, md) in enumerate(docs.items()):
        did = con.execute("insert into documents (profile_id, title, kind, file_path, mime, sha256, status) "
                          "values (?,?,?,?,?,?, 'indexed')", (lola, title, "lab", f"x/{i}.md", "text/markdown", str(i))
                          ).lastrowid
        chunks = ingest._chunk([(ingest._from_markdown(md), 1)], title)
        vectors = asyncio.run(ingest.embed_texts(
            [embed_text(title, c.metadata["headings"], c.page_content) for c in chunks]))
        index.write_chunks(con, did, lola, chunks, vectors)
        ids[title] = did
    hits = search(con, lola, "blood sugar")
    assert hits and hits[0].document_id == ids["FBS and HbA1c"]
