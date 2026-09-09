"""
MedFusion AI — Chest X-ray Dataset Module.

Handles NIH ChestX-ray14 dataset:
  - Download / directory structure validation
  - Multi-label parsing from Data_Entry CSV
  - Train / val / test splitting (patient-level to prevent leakage)
  - Albumentations augmentation pipeline
  - PyTorch Dataset and DataLoader construction
"""
