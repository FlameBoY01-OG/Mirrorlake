from fastapi import APIRouter
from pydantic import BaseModel

from services import trino_service

router = APIRouter()


class QueryRequest(BaseModel):
    sql: str


@router.post("/query")
def run_query(req: QueryRequest):
    """Run arbitrary SQL on Trino (iceberg.shop, 30s cap)."""
    return trino_service.run_query(req.sql)
