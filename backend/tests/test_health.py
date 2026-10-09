from fastapi.testclient import TestClient
from kapiling.main import app

def test_health_reports_each_model_server():
    r = TestClient(app).get("/api/health")
    assert r.status_code == 200
    assert set(r.json()) == {"llm", "embed", "rerank", "whisper", "tts"}
