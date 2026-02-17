from pydantic import BaseModel


class ImportResult(BaseModel):
    total: int
    created: int
    skipped: int
    failed: int
    errors: list[str] = []
