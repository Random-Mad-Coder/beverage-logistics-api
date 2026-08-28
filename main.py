from contextlib import asynccontextmanager
from datetime import date
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, Query
from sqlalchemy import func
from sqlmodel import Session, select

from database import create_db_and_tables, get_session
from models import (
    ContainerType,
    Status,
    Variety,
    InventoryReport,
    Delivery,
    DeliveryCreate,
    DeliveryRead,
    DeliveryMetaDataUpdate,
    DeliveryPayloadUpdate,
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


app = FastAPI(title="Fass-Logistik-API", lifespan=lifespan)

# ---------- Inventory ----------

@app.get("/inventory", response_model=list[InventoryReport])
def get_inventory(reserve: int, session: Session = Depends(get_session)):
    query = select(Keg.variety, func.count()).where(Keg.status == Status.FULL).group_by(Keg.variety).having(func.count() < reserve)
    result = session.exec(query).all()

    return [InventoryReport(variety=variety, container_type=ContainerType.KEG, count=count) for (variety, count) in result]


# ---------- Kegs ----------

@app.get("/kegs", response_model=list[KegRead])
def list_kegs(
    status: Optional[Status] = Query(default=None),
    variety: Optional[Variety] = Query(default=None),
    session: Session = Depends(get_session),
):
    query = select(Keg)
    if status:
        query = query.where(Keg.status == status)
    if variety:
        query = query.where(Keg.variety == variety)
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
