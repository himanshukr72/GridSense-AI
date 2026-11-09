def test_package_version():
    import gridsense
    assert gridsense.__version__ == "0.1.0"
def test_health_endpoint():
    from fastapi.testclient import TestClient
    from backend.main import app
    assert TestClient(app).get("/health").json()["status"] == "ok"
