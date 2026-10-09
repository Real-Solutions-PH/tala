"""Smoke test for the model servers started by ./run.sh. Skipped when they are down."""

import httpx
import pytest

EMBED = "http://127.0.0.1:8082"
RERANK = "http://127.0.0.1:8083"


def _up() -> bool:
    try:
        return httpx.get(f"{EMBED}/health", timeout=1).status_code == 200
    except httpx.HTTPError:
        return False


pytestmark = pytest.mark.skipif(
    not _up(), reason="model servers are down (GET :8082/health failed); start them with ./run.sh"
)


def test_embedding_has_1024_dimensions():
    r = httpx.post(f"{EMBED}/v1/embeddings", json={"input": ["gamot sa BP"]}, timeout=60)
    r.raise_for_status()
    assert len(r.json()["data"][0]["embedding"]) == 1024


def test_reranker_ranks_losartan_above_pancit_canton():
    docs = ["pancit canton", "Losartan 50 mg"]
    r = httpx.post(f"{RERANK}/v1/rerank", json={"query": "gamot sa BP", "documents": docs}, timeout=60)
    r.raise_for_status()
    score = {x["index"]: x["relevance_score"] for x in r.json()["results"]}
    assert score[1] > score[0]
