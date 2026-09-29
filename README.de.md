# Beverage Logistics API

[English](README.md) | **Deutsch**

Eine kleine REST-API zur Verwaltung von Getränkebestand, Wareneingängen und
Auslieferungen einer Brauerei (Fässer und Kisten), entstanden als
Portfolio-Projekt für Backend-Entwicklung.

## Tech-Stack

- **Python 3.14**
- **FastAPI** — Web-Framework
- **SQLModel** (Pydantic + SQLAlchemy) — Datenmodelle und ORM
- **SQLite** — Datenbank in einer einzigen Datei, kein separater DB-Server nötig
- **Uvicorn** — ASGI-Server
- **pytest** + FastAPI `TestClient` — automatisierte Tests
- **Docker** — containerisiertes Deployment

## Architektur

Flache Dateistruktur, kein `app/`-Paket:

```
beverage-logistics-api/
├── main.py           # FastAPI-App, alle Routen
├── models.py         # SQLModel-Entitäten, Enums, Request-/Response-Schemas
├── database.py       # Engine, Session-Dependency
├── constants.py      # gemeinsame Konstanten (Datumsformat, Fehlermeldungen)
├── conftest.py       # pytest-Fixtures (Test-DB, Test-Client, Factories)
├── tests/
│   ├── test_deliveries.py
│   ├── test_goods_receipts.py
│   ├── test_inventory.py
│   ├── test_packaging_units.py
│   └── test_pallet.py
├── docs/             # ER- und Anwendungsfalldiagramm
├── requirements.txt       # Laufzeitabhängigkeiten
├── requirements-dev.txt   # + Testabhängigkeiten
├── Dockerfile
└── .dockerignore
```

## Datenmodell

![ER-Diagramm des Datenmodells](docs/er-diagram.svg)

*(Diagrammquelle: [`docs/er-diagram.mmd`](docs/er-diagram.mmd),
Mermaid-Syntax — bei Änderungen am Modell die Quelle anpassen und neu
rendern.)*

- **`Beverage`** (Getränk) ist eine eigene Entität mit einem `type`-Feld
  statt eines Enums für Biersorten. Die Brauerei, an der sich dieses Projekt
  orientiert, verkauft tatsächlich mehr Limonade und Wasser als Bier. Sobald
  andere Getränke als Bier dazukommen, ist „Sorte“ keine einzelne Dimension
  mehr.
- **`PackagingUnit`** (Gebinde) bildet Fässer und Kisten in einer
  gemeinsamen Tabelle ab. Unterschieden werden sie allein über das
  `ContainerType`-Enum (`keg_20l`, `keg_30l`, `keg_50l`, `crate_20x05l`,
  `crate_24x033l`). Ursprünglich waren getrennte Tabellen `Keg` und `Crate`
  geplant, am Ende hatten beide aber dieselben Attribute. Verschiedene
  Größen sind Enum-Werte statt eigener Tabellen, weil die Menge realer
  Gebindegrößen klein und stabil ist.
- **`GoodsReceipt`** (Wareneingang) und **`Pallet`** (Palette) bilden
  eingehende Ware ab. Eine Palette wird über `POST /pallets/{id}/unpack` in
  einzelne Gebinde ausgepackt. `expected_pallet_count` stammt vom
  Lieferschein und ist optional; das berechnete `actual_pallet_count` dient
  als Prüfsumme und darf davon abweichen.
- **`DeliveryItem`** ist die Verknüpfungstabelle zwischen `Delivery`
  (Auslieferung) und `PackagingUnit`. Damit stellt die Datenbank selbst
  sicher, dass eine Auslieferung nur existierende Gebinde referenziert.
  Auslieferungen sind historische Datensätze: Ein Gebinde durchläuft
  `full` → `empty` → `cleaned` → `full` und wird wiederverwendet, daher kann
  dasselbe Gebinde in mehreren Auslieferungen vorkommen.
- **`Status`** (`empty`/`cleaned`/`full`) gilt gemeinsam für Fässer und
  Kisten. Das ist eine bewusste Vereinfachung: In der Praxis werden Kisten
  selten als Ganzes „gereinigt“ — die einzelnen Flaschen werden separat
  gespült und neu befüllt —, sodass `cleaned` bei Kisten praktisch ungenutzt
  bleiben kann. Für den Moment ist das vertretbar, weil die API keine
  *Statusübergänge* erzwingt; `status` ist ein einfaches Feld, keine
  Zustandsmaschine. Ob ein Gebinde gerade Teil einer Auslieferung ist, ist
  ebenfalls kein Status; dafür ist allein `DeliveryItem` maßgeblich.
