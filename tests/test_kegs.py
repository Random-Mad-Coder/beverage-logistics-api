from fastapi.testclient import TestClient

def test_create_keg(client: TestClient):
    response = client.post("/kegs", json={"size": "50l", "variety": "pilsener"})
    assert response.status_code == 201

    data = response.json()
    assert data["size"] == "50l"
    assert data["variety"] == "pilsener"
    assert data["status"] == "empty"
    assert "id" in data

def test_get_keg_success_200(client: TestClient):
    response = client.post("/kegs", json={"size": "50l", "variety": "pilsener"})
    assert response.status_code == 201
    created = response.json()

    response = client.get(f"/kegs/{created['id']}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == created["id"]
    assert data["size"] == "50l"
    assert data["variety"] == "pilsener"
    assert data["status"] == "empty"


def test_get_keg_not_found_404(client: TestClient):
    response = client.get("/kegs/1")
    assert response.status_code == 404