from typing import Callable
from fastapi.testclient import TestClient


def test_inventory_empty(client: TestClient):
    response = client.get("/inventory", params={"reserve": 10})
    assert response.status_code == 200
    assert response.json() == []


def test_inventory_missing_reserve_422(client: TestClient):
    response = client.get("/inventory")
    assert response.status_code == 422


def test_inventory_below_reserve(client: TestClient, beverage: int, make_unit: Callable[..., dict]):
    for _ in range(2):
        make_unit(beverage, "keg_50l")

    response = client.get("/inventory", params={"reserve": 3})
    assert response.status_code == 200
    assert response.json() == [{"beverage_id": beverage, "beverage_name": "Jenkins Cola", "container_type": "keg_50l", "count": 2}]


def test_inventory_at_reserve_not_reported(client: TestClient, beverage: int, make_unit: Callable[..., dict]):
    for _ in range(3):
        make_unit(beverage, "keg_50l")

    response = client.get("/inventory", params={"reserve": 3})
    assert response.status_code == 200
    assert response.json() == []


def test_inventory_kegs_and_crates_counted_separately(client: TestClient, beverage: int, unpacked_pallet: list[int], make_unit: Callable[..., dict]):
    for _ in range(2):
        make_unit(beverage, "keg_50l")

    # 64 crates from the unpacked pallet are above the reserve, the 2 kegs are below
    response = client.get("/inventory", params={"reserve": 10})
    assert response.status_code == 200
    assert response.json() == [{"beverage_id": beverage, "beverage_name": "Jenkins Cola", "container_type": "keg_50l", "count": 2}]

    response = client.get("/inventory", params={"reserve": 100})
    assert response.status_code == 200
    counts = {item["container_type"]: item["count"] for item in response.json()}
    assert counts == {"keg_50l": 2, "crate_20x05l": len(unpacked_pallet)}


def test_inventory_beverages_counted_separately(client: TestClient, beverage: int, make_unit: Callable[..., dict]):
    response = client.post("/beverages", json={"name": "Jenkins Pils", "type": "beer"})
    assert response.status_code == 201
    other_beverage = response.json()["id"]

    for _ in range(1):
        make_unit(beverage, "keg_50l")
    for _ in range(3):
        make_unit(other_beverage, "keg_50l")

    response = client.get("/inventory", params={"reserve": 2})
    assert response.status_code == 200
    assert response.json() == [{"beverage_id": beverage, "beverage_name": "Jenkins Cola", "container_type": "keg_50l", "count": 1}]


def test_inventory_counts_only_full_units(client: TestClient, beverage: int, make_unit: Callable[..., dict]):
    unit_ids = [make_unit(beverage, "keg_30l")["id"] for _ in range(3)]

    for unit_id, status in zip(unit_ids[:2], ["empty", "cleaned"]):
        response = client.patch(f"/packaging-units/{unit_id}", json={"status": status})
        assert response.status_code == 200

    response = client.get("/inventory", params={"reserve": 3})
    assert response.status_code == 200
    assert response.json() == [{"beverage_id": beverage, "beverage_name": "Jenkins Cola", "container_type": "keg_30l", "count": 1}]


# Only full stock is reported. Combinations without any full units are left out on
# purpose: whether empty or cleaned containers mean a restocking need (or are just
# leftovers of legacy stock) is for the client to decide.
def test_inventory_no_full_units_not_reported(client: TestClient, beverage: int, make_unit: Callable[..., dict]):
    unit = make_unit(beverage, "keg_50l")

    response = client.patch(f"/packaging-units/{unit['id']}", json={"status": "empty"})
    assert response.status_code == 200

    response = client.get("/inventory", params={"reserve": 5})
    assert response.status_code == 200
    assert response.json() == []
