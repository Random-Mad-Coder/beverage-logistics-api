from contextlib import asynccontextmanager
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, Query
from sqlmodel import Session, select

from app.database import create_db_and_tables, get_session
from app.models import (
    Delivery,
    DeliveryCreate,
    DeliveryRead,
    Keg,
    KegCreate,
    KegRead,
    KegStatusUpdate,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Tabellen beim Start anlegen, falls sie noch nicht existieren.
    create_db_and_tables()
    yield


app = FastAPI(title="Fass-Logistik-API", lifespan=lifespan)


# ---------- Kegs ----------

@app.get("/kegs", response_model=list[KegRead])
def list_kegs(
    status: Optional[str] = Query(default=None),
    sorte: Optional[str] = Query(default=None),
    session: Session = Depends(get_session),
):
    query = select(Keg)
    if status:
        query = query.where(Keg.status == status)
    if sorte:
        query = query.where(Keg.sorte == sorte)
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
        raise HTTPException(status_code=404, detail="Fass nicht gefunden")
    return keg


@app.patch("/kegs/{keg_id}/status", response_model=KegRead)
def update_keg_status(
    keg_id: int, update: KegStatusUpdate, session: Session = Depends(get_session)
):
    keg = session.get(Keg, keg_id)
    if not keg:
        raise HTTPException(status_code=404, detail="Fass nicht gefunden")
    keg.status = update.status
    session.add(keg)
    session.commit()
    session.refresh(keg)
    return keg


# ---------- Deliveries ----------

@app.post("/deliveries", response_model=DeliveryRead, status_code=201)
def create_delivery(
    delivery: DeliveryCreate, session: Session = Depends(get_session)
):
    db_delivery = Delivery(datum=delivery.datum, kunde=delivery.kunde)
    db_delivery.set_keg_ids(delivery.keg_ids)
    session.add(db_delivery)
    session.commit()
    session.refresh(db_delivery)
    return DeliveryRead(
        id=db_delivery.id,
        datum=db_delivery.datum,
        kunde=db_delivery.kunde,
        keg_ids=db_delivery.get_keg_ids(),
    )


@app.get("/deliveries/{delivery_id}", response_model=DeliveryRead)
def get_delivery(delivery_id: int, session: Session = Depends(get_session)):
    delivery = session.get(Delivery, delivery_id)
    if not delivery:
        raise HTTPException(status_code=404, detail="Lieferung nicht gefunden")
    return DeliveryRead(
        id=delivery.id,
        datum=delivery.datum,
        kunde=delivery.kunde,
        keg_ids=delivery.get_keg_ids(),
    )