- Bewusst **keine** eigene `Stock`-Tabelle: Relevant ist hier nur der
  aktuelle Bestand, nicht sein Verlauf. Die Live-Aggregation, die
  `/inventory` verwendet, bleibt daher korrekt, ohne einen denormalisierten
  Zähler einzuführen, der mit den tatsächlichen Datensätzen auseinanderlaufen
  könnte.

Die Konsistenz der Fremdschlüssel erzwingt die Datenbank (SQLite mit
`PRAGMA foreign_keys=ON`); Verstöße werden als HTTP 409 zurückgegeben.
Darüber hinausgehende Geschäftsregeln bleiben, wo möglich, bewusst dem
Client überlassen.

## Anwendungsfälle

![Anwendungsfalldiagramm des Lagerablaufs](docs/use-case-diagram.svg)

*(Diagrammquelle: [`docs/use-case-diagram.drawio`](docs/use-case-diagram.drawio),
draw.io.)*

Die Anwendungsfälle folgen dem Ablauf im Lager: Ware kommt als Wareneingang
mit Paletten an, Paletten werden in einzelne Fässer und Kisten ausgepackt,
deren Status wird beim Leeren und Reinigen aktualisiert, der Bestand wird
gegen eine Mindestreserve geprüft, und volle Gebinde verlassen das Lager als
Auslieferungen. Jeder Anwendungsfall wird von den unten aufgeführten
Endpunkten bedient.

## Endpunkte

| Methode | Pfad | Beschreibung |
|---------|------|--------------|
| GET    | `/beverages` | Getränke auflisten, optional gefiltert nach `name`/`beverage_type` |
| POST   | `/beverages` | Getränk anlegen |
| GET    | `/beverages/{beverage_id}` | Einzelnes Getränk abrufen |
| DELETE | `/beverages/{beverage_id}` | Getränk löschen |
| GET    | `/goods-receipts` | Wareneingänge auflisten, optional gefiltert nach `receipt_date`/`supplier` |
| POST   | `/goods-receipts` | Wareneingang anlegen |
| GET    | `/goods-receipts/{goods_receipt_id}` | Einzelnen Wareneingang abrufen, inklusive `actual_pallet_count` |
| PATCH  | `/goods-receipts/{goods_receipt_id}` | Wareneingang ändern |
| DELETE | `/goods-receipts/{goods_receipt_id}` | Wareneingang löschen |
| GET    | `/pallets` | Paletten auflisten, optional gefiltert nach `best_before`/`beverage_id`/`container_type`/`goods_receipt_id` |
| POST   | `/pallets` | Palette anlegen |
| GET    | `/pallets/{pallet_id}` | Einzelne Palette abrufen |
| PATCH  | `/pallets/{pallet_id}` | Palette ändern |
| DELETE | `/pallets/{pallet_id}` | Palette löschen |
| POST   | `/pallets/{pallet_id}/unpack` | Pro Stück auf der Palette ein Gebinde anlegen; erneutes Auspacken legt sie neu an, falls sich die Palettendaten geändert haben |
| GET    | `/packaging-units` | Gebinde auflisten, optional gefiltert nach `beverage_name`/`container_type`/`status` |
| POST   | `/packaging-units` | Gebinde anlegen |
| GET    | `/packaging-units/{unit_id}` | Einzelnes Gebinde abrufen |
| PATCH  | `/packaging-units/{unit_id}` | `status` eines Gebindes ändern |
| DELETE | `/packaging-units/{unit_id}` | Gebinde löschen |
| GET    | `/deliveries` | Auslieferungen auflisten, optional gefiltert nach `delivery_date`/`customer` |
| POST   | `/deliveries` | Auslieferung anlegen |
| GET    | `/deliveries/{delivery_id}` | Einzelne Auslieferung abrufen |
| PATCH  | `/deliveries/{delivery_id}/metadata` | `delivery_date` und/oder `customer` einer Auslieferung ändern |
| PATCH  | `/deliveries/{delivery_id}/payload` | `unit_ids` einer Auslieferung ersetzen |
| DELETE | `/deliveries/{delivery_id}` | Auslieferung löschen |
| GET    | `/inventory?reserve={n}` | Endpunkt mit Geschäftslogik: zählt je Getränk und Gebindetyp die Gebinde mit `status=full` und gibt nur die Kombinationen zurück, deren Anzahl unter `reserve` liegt |

