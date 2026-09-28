from fastapi.testclient import TestClient
from datetime import datetime
from dateutil.relativedelta import relativedelta
from constants import DATE_FORMAT_STRING


def create_pallet(client: TestClient, beverage_id: int, goods_receipt_id: int, container_type: str = "keg_50l", best_before_date: datetime | None = None) -> dict:
    bbdate = best_before_date or datetime.today() + relativedelta(years=1)
    response = client.post("/pallets", json={"container_type": container_type, "beverage_id": beverage_id, "goods_receipt_id": goods_receipt_id, "quantity": 8, "best_before_date": bbdate.strftime(DATE_FORMAT_STRING)})
    assert response.status_code == 201
    return response.json()


def test_unpack_pallet_noop(client: TestClient, pallet: int):
    response = client.post(f"/pallets/{pallet}/unpack")
    assert response.status_code == 200

    response = client.post(f"/pallets/{pallet}/unpack")
    assert response.status_code == 409


def test_unpack_pallet_unpack_after_change(client: TestClient, pallet: int):
    response = client.post(f"/pallets/{pallet}/unpack")
    assert response.status_code == 200

    response = client.get(f"/pallets/{pallet}")
    assert response.status_code == 200
    data = response.json()
    qty = data["quantity"]
    old_bbdate = datetime.strptime(data["best_before_date"], DATE_FORMAT_STRING)

    new_bbdate = old_bbdate + relativedelta(years=1)
    response = client.patch(f"/pallets/{pallet}", json={"best_before_date": new_bbdate.strftime(DATE_FORMAT_STRING)})
    assert response.status_code == 200

    response = client.post(f"/pallets/{pallet}/unpack")
    assert response.status_code == 200
    data = response.json()
    for item in data:
        assert item["best_before_date"] == new_bbdate.strftime(DATE_FORMAT_STRING)

    response = client.get("/packaging-units")
    assert response.status_code == 200    
    assert len(response.json()) == qty


def test_unpack_pallet_conflict(client: TestClient, pallet: int, unpacked_pallet: list[int], delivery: dict):
    # Change the pallet first, otherwise the unchanged-data 409 is hit before the delivery check
    new_bbdate = datetime.today() + relativedelta(years=2)
    response = client.patch(f"/pallets/{pallet}", json={"best_before_date": new_bbdate.strftime(DATE_FORMAT_STRING)})
    assert response.status_code == 200

    response = client.post(f"/pallets/{pallet}/unpack")
    assert response.status_code == 409
    conflict_ids = response.json()["detail"]["unit_ids"]
    assert conflict_ids == sorted(unpacked_pallet)


def test_unpack_pallet_success(client: TestClient, pallet: int):
    response = client.get(f"/pallets/{pallet}")
    assert response.status_code == 200
    pallet_data = response.json()

    response = client.post(f"/pallets/{pallet}/unpack")
    assert response.status_code == 200

    data = response.json()
    assert len(data) == pallet_data["quantity"]
    for item in data:
        assert item["container_type"] == pallet_data["container_type"]
        assert item["beverage_id"] == pallet_data["beverage_id"]
        assert item["best_before_date"] == pallet_data["best_before_date"]
        assert item["received_via_pallet_id"] == pallet
        assert item["status"] == "full"


def test_unpack_pallet_not_found_404(client: TestClient):
    response = client.post("/pallets/1/unpack")
    assert response.status_code == 404


def test_create_pallet_success(client: TestClient, beverage: int, goods_receipt: int):
    bbdate = datetime.today() + relativedelta(years=1)
    response = client.post("/pallets", json={"container_type": "keg_30l", "beverage_id": beverage, "goods_receipt_id": goods_receipt, "quantity": 12, "best_before_date": bbdate.strftime(DATE_FORMAT_STRING)})
    assert response.status_code == 201

    data = response.json()
    assert "id" in data
    assert data["container_type"] == "keg_30l"
    assert data["beverage_id"] == beverage
    assert data["goods_receipt_id"] == goods_receipt
    assert data["quantity"] == 12
    assert data["best_before_date"] == bbdate.strftime(DATE_FORMAT_STRING)


def test_create_pallet_invalid_beverage_409(client: TestClient, goods_receipt: int):
    bbdate = datetime.today() + relativedelta(years=1)
    response = client.post("/pallets", json={"container_type": "keg_30l", "beverage_id": 999, "goods_receipt_id": goods_receipt, "quantity": 12, "best_before_date": bbdate.strftime(DATE_FORMAT_STRING)})
    assert response.status_code == 409
    assert isinstance(response.json()["detail"], str)

    response = client.get("/pallets")
    assert response.status_code == 200
    assert response.json() == []


def test_create_pallet_invalid_goods_receipt_409(client: TestClient, beverage: int):
    bbdate = datetime.today() + relativedelta(years=1)
    response = client.post("/pallets", json={"container_type": "keg_30l", "beverage_id": beverage, "goods_receipt_id": 999, "quantity": 12, "best_before_date": bbdate.strftime(DATE_FORMAT_STRING)})
    assert response.status_code == 409
    assert isinstance(response.json()["detail"], str)

    response = client.get("/pallets")
    assert response.status_code == 200
    assert response.json() == []


def test_create_pallet_invalid_container_type_422(client: TestClient, beverage: int, goods_receipt: int):
    bbdate = datetime.today() + relativedelta(years=1)
    response = client.post("/pallets", json={"container_type": "barrel", "beverage_id": beverage, "goods_receipt_id": goods_receipt, "quantity": 12, "best_before_date": bbdate.strftime(DATE_FORMAT_STRING)})
    assert response.status_code == 422


