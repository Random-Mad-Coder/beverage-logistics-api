from collections import defaultdict
from contextlib import asynccontextmanager
from datetime import date
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from constants import DELIVERY_UNIT_GONE_MESSAGE
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
    DeliveryItem,
    GoodsReceipt,
    GoodsReceiptCreate,
    GoodsReceiptRead,
    GoodsReceiptUpdate,
    InventoryReport,
    PackagingUnit,
    PackagingUnitCreate,
    PackagingUnitRead,
    PackagingUnitUpdate,
    Pallet,
    PalletCreate,
    PalletRead,
    PalletUpdate
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
        select(Beverage.id, Beverage.name, PackagingUnit.container_type, func.count())
        .join(PackagingUnit, PackagingUnit.beverage_id == Beverage.id)
        .where(PackagingUnit.status == Status.FULL)
        .group_by(Beverage.id, Beverage.name, PackagingUnit.container_type)
        .having(func.count() < reserve)
    )
    result = session.exec(query).all()

    return [InventoryReport(beverage_id=beverage_id, beverage_name=beverage_name, container_type=container_type, count=count) for (beverage_id, beverage_name, container_type, count) in result]


# ---------- Beverage ----------

@app.get("/beverages", response_model=list[BeverageRead])
def list_beverages(
    name: Optional[str] = Query(default=None),
    beverage_type: Optional[BeverageType] = Query(default=None),
    session: Session = Depends(get_session)
):
    query = select(Beverage)
    if name:
        query = query.where(Beverage.name == name)
    if beverage_type:
        query = query.where(Beverage.type == beverage_type)

    return session.exec(query).all()


@app.get("/beverages/{beverage_id}", response_model=BeverageRead)
def get_beverage(beverage_id: int, session: Session = Depends(get_session)):
    beverage = session.get(Beverage, beverage_id)
    if not beverage:
        raise HTTPException(status_code=404, detail=f"Beverage with id {beverage_id} not found")
    return beverage


@app.post("/beverages", response_model=BeverageRead, status_code=201)
def create_beverage(beverage: BeverageCreate, session: Session = Depends(get_session)):
    db_beverage = Beverage.model_validate(beverage)
    session.add(db_beverage)

    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(status_code=409, detail=f"Beverage with name {db_beverage.name} already exists")

    session.refresh(db_beverage)
    return db_beverage


@app.delete("/beverages/{beverage_id}", status_code=204)
def delete_beverage(beverage_id: int, session: Session = Depends(get_session)):
    beverage = session.get(Beverage, beverage_id)
    if not beverage:
        raise HTTPException(status_code=404, detail=f"Beverage with id {beverage_id} not found")
    session.delete(beverage)

    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(status_code=409, detail=f"Beverage with id {beverage_id} is still stocked")


# ---------- Delivery ----------

@app.get("/deliveries", response_model=list[DeliveryRead])
def list_deliveries(
    delivery_date: Optional[date] = Query(default=None),
    customer: Optional[str] = Query(default=None),
    session: Session = Depends(get_session)
):
    query = select(Delivery)
    if delivery_date:
        query = query.where(Delivery.delivery_date == delivery_date)
    if customer:
        query = query.where(Delivery.customer == customer)

    deliveries = session.exec(query).all()

    delivery_ids = [d.id for d in deliveries]
    query = select(DeliveryItem).where(DeliveryItem.delivery_id.in_(delivery_ids))
    delivery_items = session.exec(query).all()

    unit_ids_by_delivery = defaultdict(list)
    for item in delivery_items:
        unit_ids_by_delivery[item.delivery_id].append(item.unit_id)

    return [DeliveryRead(id=d.id, delivery_date=d.delivery_date, customer=d.customer, unit_ids=unit_ids_by_delivery[d.id]) for d in deliveries]


