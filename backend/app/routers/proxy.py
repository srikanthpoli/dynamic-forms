from fastapi import APIRouter

router = APIRouter(prefix="/api/proxy", tags=["proxy"])


@router.get("/lookup")
def external_data_lookup(q: str):
    mock_database = ["Canada", "United States", "United Kingdom", "Germany", "France"]
    return [item for item in mock_database if q.lower() in item.lower()]
