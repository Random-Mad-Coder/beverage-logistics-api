from fastapi.testclient import TestClient

def test_inventory_variety_above_threshold_empty_list(client: TestClient):
    reserve = 2
    for i in range(reserve):
        response = client.post("/kegs", json={"size": "50l", "variety": "pilsener", "status": "full"})
        assert response.status_code == 201

    response = client.get("/inventory", params={"reserve": reserve})
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 0

def test_inventory_variety_below_threshold(client: TestClient):
    response = client.post("/kegs", json={"size": "50l", "variety": "pilsener", "status": "full"})
    assert response.status_code == 201

    response = client.get("/inventory", params={"reserve": 2})
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["variety"] == "pilsener"
    assert data[0]["container_type"] == "keg"
    assert data[0]["count"] == 1