@app.get("/deliveries/{delivery_id}", response_model=DeliveryRead)
def get_delivery(delivery_id: int, session: Session = Depends(get_session)):
    delivery = session.get(Delivery, delivery_id)
    if not delivery:
        raise HTTPException(status_code=404, detail=f"Delivery with id {delivery_id} not found")

    query = select(DeliveryItem.unit_id).where(DeliveryItem.delivery_id == delivery_id)
    unit_ids = session.exec(query).all()

    return DeliveryRead(
        id=delivery.id,
        delivery_date=delivery.delivery_date,
        customer=delivery.customer,
        unit_ids=unit_ids,
    )


@app.post("/deliveries", response_model=DeliveryRead, status_code=201)
def create_delivery(
    delivery: DeliveryCreate, session: Session = Depends(get_session)
):
    db_delivery = Delivery.model_validate(delivery)
    query = select(PackagingUnit.id).where(PackagingUnit.id.in_(delivery.unit_ids))
    existing_unit_ids = session.exec(query).all()
    nonexistent_unit_ids = set(delivery.unit_ids) - set(existing_unit_ids)
    if nonexistent_unit_ids:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "Inexistent packaging unit ids",
                "unit_ids": sorted(nonexistent_unit_ids),
            }
        )
    
    session.add(db_delivery)
    session.flush()
    session.add_all([DeliveryItem(delivery_id=db_delivery.id, unit_id=unit_id) for unit_id in delivery.unit_ids])
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(status_code=409, detail=DELIVERY_UNIT_GONE_MESSAGE)
    
    return DeliveryRead(
        delivery_date=db_delivery.delivery_date,
        customer=db_delivery.customer,
        id=db_delivery.id,
        unit_ids=delivery.unit_ids
    )


@app.patch("/deliveries/{delivery_id}/metadata", response_model=DeliveryRead)
def update_delivery_metadata(
    delivery_id: int, update: DeliveryMetaDataUpdate, session: Session = Depends(get_session)
):
    delivery = session.get(Delivery, delivery_id)
    if not delivery:
        raise HTTPException(status_code=404, detail=f"Delivery with id {delivery_id} not found")

    if update.delivery_date:
        delivery.delivery_date = update.delivery_date

    if update.customer and update.customer.strip():
        delivery.customer = update.customer

    session.add(delivery)
    session.commit()
    session.refresh(delivery)

    query = select(DeliveryItem.unit_id).where(DeliveryItem.delivery_id == delivery_id)
    unit_ids = session.exec(query).all()

    return DeliveryRead(
        delivery_date=delivery.delivery_date,
        customer=delivery.customer,
        id=delivery.id,
        unit_ids=unit_ids
    )

@app.patch("/deliveries/{delivery_id}/payload", response_model=DeliveryRead)
def update_delivery_payload(
    delivery_id: int, update: DeliveryPayloadUpdate, session: Session = Depends(get_session)
):
    delivery = session.get(Delivery, delivery_id)
    if not delivery:
        raise HTTPException(status_code=404, detail=f"Delivery with id {delivery_id} not found")

    query = select(DeliveryItem.unit_id).where(DeliveryItem.delivery_id == delivery_id)
    delivery_unit_ids = session.exec(query).all()

    create_unit_ids = set(update.unit_ids) - set(delivery_unit_ids)
    query = select(PackagingUnit.id).where(PackagingUnit.id.in_(create_unit_ids))
    existing_new_unit_ids = session.exec(query).all()
    nonexistent_new_unit_ids = set(create_unit_ids) - set(existing_new_unit_ids)
    if nonexistent_new_unit_ids:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "Inexistent packaging unit ids",
                "unit_ids": sorted(nonexistent_new_unit_ids),
            }
        )
    session.add_all([DeliveryItem(delivery_id=delivery_id, unit_id=id) for id in create_unit_ids])

    delete_unit_ids = set(delivery_unit_ids) - set(update.unit_ids)
    query = select(DeliveryItem).where(DeliveryItem.unit_id.in_(delete_unit_ids), DeliveryItem.delivery_id == delivery_id)
    delete_items = session.exec(query).all()
    for item in delete_items:
        session.delete(item)
    
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(status_code=409, detail=DELIVERY_UNIT_GONE_MESSAGE)

    return DeliveryRead(
        delivery_date=delivery.delivery_date,
        customer=delivery.customer,
        id=delivery.id,
        unit_ids=update.unit_ids
    )


