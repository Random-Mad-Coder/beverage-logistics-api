from typing import Callable
from fastapi.testclient import TestClient


def test_create_beverage_success(client: TestClient):
    response = client.post("/beverages", json={"name": "Jenkins Pils", "type": "beer"})
    assert response.status_code == 201

    data = response.json()
    assert "id" in data
    assert data["name"] == "Jenkins Pils"
    assert data["type"] == "beer"


def test_create_beverage_duplicate_name_409(client: TestClient, beverage: int):
    response = client.post("/beverages", json={"name": "Jenkins Cola", "type": "soft_drink"})
    assert response.status_code == 409
    assert isinstance(response.json()["detail"], str)

    response = client.get("/beverages")
    assert response.status_code == 200
    assert [item["id"] for item in response.json()] == [beverage]


def test_create_beverage_invalid_type_422(client: TestClient):
    response = client.post("/beverages", json={"name": "Jenkins Wine", "type": "wine"})
    assert response.status_code == 422


def test_get_beverage_success(client: TestClient, beverage: int):
    response = client.get(f"/beverages/{beverage}")
    assert response.status_code == 200
    assert response.json() == {"id": beverage, "name": "Jenkins Cola", "type": "soft_drink"}


def test_get_beverage_not_found_404(client: TestClient):
    response = client.get("/beverages/1")
    assert response.status_code == 404


def test_list_beverages_empty(client: TestClient):
    response = client.get("/beverages")
    assert response.status_code == 200
    assert response.json() == []


def test_list_beverages_filter_name(client: TestClient, beverage: int):
    response = client.post("/beverages", json={"name": "Jenkins Pils", "type": "beer"})
    assert response.status_code == 201

    response = client.get("/beverages", params={"name": "Jenkins Cola"})
    assert response.status_code == 200
    assert [item["id"] for item in response.json()] == [beverage]


def test_list_beverages_filter_beverage_type(client: TestClient, beverage: int):
    response = client.post("/beverages", json={"name": "Jenkins Pils", "type": "beer"})
    assert response.status_code == 201
    beer = response.json()["id"]

    response = client.get("/beverages", params={"beverage_type": "beer"})
    assert response.status_code == 200
    assert [item["id"] for item in response.json()] == [beer]


def test_delete_beverage_success(client: TestClient, beverage: int):
    response = client.delete(f"/beverages/{beverage}")
    assert response.status_code == 204

    response = client.get(f"/beverages/{beverage}")
    assert response.status_code == 404


def test_delete_beverage_not_found_404(client: TestClient):
    response = client.delete("/beverages/1")
    assert response.status_code == 404


def test_delete_beverage_referenced_by_packaging_unit_409(client: TestClient, beverage: int, make_unit: Callable[..., dict]):
    make_unit(beverage)

    response = client.delete(f"/beverages/{beverage}")
    assert response.status_code == 409
    assert isinstance(response.json()["detail"], str)

    response = client.get(f"/beverages/{beverage}")
    assert response.status_code == 200


def test_delete_beverage_referenced_by_pallet_409(client: TestClient, beverage: int, pallet: int):
    response = client.delete(f"/beverages/{beverage}")
    assert response.status_code == 409
    assert isinstance(response.json()["detail"], str)

    response = client.get(f"/beverages/{beverage}")
    assert response.status_code == 200