def test_create_pallet_zero_quantity(client: TestClient, beverage: int, goods_receipt: int):
    bbdate = datetime.today() + relativedelta(years=1)
    response = client.post("/pallets", json={"container_type": "keg_30l", "beverage_id": beverage, "goods_receipt_id": goods_receipt, "quantity": 0, "best_before_date": bbdate.strftime(DATE_FORMAT_STRING)})
    assert response.status_code == 201
    assert response.json()["quantity"] == 0


def test_create_pallet_negative_quantity_422(client: TestClient, beverage: int, goods_receipt: int):
    bbdate = datetime.today() + relativedelta(years=1)
    response = client.post("/pallets", json={"container_type": "keg_30l", "beverage_id": beverage, "goods_receipt_id": goods_receipt, "quantity": -1, "best_before_date": bbdate.strftime(DATE_FORMAT_STRING)})
    assert response.status_code == 422


def test_get_pallet_success(client: TestClient, beverage: int, goods_receipt: int):
    created = create_pallet(client, beverage, goods_receipt)

    response = client.get(f"/pallets/{created['id']}")
    assert response.status_code == 200
    assert response.json() == created


def test_get_pallet_not_found_404(client: TestClient):
    response = client.get("/pallets/1")
    assert response.status_code == 404


def test_list_pallets_empty(client: TestClient):
    response = client.get("/pallets")
    assert response.status_code == 200
    assert response.json() == []


def test_list_pallets_filter_best_before(client: TestClient, beverage: int, goods_receipt: int, pallet: int):
    bbdate = datetime.today() + relativedelta(years=2)
    created = create_pallet(client, beverage, goods_receipt, best_before_date=bbdate)

    response = client.get("/pallets", params={"best_before": bbdate.strftime(DATE_FORMAT_STRING)})
    assert response.status_code == 200
    assert [item["id"] for item in response.json()] == [created["id"]]


def test_list_pallets_filter_beverage_id(client: TestClient, goods_receipt: int, pallet: int):
    response = client.post("/beverages", json={"name": "Jenkins Pils", "type": "beer"})
    assert response.status_code == 201
    other_beverage = response.json()["id"]
    created = create_pallet(client, other_beverage, goods_receipt)

    response = client.get("/pallets", params={"beverage_id": other_beverage})
    assert response.status_code == 200
    assert [item["id"] for item in response.json()] == [created["id"]]


def test_list_pallets_filter_container_type(client: TestClient, beverage: int, goods_receipt: int, pallet: int):
    created = create_pallet(client, beverage, goods_receipt, container_type="keg_20l")

    response = client.get("/pallets", params={"container_type": "keg_20l"})
    assert response.status_code == 200
    assert [item["id"] for item in response.json()] == [created["id"]]


def test_list_pallets_filter_goods_receipt_id(client: TestClient, beverage: int, pallet: int):
    date = datetime.today().strftime(DATE_FORMAT_STRING)
    response = client.post("/goods-receipts", json={"receipt_date": date, "supplier": "Jenkins Brewery"})
    assert response.status_code == 201
    other_receipt = response.json()["id"]
    created = create_pallet(client, beverage, other_receipt)

    response = client.get("/pallets", params={"goods_receipt_id": other_receipt})
    assert response.status_code == 200
    assert [item["id"] for item in response.json()] == [created["id"]]


def test_update_pallet_partial(client: TestClient, pallet: int):
    response = client.get(f"/pallets/{pallet}")
    assert response.status_code == 200
    original = response.json()

    response = client.patch(f"/pallets/{pallet}", json={"quantity": 32, "container_type": "crate_24x033l"})
    assert response.status_code == 200

    data = response.json()
    assert data["quantity"] == 32
    assert data["container_type"] == "crate_24x033l"
    assert data["beverage_id"] == original["beverage_id"]
    assert data["goods_receipt_id"] == original["goods_receipt_id"]
    assert data["best_before_date"] == original["best_before_date"]

    response = client.get(f"/pallets/{pallet}")
    assert response.status_code == 200
    assert response.json() == data


def test_update_pallet_invalid_beverage_409(client: TestClient, beverage: int, pallet: int):
    response = client.patch(f"/pallets/{pallet}", json={"beverage_id": 999})
    assert response.status_code == 409
    assert isinstance(response.json()["detail"], str)

    response = client.get(f"/pallets/{pallet}")
    assert response.status_code == 200
    assert response.json()["beverage_id"] == beverage


def test_update_pallet_negative_quantity_422(client: TestClient, pallet: int):
    response = client.patch(f"/pallets/{pallet}", json={"quantity": -1})
    assert response.status_code == 422

    response = client.get(f"/pallets/{pallet}")
    assert response.status_code == 200
    assert response.json()["quantity"] == 64


def test_update_pallet_not_found_404(client: TestClient):
    response = client.patch("/pallets/1", json={"quantity": 32})
    assert response.status_code == 404


def test_delete_pallet_success(client: TestClient, pallet: int):
    response = client.delete(f"/pallets/{pallet}")
    assert response.status_code == 204

    response = client.get(f"/pallets/{pallet}")
    assert response.status_code == 404


def test_delete_pallet_not_found_404(client: TestClient):
    response = client.delete("/pallets/1")
    assert response.status_code == 404


def test_delete_pallet_unpacked_409(client: TestClient, pallet: int, unpacked_pallet: list[int]):
    response = client.delete(f"/pallets/{pallet}")
    assert response.status_code == 409
    assert isinstance(response.json()["detail"], str)

    response = client.get(f"/pallets/{pallet}")
    assert response.status_code == 200