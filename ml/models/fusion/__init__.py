"""
MedFusion AI — Fusion Model Module.

Late-fusion multimodal architecture that combines:
  - Image embeddings (from frozen DenseNet-121 / EfficientNet-B0)
  - Clinical embeddings (from frozen tabular encoder)
into a shared representation via MLP for joint prediction.
"""