@app.delete("/deliveries/{delivery_id}", status_code=204)
def delete_delivery(delivery_id: int, session: Session = Depends(get_session)):
    delivery = session.get(Delivery, delivery_id)
    if not delivery:
        raise HTTPException(status_code=404, detail=f"Delivery with id {delivery_id} not found")

    query = select(DeliveryItem).where(DeliveryItem.delivery_id == delivery_id)
    delete_items = session.exec(query).all()
    for item in delete_items:
        session.delete(item)
    # Without ORM relationships the unit of work doesn't know that the items
    # have to be deleted before the delivery, so enforce the order explicitly
    session.flush()
    session.delete(delivery)

    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(status_code=409, detail=DELIVERY_UNIT_GONE_MESSAGE)


# ---------- GoodsReceipt ----------

def count_pallets(goods_receipt_id: int, session: Session) -> int:
    query = select(func.count()).where(Pallet.goods_receipt_id == goods_receipt_id)
    return session.exec(query).one()


@app.get("/goods-receipts", response_model=list[GoodsReceiptRead])
def list_goods_receipt(
    receipt_date: Optional[date] = Query(default=None),
    supplier: Optional[str] = Query(default=None),
    session: Session = Depends(get_session)
):
    query = select(GoodsReceipt)
    if receipt_date:
        query = query.where(GoodsReceipt.receipt_date == receipt_date)
    if supplier:
        query = query.where(GoodsReceipt.supplier == supplier)

    goods_receipts = session.exec(query).all()

    goods_receipt_ids = [r.id for r in goods_receipts]
    query = (
        select(Pallet.goods_receipt_id, func.count())
        .where(Pallet.goods_receipt_id.in_(goods_receipt_ids))
        .group_by(Pallet.goods_receipt_id)
    )
    pallet_counts = dict(session.exec(query).all())

    return [GoodsReceiptRead.model_validate(r, update={"actual_pallet_count": pallet_counts.get(r.id, 0)}) for r in goods_receipts]


@app.get("/goods-receipts/{goods_receipt_id}", response_model=GoodsReceiptRead)
def get_goods_receipt(goods_receipt_id: int, session: Session = Depends(get_session)):
    goods_receipt = session.get(GoodsReceipt, goods_receipt_id)
    if not goods_receipt:
        raise HTTPException(status_code=404, detail=f"Goods receipt with id {goods_receipt_id} not found")

    return GoodsReceiptRead.model_validate(goods_receipt, update={"actual_pallet_count": count_pallets(goods_receipt_id, session)})


@app.post("/goods-receipts", response_model=GoodsReceiptRead, status_code=201)
def create_goods_receipt(goods_receipt: GoodsReceiptCreate, session: Session = Depends(get_session)):
    db_goods_receipt = GoodsReceipt.model_validate(goods_receipt)
    session.add(db_goods_receipt)
    session.commit()
    session.refresh(db_goods_receipt)
    # A freshly created goods receipt cannot have any pallets yet
    return GoodsReceiptRead.model_validate(db_goods_receipt, update={"actual_pallet_count": 0})


@app.patch("/goods-receipts/{goods_receipt_id}", response_model=GoodsReceiptRead)
def update_goods_receipt(
    goods_receipt_id: int, update: GoodsReceiptUpdate, session: Session = Depends(get_session)
):
    db_receipt = session.get(GoodsReceipt, goods_receipt_id)
    if not db_receipt:
        raise HTTPException(status_code=404, detail=f"Goods receipt with id {goods_receipt_id} not found")

    # return only values sent in the request as a dict
    changes = update.model_dump(exclude_unset=True)
    for field, value in changes.items():
        # expected_pallet_count is optional and can be reset via an explicit null,
        # null for the required fields is ignored
        if value is None and field != "expected_pallet_count":
            continue
        setattr(db_receipt, field, value)

    session.add(db_receipt)
    session.commit()
    session.refresh(db_receipt)
    return GoodsReceiptRead.model_validate(db_receipt, update={"actual_pallet_count": count_pallets(goods_receipt_id, session)})


