from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.database.session import get_database_session
from app.models import CategorisationRule
from app.schemas.rules import RuleItem, RuleListResponse, RuleUpdateRequest
from app.services.rule_service import (
    RuleConflictError,
    RuleNotFoundError,
    delete_rule,
    list_rules,
    update_rule,
)

router = APIRouter(prefix="/rules", tags=["rules"])
DatabaseSession = Annotated[Session, Depends(get_database_session)]


def _item(rule: CategorisationRule, match_count: int) -> RuleItem:
    return RuleItem(
        id=rule.id,
        match_pattern=rule.match_pattern,
        category_id=rule.category_id,
        category_name=rule.category.name,
        priority=rule.priority,
        enabled=rule.enabled,
        match_count=match_count,
    )


@router.get("", response_model=RuleListResponse)
async def get_rules(session: DatabaseSession) -> RuleListResponse:
    return RuleListResponse(items=[_item(rule, count) for rule, count in list_rules(session)])


@router.patch("/{rule_id}", response_model=RuleItem)
async def patch_rule(
    rule_id: int,
    request: RuleUpdateRequest,
    session: DatabaseSession,
) -> RuleItem:
    try:
        rule = update_rule(
            session,
            rule_id=rule_id,
            match_pattern=request.match_pattern,
            category_id=request.category_id,
            priority=request.priority,
            enabled=request.enabled,
        )
    except RuleNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except RuleConflictError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
    match_count = len(rule.matched_expenses)
    return _item(rule, match_count)


@router.delete("/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_rule(rule_id: int, session: DatabaseSession) -> Response:
    try:
        delete_rule(session, rule_id=rule_id)
    except RuleNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    return Response(status_code=status.HTTP_204_NO_CONTENT)
