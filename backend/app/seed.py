from sqlalchemy import select

from app.database.session import SessionLocal
from app.models import Workspace
from app.services.category_seed_service import seed_categories


def main() -> None:
    with SessionLocal() as session:
        workspace = session.scalar(
            select(Workspace).where(Workspace.is_claimed.is_(False)).order_by(Workspace.id)
        )
        if workspace is None:
            print("Category seed skipped: no unclaimed initial workspace")
            return
        session.info["workspace_id"] = workspace.id
        result = seed_categories(session)
    print(f"Category seed complete: {result.created} created, {result.existing} existing")


if __name__ == "__main__":
    main()
