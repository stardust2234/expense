from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, declared_attr, mapped_column


class WorkspaceOwned:
    """Required ownership for data that must never cross workspace boundaries."""

    @declared_attr
    def workspace_id(cls) -> Mapped[int]:
        return mapped_column(
            ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
