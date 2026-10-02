"""Retrieval-progress endpoints. Analytics endpoints start the retrieval themselves;
these let the UI poll progress, lift the safety cap, or force an update."""
from fastapi import APIRouter, Depends

from routers._common import common_filters
from services.datasets import Filters, manager

router = APIRouter()


@router.get("/status")
async def dataset_status(f: Filters = Depends(common_filters)):
    return manager.status(f)


@router.post("/continue")
async def dataset_continue(f: Filters = Depends(common_filters)):
    """Retrieve beyond the safety cap (user opted in)."""
    return await manager.lift_cap(f)


@router.post("/refresh")
async def dataset_refresh(f: Filters = Depends(common_filters)):
    """Fetch records changed since the last retrieval and merge them by NCT ID."""
    return await manager.refresh(f)
