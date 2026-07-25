from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.database.session import get_database_session
from app.schemas.merchants import (
    MerchantAliasCreateRequest,
    MerchantAliasItem,
    MerchantCreateRequest,
    MerchantItem,
    MerchantListResponse,
    MerchantMergeRequest,
)
from app.services.merchant_service import (
    MerchantConflictError,
    MerchantNotFoundError,
    add_merchant_alias,
    create_merchant,
    delete_merchant_alias,
    list_merchants,
    merge_merchants,
)

router = APIRouter(prefix="/merchants", tags=["merchants"])
DatabaseSession = Annotated[Session, Depends(get_database_session)]


def _merchant_item(merchant) -> MerchantItem:
    return MerchantItem(
        id=merchant.id,
        name=merchant.name,
        aliases=[
            MerchantAliasItem(id=alias.id, pattern=alias.pattern) for alias in merchant.aliases
        ],
    )


@router.get("", response_model=MerchantListResponse)
async def get_merchants(session: DatabaseSession) -> MerchantListResponse:
    return MerchantListResponse(
        items=[_merchant_item(merchant) for merchant in list_merchants(session)]
    )


@router.post("", response_model=MerchantItem, status_code=status.HTTP_201_CREATED)
async def post_merchant(
    request: MerchantCreateRequest,
    session: DatabaseSession,
) -> MerchantItem:
    try:
        merchant = create_merchant(session, name=request.name, aliases=request.aliases)
    except MerchantConflictError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
    return _merchant_item(merchant)


@router.post(
    "/{merchant_id}/aliases",
    response_model=MerchantAliasItem,
    status_code=status.HTTP_201_CREATED,
)
async def post_merchant_alias(
    merchant_id: int,
    request: MerchantAliasCreateRequest,
    session: DatabaseSession,
) -> MerchantAliasItem:
    try:
        alias = add_merchant_alias(session, merchant_id=merchant_id, pattern=request.pattern)
    except MerchantNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except MerchantConflictError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
    return MerchantAliasItem(id=alias.id, pattern=alias.pattern)


@router.delete("/{merchant_id}/aliases/{alias_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_merchant_alias(
    merchant_id: int,
    alias_id: int,
    session: DatabaseSession,
) -> Response:
    try:
        delete_merchant_alias(session, merchant_id=merchant_id, alias_id=alias_id)
    except MerchantNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{target_merchant_id}/merge", response_model=MerchantItem)
async def post_merchant_merge(
    target_merchant_id: int,
    request: MerchantMergeRequest,
    session: DatabaseSession,
) -> MerchantItem:
    try:
        merchant = merge_merchants(
            session,
            target_merchant_id=target_merchant_id,
            source_merchant_id=request.source_merchant_id,
        )
    except MerchantNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except MerchantConflictError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
    return _merchant_item(merchant)
