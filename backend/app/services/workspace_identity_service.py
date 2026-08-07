from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.models import User, Workspace
from app.services.auth0_service import Auth0Identity
from app.services.category_seed_service import seed_categories


class WorkspaceIdentityConflict(ValueError):
    pass


def resolve_workspace_owner(session: Session, identity: Auth0Identity) -> User:
    user = session.scalar(
        select(User)
        .where(User.auth0_subject == identity.subject)
        .options(selectinload(User.workspace))
    )
    if user is not None:
        session.info["workspace_id"] = user.workspace.id if user.workspace else None
        return user

    try:
        user = session.scalar(
            select(User).where(User.email == identity.email).options(selectinload(User.workspace))
        )
        if user is not None:
            if user.auth0_subject not in {None, identity.subject}:
                raise WorkspaceIdentityConflict("Email is already linked to another Auth0 identity")
            user.auth0_subject = identity.subject
            user.display_name = identity.display_name
        else:
            user = User(
                auth0_subject=identity.subject,
                email=identity.email,
                display_name=identity.display_name,
            )
            session.add(user)
            session.flush()
            legacy_workspace_id = session.scalar(
                select(Workspace.id)
                .where(Workspace.is_claimed.is_(False))
                .order_by(Workspace.id)
                .limit(1)
            )
            claimed_workspace = False
            if legacy_workspace_id is not None:
                claim = session.execute(
                    update(Workspace)
                    .where(
                        Workspace.id == legacy_workspace_id,
                        Workspace.owner_user_id.is_(None),
                        Workspace.is_claimed.is_(False),
                    )
                    .values(
                        owner_user_id=user.id,
                        is_claimed=True,
                        name=f"{identity.display_name}'s workspace",
                        trial_ends_at=datetime.now(UTC) + timedelta(days=30),
                    )
                )
                claimed_workspace = claim.rowcount == 1
            if not claimed_workspace:
                workspace = Workspace(
                    name=f"{identity.display_name}'s workspace", is_claimed=True, owner=user
                )
                session.add(workspace)
            else:
                session.expire(user, ["workspace"])
                workspace = user.workspace
                if workspace is None:
                    raise WorkspaceIdentityConflict("Legacy workspace claim failed")
            session.flush()
            session.info["workspace_id"] = workspace.id
            seed_categories(session, commit=False)
        if user.workspace is None:
            raise WorkspaceIdentityConflict("Auth0 identity has no workspace")
        session.info["workspace_id"] = user.workspace.id
        session.commit()
        return user
    except IntegrityError as error:
        session.rollback()
        raise WorkspaceIdentityConflict("Auth0 identity could not be linked") from error