`/inventory` ist der Endpunkt, der echte Geschäftslogik statt reinem CRUD
zeigt: Er aggregiert und filtert auf Datenbankseite (SQL `GROUP BY` /
`HAVING`), statt alle Datensätze zu laden und in Python zu zählen.

Die interaktive Dokumentation unter `/docs` gruppiert die Endpunkte nach
diesen Bereichen und beschreibt nicht offensichtliches Verhalten sowie die
möglichen Fehlerantworten. 409-Antworten, die Gebinde-IDs auflisten, liefern
ein strukturiertes `detail` (`{"message": ..., "unit_ids": [...]}`), alle
anderen Fehler einen einfachen String.

## Bekannte Einschränkung

Es gibt noch keine Schema-Migrationen. Die Tabellen werden mit `create_all`
von SQLModel angelegt, das bestehende Tabellen nicht verändert. Nach einer
Schemaänderung muss die lokale `beverage_logistics.db` daher gelöscht und
neu angelegt werden. Ein Migrationswerkzeug (z. B. Alembic) wäre Teil der
PostgreSQL-Ausbaustufe (siehe [Roadmap](#roadmap)).

## Lokal ausführen

```powershell
git clone <repo-url>
cd beverage-logistics-api

python -m venv .venv
.\.venv\Scripts\Activate.ps1

pip install -r requirements.txt

uvicorn main:app --reload
```

Die API ist dann unter `http://localhost:8000` erreichbar, die interaktive
Dokumentation unter `http://localhost:8000/docs`.

## Mit Docker ausführen

```bash
docker build -t beverage-logistics-api .
docker run -p 8000:8000 beverage-logistics-api
```

Der Container läuft als Nicht-Root-Benutzer und basiert auf
`python:3.14.3-slim`, um Image-Größe und Angriffsfläche klein zu halten.

Hinweis: Die SQLite-Datenbankdatei liegt im Dateisystem des Containers und
bleibt über Container-Neustarts hinweg nicht erhalten. Ein Volume-Mount wäre
Teil der PostgreSQL-/docker-compose-Ausbaustufe (siehe [Roadmap](#roadmap)).

## Tests ausführen

```powershell
pip install -r requirements-dev.txt
pytest
```

`requirements-dev.txt` ergänzt `requirements.txt` um die Testabhängigkeiten
(pytest, httpx2 für den `TestClient` von FastAPI, python-dateutil).
`requirements.txt` enthält nur, was die App zur Laufzeit braucht, und ist
alles, was das Docker-Image installiert.

Die Tests verwenden über `dependency_overrides` eine In-Memory-SQLite-Datenbank
und berühren die echte `beverage_logistics.db` daher nie. Testdaten werden
über die API selbst angelegt (Black-Box), mit einer Fixture-Kette in
`conftest.py` (`beverage` → `goods_receipt` → `pallet` → `unpacked_pallet`
→ `delivery`) und zusätzlichen Factory-Fixtures (`make_unit`,
`make_pallet`, `make_delivery`).

## Roadmap

Diese Ausbaustufen sind bewusst **nicht** Teil des aktuellen Stands — sie
sind hier als Planung dokumentiert, nicht als umgesetzte Funktionen.

1. **Produktionsreife Datenbank**
   - Umstieg von SQLite auf PostgreSQL
   - docker-compose, um App und Datenbank gemeinsam zu betreiben, mit einem
     Volume für Persistenz
   - Schema-Migrationen (z. B. Alembic)

2. **Gründlichere Tests**
   - Testcontainers (echtes PostgreSQL in den Tests statt SQLite)
   - Breitere Abdeckung von Randfällen der Geschäftslogik

3. **Brücke in die Cloud**
   - CI/CD mit GitHub Actions
   - Cloud-Deployment (z. B. AWS ECS, Fly.io, Render)
   - Infrastructure as Code (Terraform)
   - JWT-basierte Authentifizierung für schreibende Endpunkte
   - Observability: Health-Endpunkt, Logging, Metriken

## Lizenz

[MIT](LICENSE)
