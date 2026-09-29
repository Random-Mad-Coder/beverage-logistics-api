from typing import Callable
from fastapi.testclient import TestClient
from datetime import datetime
from dateutil.relativedelta import relativedelta
from constants import DATE_FORMAT_STRING

# Known gap: the reactive `except IntegrityError` paths in create_delivery,
# update_delivery_payload and delete_delivery only trigger when a packaging unit is
# deleted concurrently between the upfront existence check and the commit. That race
# cannot be reproduced deterministically via the API, so these paths are not tested.


def test_create_delivery_success(client: TestClient, unpacked_pallet: list[int]):
    date = datetime.today().strftime(DATE_FORMAT_STRING)
    unit_ids = unpacked_pallet[:3]
    response = client.post("/deliveries", json={"delivery_date": date, "customer": "Café Jenkins", "unit_ids": unit_ids})
    assert response.status_code == 201

    data = response.json()
    assert "id" in data
    assert data["delivery_date"] == date
    assert data["customer"] == "Café Jenkins"
    assert data["unit_ids"] == unit_ids


def test_create_delivery_without_units(client: TestClient):
    date = datetime.today().strftime(DATE_FORMAT_STRING)
    response = client.post("/deliveries", json={"delivery_date": date, "customer": "Café Jenkins"})
    assert response.status_code == 201
    assert response.json()["unit_ids"] == []


def test_create_delivery_duplicate_unit_ids(client: TestClient, unpacked_pallet: list[int]):
    date = datetime.today().strftime(DATE_FORMAT_STRING)
    response = client.post("/deliveries", json={"delivery_date": date, "customer": "Café Jenkins", "unit_ids": [unpacked_pallet[1], unpacked_pallet[0], unpacked_pallet[1]]})
    assert response.status_code == 201
    assert response.json()["unit_ids"] == [unpacked_pallet[1], unpacked_pallet[0]]

    response = client.get(f"/deliveries/{response.json()['id']}")
    assert response.status_code == 200
    assert sorted(response.json()["unit_ids"]) == sorted(unpacked_pallet[:2])


# Deliveries are historic records and packaging units are reused (full -> empty ->
# cleaned -> full), so the same unit may appear in several deliveries.
def test_create_delivery_unit_in_multiple_deliveries(client: TestClient, unpacked_pallet: list[int], make_delivery: Callable[..., dict]):
    first = make_delivery(unpacked_pallet[:1])
    second = make_delivery(unpacked_pallet[:1])

    for delivery_id in (first["id"], second["id"]):
        response = client.get(f"/deliveries/{delivery_id}")
        assert response.status_code == 200
        assert response.json()["unit_ids"] == unpacked_pallet[:1]


def test_create_delivery_invalid_unit_ids_409(client: TestClient, unpacked_pallet: list[int]):
    date = datetime.today().strftime(DATE_FORMAT_STRING)
    response = client.post("/deliveries", json={"delivery_date": date, "customer": "Café Jenkins", "unit_ids": [unpacked_pallet[0], 1001, 1000]})
    assert response.status_code == 409

    detail = response.json()["detail"]
    assert isinstance(detail["message"], str)
    assert detail["unit_ids"] == [1000, 1001]

    response = client.get("/deliveries")
    assert response.status_code == 200
    assert response.json() == []


def test_create_delivery_missing_customer_422(client: TestClient):
    date = datetime.today().strftime(DATE_FORMAT_STRING)
    response = client.post("/deliveries", json={"delivery_date": date})
    assert response.status_code == 422


def test_get_delivery_success(client: TestClient, delivery: dict):
    response = client.get(f"/deliveries/{delivery['id']}")
    assert response.status_code == 200

    data = response.json()
    assert data["id"] == delivery["id"]
    assert data["delivery_date"] == delivery["delivery_date"]
    assert data["customer"] == delivery["customer"]
    assert sorted(data["unit_ids"]) == sorted(delivery["unit_ids"])


def test_get_delivery_not_found_404(client: TestClient):
    response = client.get("/deliveries/1")
    assert response.status_code == 404