@app.delete("/goods-receipts/{goods_receipt_id}", status_code=204)
def delete_goods_receipt(goods_receipt_id: int, session: Session = Depends(get_session)):
    goods_receipt = session.get(GoodsReceipt, goods_receipt_id)
    if not goods_receipt:
        raise HTTPException(status_code=404, detail=f"Goods receipt with id {goods_receipt_id} not found")
    session.delete(goods_receipt)

    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(status_code=409, detail=f"Goods receipt with id {goods_receipt_id} still has pallets referencing it")


# ---------- PackagingUnit ----------

@app.get("/packaging-units", response_model=list[PackagingUnitRead])
def list_packaging_units(
    beverage_name: Optional[str] = Query(default=None),
    container_type: Optional[ContainerType] = Query(default=None),
    status: Optional[Status] = Query(default=None),
    session: Session = Depends(get_session)
):
    query = select(PackagingUnit)
    if beverage_name:
        query = query.join(Beverage, PackagingUnit.beverage_id == Beverage.id).where(Beverage.name == beverage_name)
    if container_type:
        query = query.where(PackagingUnit.container_type == container_type)
    if status:
        query = query.where(PackagingUnit.status == status)

    return session.exec(query).all()


@app.get("/packaging-units/{unit_id}", response_model=PackagingUnitRead)
def get_packaging_unit(unit_id: int, session: Session = Depends(get_session)):
    unit = session.get(PackagingUnit, unit_id)
    if not unit:
        raise HTTPException(status_code=404, detail=f"Packaging unit with id {unit_id} not found")
    return unit


@app.post("/packaging-units", response_model=PackagingUnitRead, status_code=201)
def create_packaging_unit(unit: PackagingUnitCreate, session: Session = Depends(get_session)):
    db_unit = PackagingUnit.model_validate(unit)
    session.add(db_unit)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(status_code=409, detail=f"Beverage with id {db_unit.beverage_id} or pallet with id {db_unit.received_via_pallet_id} does not exist")
    session.refresh(db_unit)
    return db_unit


@app.patch("/packaging-units/{unit_id}", response_model=PackagingUnitRead)
def update_packaging_unit(
    unit_id: int, update: PackagingUnitUpdate, session: Session = Depends(get_session)
):
    unit = session.get(PackagingUnit, unit_id)
    if not unit:
        raise HTTPException(status_code=404, detail=f"Packaging unit with id {unit_id} not found")
    
    unit.status = update.status
    session.add(unit)
    session.commit()
    session.refresh(unit)
    return unit


@app.delete("/packaging-units/{unit_id}", status_code=204)
def delete_packaging_unit(unit_id: int, session: Session = Depends(get_session)):
    unit = session.get(PackagingUnit, unit_id)
    if not unit:
        raise HTTPException(status_code=404, detail=f"Packaging unit with id {unit_id} not found")
    session.delete(unit)

    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(status_code=409, detail=f"Packaging unit with id {unit_id} is still part of a delivery")


# ---------- Pallet ----------

@app.get("/pallets", response_model=list[PalletRead])
def list_pallets(
    best_before: Optional[date] = Query(default=None),
    beverage_id: Optional[int] = Query(default=None),
    container_type: Optional[ContainerType] = Query(default=None),
    goods_receipt_id: Optional[int] = Query(default=None),
    session: Session = Depends(get_session)
):
    query = select(Pallet)
    if best_before:
        query = query.where(Pallet.best_before_date == best_before)
    if beverage_id:
        query = query.where(Pallet.beverage_id == beverage_id)
    if container_type:
        query = query.where(Pallet.container_type == container_type)
    if goods_receipt_id:
        query = query.where(Pallet.goods_receipt_id == goods_receipt_id)

    return session.exec(query).all()


