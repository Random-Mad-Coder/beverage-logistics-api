import pytest
from datetime import datetime
from dateutil.relativedelta import relativedelta

from sqlmodel import SQLModel, Session, create_engine
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from main import app
from database import get_session, enable_foreign_keys
from constants import DATE_FORMAT_STRING

@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    enable_foreign_keys(engine)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture(name="client")
def client_fixture(session: Session):
    def get_session_override():
        return session

    app.dependency_overrides[get_session] = get_session_override
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


@pytest.fixture(name="beverage")
def beverage_fixture(client: TestClient):
    response = client.post("/beverages", json={"name": "Jenkins Cola", "type": "soft_drink"})
    assert response.status_code == 201
    return response.json()["id"]


@pytest.fixture(name="goods_receipt")
def goods_receipt_fixture(client: TestClient):
    date = datetime.today().strftime(DATE_FORMAT_STRING)
    response = client.post("/goods-receipts", json={"receipt_date": f"{date}", "supplier": "Doberman Beverages Inc."})
    assert response.status_code == 201
    return response.json()["id"]


@pytest.fixture(name="pallet")
def pallet_fixture(client: TestClient, beverage: int, goods_receipt: int):
    bbdate = datetime.today() + relativedelta(years=1)
    response = client.post("/pallets", json={"container_type": "crate_20x05l", "beverage_id": f"{beverage}", "goods_receipt_id": f"{goods_receipt}", "quantity": "64", "best_before_date": f"{bbdate.strftime(DATE_FORMAT_STRING)}"})
    assert response.status_code == 201
    return response.json()["id"]


@pytest.fixture(name="unpacked_pallet")
def unpacked_pallet_fixture(client: TestClient, pallet: int):
    response = client.post(f"/pallets/{pallet}/unpack")
    assert response.status_code == 200
    return [item["id"] for item in response.json()]


@pytest.fixture(name="delivery")
def delivery_fixture(client: TestClient, unpacked_pallet: list[int]):
    date = datetime.today()
    response = client.post("/deliveries", json={"delivery_date": f"{date.strftime(DATE_FORMAT_STRING)}", "customer": "Thirsty People Ltd.", "unit_ids": unpacked_pallet})
    assert response.status_code == 201
    return response.json()


@pytest.fixture(name="make_unit")
def make_unit_fixture(client: TestClient):
    def make_unit(beverage_id: int, container_type: str = "keg_50l") -> dict:
        bbdate = datetime.today() + relativedelta(years=1)
        response = client.post("/packaging-units", json={"container_type": container_type, "beverage_id": beverage_id, "best_before_date": bbdate.strftime(DATE_FORMAT_STRING)})
        assert response.status_code == 201
        return response.json()
    return make_unit


@pytest.fixture(name="make_pallet")
def make_pallet_fixture(client: TestClient):
    def make_pallet(beverage_id: int, goods_receipt_id: int, container_type: str = "keg_50l", best_before_date: datetime | None = None) -> dict:
        bbdate = best_before_date or datetime.today() + relativedelta(years=1)
        response = client.post("/pallets", json={"container_type": container_type, "beverage_id": beverage_id, "goods_receipt_id": goods_receipt_id, "quantity": 8, "best_before_date": bbdate.strftime(DATE_FORMAT_STRING)})
        assert response.status_code == 201
        return response.json()
    return make_pallet


@pytest.fixture(name="make_delivery")
def make_delivery_fixture(client: TestClient):
    def make_delivery(unit_ids: list[int], customer: str = "Café Jenkins") -> dict:
        date = datetime.today().strftime(DATE_FORMAT_STRING)
        response = client.post("/deliveries", json={"delivery_date": date, "customer": customer, "unit_ids": unit_ids})
        assert response.status_code == 201
        return response.json()
    return make_delivery