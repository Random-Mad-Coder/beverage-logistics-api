from fastapi.testclient import TestClient
from datetime import date

def test_create_delivery_success(client: TestClient):
    keg_ids = []

    for i in range(2):
        response = client.post("/kegs", json={"size": "50l", "variety": "pilsener", "status": "full"})
        assert response.status_code == 201
        keg_ids.append(response.json()["id"])

    today = date.today()
    response = client.post("/deliveries", json={"customer": "Café Jenkins", "date": today.strftime("%Y-%m-%d"), "keg_ids": keg_ids})
    assert response.status_code == 201

    data = response.json()
    assert "id" in data
    assert data["customer"] == "Café Jenkins"
    assert data["date"] == today.strftime("%Y-%m-%d")
    assert data["keg_ids"] == keg_ids