def test_list_deliveries_empty(client: TestClient):
    response = client.get("/deliveries")
    assert response.status_code == 200
    assert response.json() == []


def test_list_deliveries_unit_ids_per_delivery(client: TestClient, unpacked_pallet: list[int], make_delivery: Callable[..., dict]):
    first = make_delivery(unpacked_pallet[:2])
    second = make_delivery(unpacked_pallet[2:5])
    empty = make_delivery([])

    response = client.get("/deliveries")
    assert response.status_code == 200
    unit_ids = {item["id"]: sorted(item["unit_ids"]) for item in response.json()}
    assert unit_ids == {
        first["id"]: sorted(unpacked_pallet[:2]),
        second["id"]: sorted(unpacked_pallet[2:5]),
        empty["id"]: [],
    }


def test_list_deliveries_filter_delivery_date(client: TestClient, make_delivery: Callable[..., dict]):
    make_delivery([])
    yesterday = (datetime.today() - relativedelta(days=1)).strftime(DATE_FORMAT_STRING)
    response = client.post("/deliveries", json={"delivery_date": yesterday, "customer": "Café Jenkins"})
    assert response.status_code == 201
    old_delivery = response.json()["id"]

    response = client.get("/deliveries", params={"delivery_date": yesterday})
    assert response.status_code == 200
    assert [item["id"] for item in response.json()] == [old_delivery]


def test_list_deliveries_filter_customer(client: TestClient, make_delivery: Callable[..., dict]):
    make_delivery([], customer="Thirsty People Ltd.")
    created = make_delivery([], customer="Café Jenkins")

    response = client.get("/deliveries", params={"customer": "Café Jenkins"})
    assert response.status_code == 200
    assert [item["id"] for item in response.json()] == [created["id"]]


def test_update_delivery_metadata(client: TestClient, delivery: dict):
    new_date = (datetime.today() + relativedelta(days=3)).strftime(DATE_FORMAT_STRING)
    response = client.patch(f"/deliveries/{delivery['id']}/metadata", json={"delivery_date": new_date, "customer": "Café Jenkins"})
    assert response.status_code == 200

    data = response.json()
    assert data["delivery_date"] == new_date
    assert data["customer"] == "Café Jenkins"
    assert sorted(data["unit_ids"]) == sorted(delivery["unit_ids"])

    response = client.get(f"/deliveries/{delivery['id']}")
    assert response.status_code == 200
    assert response.json()["delivery_date"] == new_date
    assert response.json()["customer"] == "Café Jenkins"


def test_update_delivery_metadata_partial(client: TestClient, delivery: dict):
    response = client.patch(f"/deliveries/{delivery['id']}/metadata", json={"customer": "Café Jenkins"})
    assert response.status_code == 200
    assert response.json()["customer"] == "Café Jenkins"
    assert response.json()["delivery_date"] == delivery["delivery_date"]


def test_update_delivery_metadata_blank_customer_ignored(client: TestClient, delivery: dict):
    response = client.patch(f"/deliveries/{delivery['id']}/metadata", json={"customer": "   "})
    assert response.status_code == 200
    assert response.json()["customer"] == delivery["customer"]


def test_update_delivery_metadata_not_found_404(client: TestClient):
    response = client.patch("/deliveries/1/metadata", json={"customer": "Café Jenkins"})
    assert response.status_code == 404


def test_update_delivery_payload_add(client: TestClient, unpacked_pallet: list[int], make_delivery: Callable[..., dict]):
    created = make_delivery(unpacked_pallet[:2])

    response = client.patch(f"/deliveries/{created['id']}/payload", json={"unit_ids": unpacked_pallet[:4]})
    assert response.status_code == 200
    assert sorted(response.json()["unit_ids"]) == sorted(unpacked_pallet[:4])

    response = client.get(f"/deliveries/{created['id']}")
    assert response.status_code == 200
    assert sorted(response.json()["unit_ids"]) == sorted(unpacked_pallet[:4])


