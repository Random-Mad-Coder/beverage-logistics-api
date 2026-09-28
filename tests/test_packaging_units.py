from typing import Callable
from fastapi.testclient import TestClient
from datetime import datetime
from dateutil.relativedelta import relativedelta
from constants import DATE_FORMAT_STRING


def test_create_packaging_unit_success(client: TestClient, beverage: int):
    bbdate = datetime.today() + relativedelta(years=1)
    response = client.post("/packaging-units", json={"container_type": "keg_50l", "beverage_id": beverage, "best_before_date": bbdate.strftime(DATE_FORMAT_STRING)})
    assert response.status_code == 201

    data = response.json()
    assert "id" in data
    assert data["container_type"] == "keg_50l"
    assert data["beverage_id"] == beverage
    assert data["status"] == "full"
    assert data["best_before_date"] == bbdate.strftime(DATE_FORMAT_STRING)
    assert data["received_via_pallet_id"] is None


def test_create_packaging_unit_with_pallet_reference(client: TestClient, beverage: int, pallet: int):
    bbdate = datetime.today() + relativedelta(years=1)
    response = client.post("/packaging-units", json={"container_type": "crate_20x05l", "beverage_id": beverage, "best_before_date": bbdate.strftime(DATE_FORMAT_STRING), "received_via_pallet_id": pallet})
    assert response.status_code == 201
    assert response.json()["received_via_pallet_id"] == pallet


def test_create_packaging_unit_invalid_beverage_409(client: TestClient):
    bbdate = datetime.today() + relativedelta(years=1)
    response = client.post("/packaging-units", json={"container_type": "keg_50l", "beverage_id": 999, "best_before_date": bbdate.strftime(DATE_FORMAT_STRING)})
    assert response.status_code == 409
    assert isinstance(response.json()["detail"], str)

    response = client.get("/packaging-units")
    assert response.status_code == 200
    assert response.json() == []


def test_create_packaging_unit_invalid_pallet_409(client: TestClient, beverage: int):
    bbdate = datetime.today() + relativedelta(years=1)
    response = client.post("/packaging-units", json={"container_type": "keg_50l", "beverage_id": beverage, "best_before_date": bbdate.strftime(DATE_FORMAT_STRING), "received_via_pallet_id": 999})
    assert response.status_code == 409


def test_create_packaging_unit_invalid_container_type_422(client: TestClient, beverage: int):
    bbdate = datetime.today() + relativedelta(years=1)
    response = client.post("/packaging-units", json={"container_type": "barrel", "beverage_id": beverage, "best_before_date": bbdate.strftime(DATE_FORMAT_STRING)})
    assert response.status_code == 422


def test_get_packaging_unit_success(client: TestClient, beverage: int, make_unit: Callable[..., dict]):
    created = make_unit(beverage)

    response = client.get(f"/packaging-units/{created['id']}")
    assert response.status_code == 200
    assert response.json() == created


def test_get_packaging_unit_not_found_404(client: TestClient):
    response = client.get("/packaging-units/1")
    assert response.status_code == 404


def test_list_packaging_units_empty(client: TestClient):
    response = client.get("/packaging-units")
    assert response.status_code == 200
    assert response.json() == []


def test_list_packaging_units_filter_beverage_name(client: TestClient, beverage: int, make_unit: Callable[..., dict]):
    response = client.post("/beverages", json={"name": "Jenkins Pils", "type": "beer"})
    assert response.status_code == 201
    other_beverage = response.json()["id"]

    unit = make_unit(beverage)
    make_unit(other_beverage)

    response = client.get("/packaging-units", params={"beverage_name": "Jenkins Cola"})
    assert response.status_code == 200
    assert [item["id"] for item in response.json()] == [unit["id"]]


def test_list_packaging_units_filter_container_type(client: TestClient, beverage: int, make_unit: Callable[..., dict]):
    keg = make_unit(beverage, "keg_30l")
    make_unit(beverage, "crate_24x033l")

    response = client.get("/packaging-units", params={"container_type": "keg_30l"})
    assert response.status_code == 200
    assert [item["id"] for item in response.json()] == [keg["id"]]


def test_list_packaging_units_filter_status(client: TestClient, beverage: int, make_unit: Callable[..., dict]):
    empty_unit = make_unit(beverage)
    make_unit(beverage)

    response = client.patch(f"/packaging-units/{empty_unit['id']}", json={"status": "empty"})
    assert response.status_code == 200

    response = client.get("/packaging-units", params={"status": "empty"})
    assert response.status_code == 200
    assert [item["id"] for item in response.json()] == [empty_unit["id"]]


def test_update_packaging_unit_status(client: TestClient, beverage: int, make_unit: Callable[..., dict]):
    created = make_unit(beverage)

    response = client.patch(f"/packaging-units/{created['id']}", json={"status": "cleaned"})
    assert response.status_code == 200
    assert response.json()["status"] == "cleaned"

    response = client.get(f"/packaging-units/{created['id']}")
    assert response.status_code == 200
    assert response.json()["status"] == "cleaned"


def test_update_packaging_unit_missing_status_422(client: TestClient, beverage: int, make_unit: Callable[..., dict]):
    created = make_unit(beverage)

    response = client.patch(f"/packaging-units/{created['id']}", json={})
    assert response.status_code == 422


def test_update_packaging_unit_not_found_404(client: TestClient):
    response = client.patch("/packaging-units/1", json={"status": "empty"})
    assert response.status_code == 404


def test_delete_packaging_unit_success(client: TestClient, beverage: int, make_unit: Callable[..., dict]):
    created = make_unit(beverage)

    response = client.delete(f"/packaging-units/{created['id']}")
    assert response.status_code == 204

    response = client.get(f"/packaging-units/{created['id']}")
    assert response.status_code == 404


def test_delete_packaging_unit_not_found_404(client: TestClient):
    response = client.delete("/packaging-units/1")
    assert response.status_code == 404


def test_delete_packaging_unit_in_delivery_409(client: TestClient, unpacked_pallet: list[int], delivery: dict):
    response = client.delete(f"/packaging-units/{unpacked_pallet[0]}")
    assert response.status_code == 409
    assert isinstance(response.json()["detail"], str)

    response = client.get(f"/packaging-units/{unpacked_pallet[0]}")
    assert response.status_code == 200