@app.get("/pallets/{pallet_id}", response_model=PalletRead)
def get_pallet(pallet_id: int, session: Session = Depends(get_session)):
    pallet = session.get(Pallet, pallet_id)
    if not pallet:
        raise HTTPException(status_code=404, detail=f"Pallet with id {pallet_id} not found")

    return PalletRead.model_validate(pallet)


@app.post("/pallets", response_model=PalletRead, status_code=201)
def create_pallet(pallet: PalletCreate, session: Session = Depends(get_session)):
    db_pallet = Pallet.model_validate(pallet)
    session.add(db_pallet)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(status_code=409, detail=f"Beverage with id {db_pallet.beverage_id} or goods receipt with id {db_pallet.goods_receipt_id} does not exist")
    session.refresh(db_pallet)
    return db_pallet


def unpack(pallet: Pallet, session: Session) -> list[PackagingUnit]:
    item_list = [        
        PackagingUnit(
            container_type=pallet.container_type,
            beverage_id=pallet.beverage_id,
            best_before_date=pallet.best_before_date,
            received_via_pallet_id=pallet.id
        ) for _ in range(pallet.quantity)
        ]
    session.add_all(item_list)
    session.commit()

    for item in item_list:
        session.refresh(item)

    return item_list


@app.post("/pallets/{pallet_id}/unpack", response_model=list[PackagingUnitRead])
def unpack_pallet(pallet_id: int, session: Session = Depends(get_session)):
    pallet = session.get(Pallet, pallet_id)
    if not pallet:
        raise HTTPException(status_code=404, detail=f"Pallet with id {pallet_id} not found")

    query = select(PackagingUnit).where(PackagingUnit.received_via_pallet_id == pallet_id)
    units = session.exec(query).all()

    if not units:
        return unpack(pallet, session)

    count = len(units)
    sample = units[0]

    if (
        sample.beverage_id == pallet.beverage_id 
        and sample.container_type == pallet.container_type 
        and sample.best_before_date == pallet.best_before_date
        and count == pallet.quantity
    ):
        raise HTTPException(status_code=409, detail=f"Pallet with id {pallet_id} is already unpacked with unchanged data")

    pallet_unit_ids = [item.id for item in units]
    query = select(DeliveryItem).where(DeliveryItem.unit_id.in_(pallet_unit_ids))
    delivery_units = session.exec(query).all()

    if delivery_units:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "Packaging units are still part of a delivery",
                "unit_ids": sorted([item.unit_id for item in delivery_units]),
            }
        )
    
    for item in units:
        session.delete(item)

    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(status_code=409, detail="Error deleting existing packaging units")

    return unpack(pallet, session)


@app.patch("/pallets/{pallet_id}", response_model=PalletRead)
def update_pallet(
    pallet_id: int, update: PalletUpdate, session: Session = Depends(get_session)
):
    db_pallet = session.get(Pallet, pallet_id)
    if not db_pallet:
        raise HTTPException(status_code=404, detail=f"Pallet with id {pallet_id} not found")

    # return only set values as a dict
    changes = update.model_dump(exclude_none=True)
    for field, value in changes.items():
        setattr(db_pallet, field, value)

    session.add(db_pallet)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(status_code=409, detail=f"Beverage with id {db_pallet.beverage_id} does not exist")
    session.refresh(db_pallet)
    return db_pallet


@app.delete("/pallets/{pallet_id}", status_code=204)
def delete_pallet(pallet_id: int, session: Session = Depends(get_session)):
    pallet = session.get(Pallet, pallet_id)
    if not pallet:
        raise HTTPException(status_code=404, detail=f"Pallet with id {pallet_id} not found")
    session.delete(pallet)

    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(status_code=409, detail=f"Pallet with id {pallet_id} still has packaging units referencing it")