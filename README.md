# CodeAlpha_DataRedundancyRemoval
CodeAlpha Cloud Computing Internship - **Task 1: Data Redundancy Removal System**

A small cloud-deployable API that validates incoming records against the database and only appends unique, verified entries.

## How it works
Every record is normalized (case, whitespace, `+tags` in emails, phone digits) and classified as:
| Status | Meaning |
|---|---|
| `unique` | Valid and new - appended to the database |
| `redundant` | Exact duplicate (SHA-256 fingerprint), same email, same phone, or a near-duplicate name on the same email domain (similarity >= 0.9) |
| `false_positive` | Invalid or placeholder data (junk name, malformed email/phone) - never stored |

Non-unique records are logged in a `rejected` table for auditing. Unique indexes in the database are a second guard against duplicates, even under concurrent requests.

## Run
```bash
pip install -r requirements.txt
python app.py                      # http://localhost:8080
pytest                             # run tests
curl -X POST localhost:8080/records -H 'Content-Type: application/json' \
  -d '{"name":"Ann Lee","email":"ann@x.com","phone":"0821234567"}'
```
Endpoints: `POST /records` (object or list), `GET /records`, `GET /stats`, `GET /health`.

## Deploy
`docker build -t redundancy . && docker run -p 8080:8080 -v $PWD/data:/data -e DB_PATH=/data/records.db redundancy`
works on any cloud container service (AWS App Runner/ECS, Azure Container Apps, Google Cloud Run). For a managed database, swap the `sqlite3` calls for PostgreSQL; the unique constraints carry over unchanged.
