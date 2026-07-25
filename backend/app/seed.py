from app.database.session import SessionLocal
from app.services.category_seed_service import seed_categories


def main() -> None:
    with SessionLocal() as session:
        result = seed_categories(session)
    print(f"Category seed complete: {result.created} created, {result.existing} existing")


if __name__ == "__main__":
    main()
