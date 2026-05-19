def test_health(client):
    response = client.get("/api/health/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "app_name" in data
    assert "app_version" in data


def test_health_db(client):
    response = client.get("/api/health/db")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "postgres"


def test_health_storage(client):
    response = client.get("/api/health/storage")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert data["service"] == "minio"