def test_update_delivery_payload_remove(client: TestClient, unpacked_pallet: list[int], make_delivery: Callable[..., dict]):
    created = make_delivery(unpacked_pallet[:4])

    response = client.patch(f"/deliveries/{created['id']}/payload", json={"unit_ids": unpacked_pallet[:1]})
    assert response.status_code == 200
    assert response.json()["unit_ids"] == unpacked_pallet[:1]

    response = client.get(f"/deliveries/{created['id']}")
    assert response.status_code == 200
    assert response.json()["unit_ids"] == unpacked_pallet[:1]

    # Removed units are released: they can be deleted again
    response = client.delete(f"/packaging-units/{unpacked_pallet[3]}")
    assert response.status_code == 204


def test_update_delivery_payload_add_and_remove(client: TestClient, unpacked_pallet: list[int], make_delivery: Callable[..., dict]):
    created = make_delivery(unpacked_pallet[:3])
    new_unit_ids = unpacked_pallet[1:3] + unpacked_pallet[5:7]

    response = client.patch(f"/deliveries/{created['id']}/payload", json={"unit_ids": new_unit_ids})
    assert response.status_code == 200
    assert sorted(response.json()["unit_ids"]) == sorted(new_unit_ids)

    response = client.get(f"/deliveries/{created['id']}")
    assert response.status_code == 200
    assert sorted(response.json()["unit_ids"]) == sorted(new_unit_ids)


def test_update_delivery_payload_duplicate_unit_ids(client: TestClient, unpacked_pallet: list[int], make_delivery: Callable[..., dict]):
    created = make_delivery(unpacked_pallet[:1])

    response = client.patch(f"/deliveries/{created['id']}/payload", json={"unit_ids": [unpacked_pallet[0], unpacked_pallet[1], unpacked_pallet[1]]})
    assert response.status_code == 200
    assert response.json()["unit_ids"] == unpacked_pallet[:2]

    response = client.get(f"/deliveries/{created['id']}")
    assert response.status_code == 200
    assert sorted(response.json()["unit_ids"]) == sorted(unpacked_pallet[:2])


def test_update_delivery_payload_clear(client: TestClient, delivery: dict):
    response = client.patch(f"/deliveries/{delivery['id']}/payload", json={"unit_ids": []})
    assert response.status_code == 200
    assert response.json()["unit_ids"] == []

    response = client.get(f"/deliveries/{delivery['id']}")
    assert response.status_code == 200
    assert response.json()["unit_ids"] == []


def test_update_delivery_payload_invalid_unit_ids_409(client: TestClient, unpacked_pallet: list[int], make_delivery: Callable[..., dict]):
    created = make_delivery(unpacked_pallet[:3])

    response = client.patch(f"/deliveries/{created['id']}/payload", json={"unit_ids": unpacked_pallet[1:4] + [1001, 1000]})
    assert response.status_code == 409

    detail = response.json()["detail"]
    assert isinstance(detail["message"], str)
    assert detail["unit_ids"] == [1000, 1001]

    # Neither the valid additions nor the removals were applied
    response = client.get(f"/deliveries/{created['id']}")
    assert response.status_code == 200
    assert sorted(response.json()["unit_ids"]) == sorted(unpacked_pallet[:3])


def test_update_delivery_payload_not_found_404(client: TestClient):
    response = client.patch("/deliveries/1/payload", json={"unit_ids": []})
    assert response.status_code == 404


def test_delete_delivery_success(client: TestClient, delivery: dict):
    response = client.delete(f"/deliveries/{delivery['id']}")
    assert response.status_code == 204

    response = client.get(f"/deliveries/{delivery['id']}")
    assert response.status_code == 404


def test_delete_delivery_cascades_items(client: TestClient, unpacked_pallet: list[int], delivery: dict):
    response = client.delete(f"/deliveries/{delivery['id']}")
    assert response.status_code == 204

    # The packaging units themselves survive the delivery
    response = client.get(f"/packaging-units/{unpacked_pallet[0]}")
    assert response.status_code == 200

    # The delivery items are gone, so the units are no longer blocked from deletion
    response = client.delete(f"/packaging-units/{unpacked_pallet[0]}")
    assert response.status_code == 204


def test_delete_delivery_not_found_404(client: TestClient):
    response = client.delete("/deliveries/1")
    assert response.status_code == 404
