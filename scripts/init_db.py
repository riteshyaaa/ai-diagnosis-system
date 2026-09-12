#!/usr/bin/env python3
"""
MedFusion AI — Database Initialization & Seeding Script.

Initializes database schema and seeds initial administrative users and
reference clinical records.
"""

import asyncio
import hashlib
import sys
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.database import engine as async_engine, AsyncSessionLocal
from app.models import (
    Base,
    User,
    UserRole,
    Patient,
    BiologicalSex,
    AuditLog,
    AuditAction,
    AuditResourceType,
)
from app.security.password import hash_password
from app.repositories.user_repository import UserRepository
from app.repositories.patient_repository import PatientRepository
from app.repositories.audit_log_repository import AuditLogRepository


async def init_db() -> None:
    """Initialize database tables and seed initial users."""
    print("=" * 60)
    print("MedFusion AI — Database Initialization & Seeding")
    print("=" * 60)

    print("\n1. Creating database tables if not present...")
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("   ✓ Schema tables verified and ready.")

    print("\n2. Seeding default role accounts...")
    async with AsyncSessionLocal() as session:
        user_repo = UserRepository(session)
        patient_repo = PatientRepository(session)
        audit_repo = AuditLogRepository(session)

        # Default users to seed (matches frontend demo personas)
        seed_users = [
            {
                "email": "admin@medfusion.local",
                "password": "MedFusion#2026Secure!",
                "full_name": "System Administrator",
                "role": UserRole.ADMIN,
                "department": "Informatics & Security",
            },
            {
                "email": "dr.chen@medfusion.local",
                "password": "MedFusion#2026Secure!",
                "full_name": "Dr. Sarah Chen, MD",
                "role": UserRole.CLINICIAN,
                "department": "Cardiology",
            },
            {
                "email": "dr.patel@medfusion.local",
                "password": "MedFusion#2026Secure!",
                "full_name": "Dr. Aarav Patel, MD",
                "role": UserRole.RADIOLOGIST,
                "department": "Diagnostic Radiology",
            },
            {
                "email": "dr.rodriguez@medfusion.local",
                "password": "MedFusion#2026Secure!",
                "full_name": "Dr. Carlos Rodriguez, MD",
                "role": UserRole.RADIOLOGIST,
                "department": "Diagnostic Radiology",
            },
            {
                "email": "auditor.smith@medfusion.local",
                "password": "MedFusion#2026Secure!",
                "full_name": "Eleanor Smith, CISA",
                "role": UserRole.AUDITOR,
                "department": "Clinical Compliance & Quality",
            },
        ]

        created_users = []
        for u_data in seed_users:
            existing = await user_repo.get_by_email(u_data["email"])
            if existing is None:
                user = User(
                    email=u_data["email"],
                    hashed_password=hash_password(u_data["password"]),
                    full_name=u_data["full_name"],
                    role=u_data["role"],
                    department=u_data["department"],
                    is_active=True,
                    is_verified=True,
                )
                created = await user_repo.create(user)
                created_users.append(created)
                print(f"   ✓ Created user: {u_data['email']} [{u_data['role'].value}]")

                # Log audit event
                await audit_repo.log_event(
                    action=AuditAction.USER_REGISTER,
                    resource_type=AuditResourceType.USER,
                    resource_id=str(created.id),
                    details={"email": u_data["email"], "seeded": True},
                )
            else:
                existing.hashed_password = hash_password(u_data["password"])
                existing.failed_login_attempts = 0
                existing.locked_until = None
                existing.is_active = True
                existing.is_verified = True
                await session.flush()
                print(f"   ✓ Updated password for user: {u_data['email']}")

        print("\n3. Seeding reference de-identified patient record...")
        sample_mrn = "MRN-2026-00101"
        sample_mrn_hash = hashlib.sha256(sample_mrn.encode("utf-8")).hexdigest()

        existing_patient = await patient_repo.get_by_mrn_hash(sample_mrn_hash)
        if existing_patient is None:
            patient = Patient(
                mrn_hash=sample_mrn_hash,
                age=58,
                sex=BiologicalSex.MALE,
                blood_group="O+",
                medical_history_summary="History of hypertension, hyperlipidemia, non-smoker.",
            )
            created_patient = await patient_repo.create(patient)
            print(f"   ✓ Created reference patient with SHA-256 MRN hash: {sample_mrn_hash[:12]}...")

            await audit_repo.log_event(
                action=AuditAction.PATIENT_CREATE,
                resource_type=AuditResourceType.PATIENT,
                resource_id=str(created_patient.id),
                details={"age": 58, "sex": "male", "seeded": True},
            )
        else:
            print(f"   • Reference patient already exists: {sample_mrn_hash[:12]}...")

        await session.commit()

    print("\nDatabase initialization and seeding completed successfully!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(init_db())
