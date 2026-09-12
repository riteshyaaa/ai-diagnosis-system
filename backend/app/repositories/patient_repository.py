"""
MedFusion AI — Patient Repository.

Encapsulates database operations on the de-identified Patient entity:
- Lookups by hashed MRN (SHA-256)
- Demographic filtering and pagination
- Eager retrieval of diagnostic case history
"""

from typing import List, Optional
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.patient import Patient, BiologicalSex
from app.repositories.base import BaseRepository


class PatientRepository(BaseRepository[Patient]):
    """Patient repository managing de-identified patient records."""

    def __init__(self, session: AsyncSession):
        super().__init__(Patient, session)

    async def get_by_mrn_hash(self, mrn_hash: str) -> Optional[Patient]:
        """Fetch a patient record by unique 64-character MRN hash."""
        stmt = select(Patient).where(Patient.mrn_hash == mrn_hash)
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_with_cases(self, patient_id: UUID) -> Optional[Patient]:
        """Fetch patient by ID with eager loading of all diagnostic cases."""
        stmt = (
            select(Patient)
            .where(Patient.id == patient_id)
            .options(selectinload(Patient.cases))
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def filter_patients(
        self,
        sex: Optional[BiologicalSex] = None,
        min_age: Optional[int] = None,
        max_age: Optional[int] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> List[Patient]:
        """Filter patients by demographic attributes with pagination."""
        stmt = select(Patient)
        if sex is not None:
            stmt = stmt.where(Patient.sex == sex)
        if min_age is not None:
            stmt = stmt.where(Patient.age >= min_age)
        if max_age is not None:
            stmt = stmt.where(Patient.age <= max_age)

        stmt = stmt.order_by(Patient.created_at.desc()).offset(skip).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
