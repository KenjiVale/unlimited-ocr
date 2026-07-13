from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_health_does_not_load_model() -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "app_env": "development", "model_loaded": False}


def test_gpu_endpoint_is_graceful() -> None:
    response = client.get("/api/system/gpu")
    assert response.status_code == 200
    body = response.json()
    assert isinstance(body["cuda_available"], bool)
    assert "torch_version" in body

