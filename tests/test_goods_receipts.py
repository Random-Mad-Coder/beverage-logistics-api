from fastapi.testclient import TestClient
from datetime import datetime
from dateutil.relativedelta import relativedelta
from constants import DATE_FORMAT_STRING


def create_pallet(client: TestClient, beverage_id: int, goods_receipt_id: int) -> int:
    bbdate = datetime.today() + relativedelta(years=1)
    response = client.post("/pallets", json={"container_type": "keg_50l", "beverage_id": beverage_id, "goods_receipt_id": goods_receipt_id, "quantity": 8, "best_before_date": bbdate.strftime(DATE_FORMAT_STRING)})
    assert response.status_code == 201
    return response.json()["id"]


def test_create_goods_receipt_success(client: TestClient):
    date = datetime.today().strftime(DATE_FORMAT_STRING)
    response = client.post("/goods-receipts", json={"date": date, "supplier": "Doberman Beverages Inc.", "expected_pallet_count": 3})
    assert response.status_code == 201

    data = response.json()
    assert "id" in data
    assert data["date"] == date
    assert data["supplier"] == "Doberman Beverages Inc."
    assert data["expected_pallet_count"] == 3
    assert data["actual_pallet_count"] == 0


def test_create_goods_receipt_without_expected_pallet_count(client: TestClient):
    date = datetime.today().strftime(DATE_FORMAT_STRING)
    response = client.post("/goods-receipts", json={"date": date, "supplier": "Doberman Beverages Inc."})
    assert response.status_code == 201
    assert response.json()["expected_pallet_count"] is None


def test_create_goods_receipt_missing_supplier_422(client: TestClient):
    date = datetime.today().strftime(DATE_FORMAT_STRING)
    response = client.post("/goods-receipts", json={"date": date})
    assert response.status_code == 422


def test_get_goods_receipt_success(client: TestClient, goods_receipt: int):
    response = client.get(f"/goods-receipts/{goods_receipt}")
    assert response.status_code == 200

    data = response.json()
    assert data["id"] == goods_receipt
    assert data["supplier"] == "Doberman Beverages Inc."
    assert data["actual_pallet_count"] == 0


def test_get_goods_receipt_actual_pallet_count(client: TestClient, beverage: int, goods_receipt: int, pallet: int):
    create_pallet(client, beverage, goods_receipt)

    response = client.get(f"/goods-receipts/{goods_receipt}")
    assert response.status_code == 200
    assert response.json()["actual_pallet_count"] == 2


def test_get_goods_receipt_not_found_404(client: TestClient):
    response = client.get("/goods-receipts/1")
    assert response.status_code == 404


def test_list_goods_receipts_empty(client: TestClient):
    response = client.get("/goods-receipts")
    assert response.status_code == 200
    assert response.json() == []


def test_list_goods_receipts_actual_pallet_count(client: TestClient, goods_receipt: int, pallet: int):
    date = datetime.today().strftime(DATE_FORMAT_STRING)
    response = client.post("/goods-receipts", json={"date": date, "supplier": "Doberman Beverages Inc."})
    assert response.status_code == 201
    empty_receipt = response.json()["id"]

    response = client.get("/goods-receipts")
    assert response.status_code == 200
    counts = {item["id"]: item["actual_pallet_count"] for item in response.json()}
    assert counts == {goods_receipt: 1, empty_receipt: 0}


def test_list_goods_receipts_filter_date(client: TestClient, goods_receipt: int):
    yesterday = (datetime.today() - relativedelta(days=1)).strftime(DATE_FORMAT_STRING)
    response = client.post("/goods-receipts", json={"date": yesterday, "supplier": "Doberman Beverages Inc."})
    assert response.status_code == 201
    old_receipt = response.json()["id"]

    response = client.get("/goods-receipts", params={"date": yesterday})
    assert response.status_code == 200
    assert [item["id"] for item in response.json()] == [old_receipt]


def test_list_goods_receipts_filter_supplier(client: TestClient, goods_receipt: int):
    date = datetime.today().strftime(DATE_FORMAT_STRING)
    response = client.post("/goods-receipts", json={"date": date, "supplier": "Jenkins Brewery"})
    assert response.status_code == 201

    response = client.get("/goods-receipts", params={"supplier": "Doberman Beverages Inc."})
    assert response.status_code == 200
    assert [item["id"] for item in response.json()] == [goods_receipt]


def test_update_goods_receipt_partial(client: TestClient, goods_receipt: int):
    response = client.get(f"/goods-receipts/{goods_receipt}")
    assert response.status_code == 200
    original = response.json()

    response = client.patch(f"/goods-receipts/{goods_receipt}", json={"supplier": "Jenkins Brewery", "expected_pallet_count": 5})
    assert response.status_code == 200

    data = response.json()
    assert data["supplier"] == "Jenkins Brewery"
    assert data["expected_pallet_count"] == 5
    assert data["date"] == original["date"]

    response = client.get(f"/goods-receipts/{goods_receipt}")
    assert response.status_code == 200
    assert response.json() == data


def test_update_goods_receipt_reset_expected_pallet_count(client: TestClient, goods_receipt: int):
    response = client.patch(f"/goods-receipts/{goods_receipt}", json={"expected_pallet_count": 5})
    assert response.status_code == 200
    assert response.json()["expected_pallet_count"] == 5

    response = client.patch(f"/goods-receipts/{goods_receipt}", json={"expected_pallet_count": None})
    assert response.status_code == 200
    assert response.json()["expected_pallet_count"] is None

    response = client.get(f"/goods-receipts/{goods_receipt}")
    assert response.status_code == 200
    assert response.json()["expected_pallet_count"] is None


def test_update_goods_receipt_null_required_field_ignored(client: TestClient, goods_receipt: int):
    response = client.patch(f"/goods-receipts/{goods_receipt}", json={"supplier": None})
    assert response.status_code == 200
    assert response.json()["supplier"] == "Doberman Beverages Inc."


def test_update_goods_receipt_actual_pallet_count(client: TestClient, goods_receipt: int, pallet: int):
    response = client.patch(f"/goods-receipts/{goods_receipt}", json={"supplier": "Jenkins Brewery"})
    assert response.status_code == 200
    assert response.json()["actual_pallet_count"] == 1


def test_update_goods_receipt_not_found_404(client: TestClient):
    response = client.patch("/goods-receipts/1", json={"supplier": "Jenkins Brewery"})
    assert response.status_code == 404


def test_delete_goods_receipt_success(client: TestClient, goods_receipt: int):
    response = client.delete(f"/goods-receipts/{goods_receipt}")
    assert response.status_code == 204

    response = client.get(f"/goods-receipts/{goods_receipt}")
    assert response.status_code == 404


def test_delete_goods_receipt_not_found_404(client: TestClient):
    response = client.delete("/goods-receipts/1")
    assert response.status_code == 404


def test_delete_goods_receipt_with_pallets_409(client: TestClient, goods_receipt: int, pallet: int):
    response = client.delete(f"/goods-receipts/{goods_receipt}")
    assert response.status_code == 409
    assert isinstance(response.json()["detail"], str)

    response = client.get(f"/goods-receipts/{goods_receipt}")
    assert response.status_code == 200
    assert response.json()["actual_pallet_count"] == 1
