from fastapi.testclient import TestClient
from datetime import datetime
from dateutil.relativedelta import relativedelta
from constants import DATE_FORMAT_STRING

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