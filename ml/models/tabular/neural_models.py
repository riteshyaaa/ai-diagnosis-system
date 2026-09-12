"""
MedFusion AI — PyTorch Neural Network for Tabular Clinical Risk Prediction.

Implements deep tabular architecture with residual layers, embedding extraction for multimodal fusion,
and temperature-scaled calibrated risk probability estimation.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, Union
import numpy as np
import torch
import torch.nn as nn


class TabularRiskMLP(nn.Module):
    """
    Deep Tabular Multi-Layer Perceptron with Residual Feed-Forward Blocks.
    Extracts high-order non-linear clinical representations and outputs calibrated risk probabilities.
    """

    def __init__(
        self,
        input_dim: int = 13,
        embedding_dim: int = 128,
        hidden_dim: int = 128,
        dropout_rate: float = 0.2,
        num_features: Optional[int] = None,
        hidden_dims: Optional[List[int]] = None,
    ):
        super().__init__()
        actual_input_dim = num_features if num_features is not None else input_dim
        actual_hidden_dim = hidden_dims[0] if (hidden_dims is not None and len(hidden_dims) > 0) else hidden_dim

        self.input_dim = actual_input_dim
        self.num_features = actual_input_dim
        self.embedding_dim = embedding_dim
        self.hidden_dim = actual_hidden_dim

        # Input projection
        self.input_layer = nn.Sequential(
            nn.Linear(self.input_dim, self.hidden_dim),
            nn.BatchNorm1d(self.hidden_dim),
            nn.LeakyReLU(0.1, inplace=True),
            nn.Dropout(dropout_rate),
        )

        # Residual processing block
        self.res_block = nn.Sequential(
            nn.Linear(self.hidden_dim, self.hidden_dim),
            nn.BatchNorm1d(self.hidden_dim),
            nn.LeakyReLU(0.1, inplace=True),
            nn.Dropout(dropout_rate),
            nn.Linear(self.hidden_dim, self.hidden_dim),
            nn.BatchNorm1d(self.hidden_dim),
        )
        self.res_act = nn.LeakyReLU(0.1, inplace=True)

        # Embedding projection head (for multimodal fusion)
        self.embedding_head = nn.Sequential(
            nn.Linear(self.hidden_dim, embedding_dim),
            nn.BatchNorm1d(embedding_dim),
            nn.LeakyReLU(0.1, inplace=True),
        )

        # Binary diagnostic risk classifier
        self.classifier = nn.Linear(embedding_dim, 1)

        # Temperature parameter for calibrated logits
        self.temperature = nn.Parameter(torch.ones(1))

    def freeze(self, freeze: bool = True) -> None:
        """Freeze or unfreeze parameters."""
        for param in self.parameters():
            param.requires_grad = not freeze

    def extract_features(self, x: torch.Tensor) -> torch.Tensor:
        """Extract dense clinical embedding vector [batch_size, embedding_dim]."""
        h = self.input_layer(x)
        res = self.res_block(h)
        h = self.res_act(h + res)
        embeddings = self.embedding_head(h)
        return embeddings

    def forward(
        self,
        x: torch.Tensor,
        return_embeddings: bool = False,
    ) -> Dict[str, torch.Tensor]:
        """
        Forward pass.
        Args:
            x: Input tabular tensor [batch_size, input_dim]
            return_embeddings: Whether to return extracted clinical embeddings
        Returns:
            Dictionary containing 'logits', 'scaled_logits', and 'probabilities'
        """
        embeddings = self.extract_features(x)
        logits = self.classifier(embeddings)

        temp = torch.clamp(self.temperature, min=0.01)
        scaled_logits = logits / temp
        probabilities = torch.sigmoid(scaled_logits)

        out = {
            "logits": logits,
            "scaled_logits": scaled_logits,
            "probabilities": probabilities,
        }
        if return_embeddings:
            out["embeddings"] = embeddings

        return out

    def predict_proba(self, x: Union[torch.Tensor, np.ndarray]) -> np.ndarray:
        """Generate predicted disease probabilities as 1D NumPy array."""
        self.eval()
        if isinstance(x, np.ndarray):
            x = torch.from_numpy(x.astype(np.float32))

        with torch.no_grad():
            out = self.forward(x)
            probs = out["probabilities"].cpu().numpy().ravel()
        return probs

    def predict(self, x: Union[torch.Tensor, np.ndarray], threshold: float = 0.5) -> np.ndarray:
        """Generate binary risk predictions (0 or 1)."""
        probs = self.predict_proba(x)
        return (probs >= threshold).astype(int)

    def save_checkpoint(self, path: Union[str, Path]) -> None:
        """Save model weights and architecture settings."""
        dest = Path(path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        torch.save(
            {
                "state_dict": self.state_dict(),
                "input_dim": self.input_dim,
                "embedding_dim": self.embedding_dim,
                "hidden_dim": self.hidden_dim,
            },
            dest,
        )

    @classmethod
    def load_checkpoint(
        cls,
        path: Union[str, Path],
        map_location: Optional[str] = "cpu",
    ) -> "TabularRiskMLP":
        """Load model from saved checkpoint."""
        ckpt = torch.load(path, map_location=map_location, weights_only=True)
        model = cls(
            input_dim=ckpt["input_dim"],
            embedding_dim=ckpt["embedding_dim"],
            hidden_dim=ckpt["hidden_dim"],
        )
        model.load_state_dict(ckpt["state_dict"])
        return model
