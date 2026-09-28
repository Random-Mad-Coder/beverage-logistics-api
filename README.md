# Fass-Logistik-API (Keg Logistics API)

A small REST API for managing kegs and deliveries for a brewery, built as a
backend-development portfolio project.

## Tech stack

- **Python 3.14**
- **FastAPI** — web framework
- **SQLModel** (Pydantic + SQLAlchemy) — data models and ORM
- **SQLite** — single-file database, no separate DB server required
- **Uvicorn** — ASGI server
- **pytest** + FastAPI `TestClient` — automated tests
- **Docker** — containerized deployment

## Architecture

Flat file structure, no `app/` package:

```
keg-logistics-api/
├── main.py           # FastAPI app, all route definitions
├── models.py         # SQLModel entities, enums, request/response schemas
├── database.py       # engine, session dependency
├── conftest.py       # pytest fixtures (test DB, test client)
├── tests/
│   ├── test_kegs.py
│   ├── test_deliveries.py
│   └── test_inventory.py
├── requirements.txt
├── Dockerfile
└── .dockerignore
```

## Endpoints

| Method | Path                          | Description                                      |
|--------|-------------------------------|---------------------------------------------------|
| GET    | `/kegs`                       | List kegs, optionally filtered by `status`/`variety` |
| POST   | `/kegs`                       | Create a keg                                       |
| GET    | `/kegs/{keg_id}`              | Get a single keg                                   |
| PATCH  | `/kegs/{keg_id}/status`       | Update a keg's status                              |
| DELETE | `/kegs/{keg_id}`              | Delete a keg                                       |
| POST   | `/deliveries`                 | Create a delivery                                  |
| GET    | `/deliveries/{delivery_id}`   | Get a single delivery                              |
| GET    | `/deliveries`                 | List deliveries, optionally filtered by `delivery_date`/`customer` |
| PATCH  | `/deliveries/{delivery_id}/metadata` | Update delivery `delivery_date` and/or `customer` |
| PATCH  | `/deliveries/{delivery_id}/payload`  | Replace a delivery's `keg_ids`              |
| DELETE | `/deliveries/{delivery_id}`   | Delete a delivery                                  |
| GET    | `/inventory?reserve={n}`      | Business-logic endpoint: for each variety, count kegs with `status=full` and return only varieties whose count is below `reserve` |

`/inventory` is the endpoint that demonstrates real business logic rather
than plain CRUD: it aggregates and filters on the database side (SQL
`GROUP BY` / `HAVING`) rather than loading all rows and counting in Python.

## Known limitation

`Delivery.keg_ids` is not validated against the `Keg` table — the API
currently accepts any list of integers, whether or not they correspond to
existing kegs. This is a deliberate scope cut for the MVP, not an oversight;
a proper many-to-many relationship (see [Roadmap](#roadmap)) would enforce
this at the database level.

## Running locally

```powershell
git clone <repo-url>
cd keg-logistics-api

python -m venv .venv
.\.venv\Scripts\Activate.ps1

pip install -r requirements.txt

uvicorn main:app --reload
```

The API is then available at `http://localhost:8000`, with interactive docs
at `http://localhost:8000/docs`.

## Running with Docker

```bash
docker build -t keg-logistics-api .
docker run -p 8000:8000 keg-logistics-api
```

The container runs as a non-root user and is based on `python:3.14.3-slim`
to keep the image size and vulnerability surface small.

Note: the SQLite database file lives inside the container's filesystem and
is not persisted across container restarts. Adding a volume mount would be
part of the PostgreSQL/docker-compose extension stage (see
[Roadmap](#roadmap)).

## Running tests

```powershell
pytest
```

Tests use an in-memory SQLite database via `dependency_overrides`, so they
never touch the real `fass_logistik.db`.

## Roadmap

These extension stages are deliberately **not** part of the current MVP —
they are documented here as planning, not as implemented features.

1. **Fuller data model**

   Target entity design (planning only — not yet implemented):

   ![ER diagram of the target data model](docs/er-diagram.svg)

   *(Diagram source: [`docs/er-diagram.mmd`](docs/er-diagram.mmd), Mermaid
   syntax — edit the source and re-render if the model changes.)*

   - Replace the `Variety` enum with a `Beverage` entity. The brewery this
     project is modeled on actually sells more lemonade and water than beer —
     "variety" is not a single dimension once non-beer beverages are
     included, so this needs a proper entity (with a `type` field) rather
     than an enum of beer styles.
   - Add a `Crate` entity alongside `Keg` (a separate table, not a shared one
     with `Keg`, since the two have different attributes). Different crate
     sizes (e.g. 20×0.5l, 24×0.33l) are modeled as additional `ContainerType`
     enum values rather than as separate tables, since the set of real-world
     crate sizes is small and stable.
   - Two separate junction tables, `DeliveryKeg` and `DeliveryCrate`, replace
     the current JSON-encoded `keg_ids` list. This closes the validation gap
     described above: the database itself can enforce that a delivery only
     ever references kegs/crates that actually exist.
   - `Keg` and `Crate` are planned to share one `Status` enum
     (`empty`/`cleaned`/`in_delivery`/`full`). This is a known simplification:
     in practice, crates as a whole are rarely "cleaned" — individual bottles
     are rinsed and refilled separately — so `cleaned` may end up effectively
     unused for `Crate`. Acceptable for now because nothing in the API
     enforces state *transitions*; `status` is a plain field, not a state
     machine.
   - Deliberately **no** dedicated `Stock` table: only current stock matters
     here, not stock over time, so live aggregation — the approach
     `/inventory` already uses — stays accurate without introducing a
     denormalized count that could drift out of sync with the actual rows.

2. **Production-grade database**
   - Switch from SQLite to PostgreSQL
   - Add docker-compose to run the app and database together, with a volume
     for persistence

3. **More thorough testing**
   - Testcontainers (real PostgreSQL in tests instead of SQLite)
   - Broader coverage of business-logic edge cases

4. **Cloud bridge**
   - CI/CD via GitHub Actions
   - Cloud deployment (e.g. AWS ECS, Fly.io, Render)
   - Infrastructure as Code (Terraform)
   - JWT-based authentication for write endpoints
   - Observability: health endpoint, logging, metrics
