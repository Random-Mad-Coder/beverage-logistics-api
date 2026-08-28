"""Data model: Keg and Delivery.

Kept deliberately minimal (minimal build):
- Keg: id, size, variety, status
- Delivery: id, date, customer, keg_ids (stored as a JSON string in SQLite,
  exposed externally as a list of ints)
"""
import json
from datetime import date
from enum import Enum
from typing import Optional
from sqlmodel import SQLModel, Field

# ---------- General Business Logic ----------

class ContainerType(str, Enum):
    KEG = "keg"

class Status(str, Enum):
    EMPTY = "empty"
    CLEANED = "cleaned"
    IN_DELIVERY = "in_delivery"
    FULL = "full"

class Variety(str, Enum):
    IPA = "ipa"
    STOUT = "stout"
    PILSENER = "pilsener"
    HELLES = "helles"
    DUNKEL = "dunkel"
    BOCK = "bock"

# ---------- Inventory ----------

class InventoryReport(SQLModel):
    variety: Variety
    container_type: ContainerType
    count: int

# ---------- Keg ----------

class KegBase(SQLModel):
    size: str  # "20l", "30l", "50l"
    variety: Variety
    status: Status = Status.EMPTY

class Keg(KegBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)

class KegCreate(KegBase):
    pass

class KegRead(KegBase):
    id: int

class KegStatusUpdate(SQLModel):
    status: Status

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