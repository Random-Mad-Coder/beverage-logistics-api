"""
"""
import json
from datetime import date
from enum import Enum
from typing import Optional
from sqlmodel import SQLModel, Field

# ---------- General Business Logic ----------

class ContainerType(str, Enum):
    KEG_20L = "keg_20l"
    KEG_30L = "keg_30l"
    KEG_50L = "keg_50l"
    CRATE_20X05L = "crate_20x05l"
    CRATE_24X033L = "crate_24x033l"

class Status(str, Enum):
    EMPTY = "empty"
    CLEANED = "cleaned"
    IN_DELIVERY = "in_delivery"
    FULL = "full"

# Consciously conflated water and lemonade into a soft_drink category
# Could be changed if ever relevant to the domain in question
class BeverageType(str, Enum):
    BEER = "beer"
    SOFT_DRINK = "soft_drink"

# ---------- Beverage ----------

class BeverageBase(SQLModel):
    name: str
    type: BeverageType

class Beverage(BeverageBase, table=True):
    name: str = Field(unique=True)
    id: Optional[int] = Field(default=None, primary_key=True)

class BeverageCreate(BeverageBase):
    pass

class BeverageRead(BeverageBase):
    id: int

# ---------- Delivery ----------

class DeliveryBase(SQLModel):
    date: date
    customer: str

class Delivery(DeliveryBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    # SQLite cannot store lists -> stored as JSON text.
    # Externally (API) clients just see a normal list of ints.
    keg_ids_json: str = "[]"

    def get_keg_ids(self) -> list[int]:
        return json.loads(self.keg_ids_json)

    def set_keg_ids(self, keg_ids: list[int]) -> None:
        self.keg_ids_json = json.dumps(keg_ids)

class DeliveryCreate(DeliveryBase):
    keg_ids: list[int] = []

class DeliveryRead(DeliveryBase):
    id: int
    keg_ids: list[int]

class DeliveryMetaDataUpdate(SQLModel):
    date: Optional[date] = None
    customer: Optional[str] = None

class DeliveryPayloadUpdate(SQLModel):
    keg_ids: list[int]

# ---------- GoodsReceipt ----------

class GoodsReceiptBase(SQLModel):
    date: date
    supplier: str
    expected_pallet_count: Optional[int] = None

class GoodsReceipt(GoodsReceiptBase, table=True):
    __tablename__ = "goods_receipt"
    id: Optional[int] = Field(default=None, primary_key=True)

class GoodsReceiptCreate(GoodsReceiptBase):
    pass

class GoodsReceiptRead(GoodsReceiptBase):
    id: int
    actual_pallet_count: int

class GoodsReceiptUpdate(SQLModel):
    date: Optional[date] = None
    supplier: Optional[str] = None
    expected_pallet_count: Optional[int] = None

# ---------- Inventory ----------

class InventoryReport(SQLModel):
    beverage_id: int
    beverage_name: str
    container_type: ContainerType
    count: int

# ---------- PackagingUnit ----------

class PackagingUnitBase(SQLModel):
    container_type: ContainerType
    beverage_id: int
    status: Status = Status.EMPTY
    best_before_date: date
    received_via_pallet_id: Optional[int] = None

class PackagingUnit(PackagingUnitBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    beverage_id: int = Field(foreign_key="beverage.id")
    received_via_pallet_id: Optional[int] = Field(default=None, foreign_key="pallet.id")

class PackagingUnitCreate(PackagingUnitBase):
    pass

class PackagingUnitRead(PackagingUnitBase):
    id: int

class PackagingUnitUpdate(SQLModel):
    status: Status

# ---------- Pallet ----------

class PalletBase(SQLModel):
    container_type: ContainerType
    beverage_id: int
    goods_receipt_id: int
    quantity: int
    best_before_date: date

class Pallet(PalletBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    beverage_id: int = Field(foreign_key="beverage.id")
    goods_receipt_id: int = Field(foreign_key="goods_receipt.id")

class PalletCreate(PalletBase):
    pass

class PalletRead(PalletBase):
    id: int

class PalletUpdate(SQLModel):
    container_type: Optional[ContainerType] = None
    beverage_id: Optional[int] = None
    quantity: Optional[int] = None
    best_before_date: Optional[date] = None