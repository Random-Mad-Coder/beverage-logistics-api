"""Datenmodell: Keg (Fass) und Delivery (Lieferung).

Bewusst minimal gehalten (Minimalbuild):
- Keg: id, groesse, sorte, status
- Delivery: id, datum, kunde, keg_ids (als JSON-String in SQLite gespeichert,
  nach außen als Liste von ints)
"""
import json
from datetime import date
from typing import Optional

from sqlmodel import SQLModel, Field


# ---------- Keg ----------

class KegBase(SQLModel):
    groesse: str  # "20l", "30l", "50l"
    sorte: str    # "Pils", "Weizen", ...
    status: str = "LEER"  # VOLL, UNTERWEGS, LEER, GEREINIGT


class Keg(KegBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)


class KegCreate(KegBase):
    pass


class KegRead(KegBase):
    id: int


class KegStatusUpdate(SQLModel):
    status: str


# ---------- Delivery ----------

class DeliveryBase(SQLModel):
    datum: date
    kunde: str


class Delivery(DeliveryBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    # SQLite kann keine Listen speichern -> als JSON-Text ablegen.
    # Nach außen (API) sehen Clients ganz normal eine Liste von ints.
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
