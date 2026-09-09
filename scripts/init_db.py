#!/usr/bin/env python3
"""
MedFusion AI — Database Initialization Script.

Creates tables via SQLAlchemy metadata or runs Alembic migrations.
Can seed default admin user and sample reference data.
"""

import sys
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(backend_dir))


def main():
    print("MedFusion AI — Database Initialization")
    print("=" * 45)
    print("This script will be expanded in Phase 3 (Database Schema & Migrations).")
    print("Alembic migrations will create the database schema.")


if __name__ == "__main__":
    main()
