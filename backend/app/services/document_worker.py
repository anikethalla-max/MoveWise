import time
from app.db.session import SessionLocal
from app.services.documents import process_one


def main():
    print("MoveWise document worker running", flush=True)
    while True:
        with SessionLocal() as db:
            worked = process_one(db)
        if not worked:
            time.sleep(2)


if __name__ == "__main__":
    main()
