from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.database.session import get_database_session
from app.models import SpendingPriority
from app.schemas.categories import CategoryItem, CategoryListResponse, CategoryWriteRequest
from app.services.category_service import (
    CategoryConflictError,
    CategoryNotFoundError,
    create_category,
    delete_category,
    list_categories,
    update_category,
)

router = APIRouter(tags=["categories"])
DatabaseSession = Annotated[Session, Depends(get_database_session)]


@router.get("/categories", response_model=CategoryListResponse)
async def get_categories(session: DatabaseSession) -> CategoryListResponse:
    categories = list_categories(session)
    return CategoryListResponse(
        items=[
            CategoryItem(
                id=category.id,
                name=category.name,
                parent_category_id=category.parent_category_id,
                default_priority=category.default_priority,
            )
            for category in categories
        ]
    )


@router.post(
    "/categories",
    response_model=CategoryItem,
    status_code=status.HTTP_201_CREATED,
)
async def post_category(
    request: CategoryWriteRequest,
    session: DatabaseSession,
) -> CategoryItem:
    if request.name is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="name is required",
        )
    try:
        category = create_category(
            session,
            name=request.name,
            parent_category_id=request.parent_category_id,
            default_priority=request.default_priority or SpendingPriority.ADJUSTABLE,
        )
    except CategoryConflictError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
    return CategoryItem.model_validate(category, from_attributes=True)


@router.patch("/categories/{category_id}", response_model=CategoryItem)
async def patch_category(
    category_id: int,
    request: CategoryWriteRequest,
    session: DatabaseSession,
) -> CategoryItem:
    try:
        category = update_category(
            session,
            category_id=category_id,
            name=request.name,
            parent_category_id=request.parent_category_id,
            parent_supplied="parent_category_id" in request.model_fields_set,
            default_priority=request.default_priority,
        )
    except CategoryNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except CategoryConflictError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
    return CategoryItem.model_validate(category, from_attributes=True)


@router.delete("/categories/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_category(category_id: int, session: DatabaseSession) -> Response:
    try:
        delete_category(session, category_id=category_id)
    except CategoryNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except CategoryConflictError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
    return Response(status_code=status.HTTP_204_NO_CONTENT)
