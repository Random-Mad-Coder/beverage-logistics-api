from contextlib import asynccontextmanager
from datetime import date
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from database import create_db_and_tables, get_session
from models import (
    BeverageType,
    ContainerType,
    Status,
    Beverage,
    BeverageCreate,
    BeverageRead,
    Delivery,
    DeliveryCreate,
    DeliveryRead,
    DeliveryMetaDataUpdate,
    DeliveryPayloadUpdate,
    InventoryReport,
    Keg,
    KegCreate,
    KegRead,
    KegStatusUpdate,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables here in case they don't exist yet.
    create_db_and_tables()
    yield


app = FastAPI(title="Beverage Logistics API", lifespan=lifespan)

# ---------- Inventory ----------

@app.get("/inventory", response_model=list[InventoryReport])
def get_inventory(reserve: int, session: Session = Depends(get_session)):
    query = (
        select(Beverage.id, Beverage.name, func.count())
        .join(Beverage, Keg.beverage_id == Beverage.id)
        .where(Keg.status == Status.FULL)
        .group_by(Beverage.id, Beverage.name)
        .having(func.count() < reserve)
    )
    result = session.exec(query).all()

    return [InventoryReport(beverage_id=beverage_id, beverage_name=beverage_name, container_type=ContainerType.KEG, count=count) for (beverage_id, beverage_name, count) in result]


# ---------- Beverage ----------

@app.get("/beverages", response_model=list[BeverageRead])
def list_beverages(
    name: Optional[str] = Query(default=None),
    beverage_type: Optional[BeverageType] = Query(default=None),
    session: Session = Depends(get_session),
):
    query = select(Beverage)
    if name:
        query = query.where(Beverage.name == name)
    if beverage_type:
        query = query.where(Beverage.type == beverage_type)

    return session.exec(query).all()


@app.post("/beverages", response_model=BeverageRead, status_code=201)
def create_beverage(beverage: BeverageCreate, session: Session = Depends(get_session)):
    db_beverage = Beverage.model_validate(beverage)
    session.add(db_beverage)

    try:
        session.commit()
    except IntegrityError: 
        raise HTTPException(status_code=409, detail=f"Beverage with name {db_beverage.name} already exists")

    session.refresh(db_beverage)
    return db_beverage


@app.get("/beverages/{beverage_id}", response_model=BeverageRead)
def get_beverage(beverage_id: int, session: Session = Depends(get_session)):
    beverage = session.get(Beverage, beverage_id)
    if not beverage:
        raise HTTPException(status_code=404, detail=f"Beverage with id {beverage_id} not found")
    return beverage

# ---------- Kegs ----------

@app.get("/kegs", response_model=list[KegRead])
def list_kegs(
    beverage_name: Optional[str] = Query(default=None),
    status: Optional[Status] = Query(default=None),
    session: Session = Depends(get_session),
):
    query = select(Keg)
    if beverage_name:
        query = query.join(Beverage, Keg.beverage_id == Beverage.id).where(Beverage.name == beverage_name)
    if status:
        query = query.where(Keg.status == status)

    return session.exec(query).all()


@app.post("/kegs", response_model=KegRead, status_code=201)
def create_keg(keg: KegCreate, session: Session = Depends(get_session)):
    db_keg = Keg.model_validate(keg)
    session.add(db_keg)
    session.commit()
    session.refresh(db_keg)
    return db_keg


@app.get("/kegs/{keg_id}", response_model=KegRead)
def get_keg(keg_id: int, session: Session = Depends(get_session)):
    keg = session.get(Keg, keg_id)
    if not keg:
        raise HTTPException(status_code=404, detail=f"Keg with id {keg_id} not found")
    return keg


@app.patch("/kegs/{keg_id}/status", response_model=KegRead)
def update_keg_status(
    keg_id: int, update: KegStatusUpdate, session: Session = Depends(get_session)
):
    keg = session.get(Keg, keg_id)
    if not keg:
        raise HTTPException(status_code=404, detail=f"Keg with id {keg_id} not found")
    keg.status = update.status
    session.add(keg)
    session.commit()
    session.refresh(keg)
    return keg


@app.delete("/kegs/{keg_id}", status_code=204)
def delete_keg(keg_id: int, session: Session = Depends(get_session)):
    keg = session.get(Keg, keg_id)
    if not keg:
        raise HTTPException(status_code=404, detail=f"Keg with id {keg_id} not found")
    session.delete(keg)
    session.commit()


# ---------- Deliveries ----------

@app.get("/deliveries", response_model=list[DeliveryRead])
def list_deliveries(
    date: Optional[date] = Query(default=None),
    customer: Optional[str] = Query(default=None),
    session: Session = Depends(get_session)
):
    query = select(Delivery)
    if date:
        query = query.where(Delivery.date == date)
    if customer:
        query = query.where(Delivery.customer == customer)

    deliveries = session.exec(query).all()

    return [DeliveryRead(id=d.id, date=d.date, customer=d.customer, keg_ids=d.get_keg_ids()) for d in deliveries]


@app.post("/deliveries", response_model=DeliveryRead, status_code=201)
def create_delivery(
    delivery: DeliveryCreate, session: Session = Depends(get_session)
):
    db_delivery = Delivery(date=delivery.date, customer=delivery.customer)
    db_delivery.set_keg_ids(delivery.keg_ids)
    session.add(db_delivery)
    session.commit()
    session.refresh(db_delivery)
    return DeliveryRead(
        id=db_delivery.id,
        date=db_delivery.date,
        customer=db_delivery.customer,
        keg_ids=db_delivery.get_keg_ids(),
    )


@app.get("/deliveries/{delivery_id}", response_model=DeliveryRead)
def get_delivery(delivery_id: int, session: Session = Depends(get_session)):
    delivery = session.get(Delivery, delivery_id)
    if not delivery:
        raise HTTPException(status_code=404, detail=f"Delivery with id {delivery_id} not found")
    return DeliveryRead(
        id=delivery.id,
        date=delivery.date,
        customer=delivery.customer,
        keg_ids=delivery.get_keg_ids(),
    )


@app.delete("/deliveries/{delivery_id}", status_code=204)
def delete_delivery(delivery_id: int, session: Session = Depends(get_session)):
    delivery = session.get(Delivery, delivery_id)
    if not delivery:
        raise HTTPException(status_code=404, detail=f"Delivery with id {delivery_id} not found")
    session.delete(delivery)
    session.commit()


@app.patch("/deliveries/{delivery_id}/metadata", response_model=DeliveryRead)
def update_delivery_metadata(
    delivery_id: int, update: DeliveryMetaDataUpdate, session: Session = Depends(get_session)
):
    delivery = session.get(Delivery, delivery_id)
    if not delivery:
        raise HTTPException(status_code=404, detail=f"Delivery with id {delivery_id} not found")

    if update.date:
        delivery.date = update.date

    if update.customer and update.customer.strip():
        delivery.customer = update.customer

    session.add(delivery)
    session.commit()
    session.refresh(delivery)

    return DeliveryRead(
        id=delivery.id,
        date=delivery.date,
        customer=delivery.customer,
        keg_ids=delivery.get_keg_ids(),
    )

@app.patch("/deliveries/{delivery_id}/payload", response_model=DeliveryRead)
def update_delivery_payload(
    delivery_id: int, update: DeliveryPayloadUpdate, session: Session = Depends(get_session)
):
    delivery = session.get(Delivery, delivery_id)
    if not delivery:
        raise HTTPException(status_code=404, detail=f"Delivery with id {delivery_id} not found")

    delivery.set_keg_ids(update.keg_ids)

    session.add(delivery)
    session.commit()
    session.refresh(delivery)

    return DeliveryRead(
        id=delivery.id,
        date=delivery.date,
        customer=delivery.customer,
        keg_ids=delivery.get_keg_ids(),
    )
