"""
Real semantic dense encoder using sentence-transformers.

REQUIRES either internet access (to download the model from huggingface.co
on first use) or a pre-populated local HF cache (~/.cache/huggingface).
This will raise a clear RuntimeError if the model can't be loaded, rather
than failing with an opaque huggingface_hub stack trace.

To use this instead of the LSA fallback, set ENCODER_TYPE = "sentence_transformer"
in ir/embeddings/config.py, then re-run:
    python scripts/build_dense_index.py --reset

No other code needs to change -- DenseIndex, hybrid fusion, and the
evaluation scripts all depend only on the Encoder interface (ir/embeddings/base.py).
"""
import numpy as np

from .base import Encoder

DEFAULT_MODEL_NAME = "all-MiniLM-L6-v2"


class SentenceTransformerEncoder(Encoder):
    def __init__(self, model_name: str = DEFAULT_MODEL_NAME):
        self.model_name = model_name
        self._model = None

    @property
    def name(self) -> str:
        return self.model_name

    def _load_model(self):
        if self._model is not None:
            return
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as e:
            raise RuntimeError(
                "sentence-transformers is not installed. Run: pip install sentence-transformers"
            ) from e

        try:
            self._model = SentenceTransformer(self.model_name)
        except Exception as e:
            raise RuntimeError(
                f"Could not load sentence-transformers model '{self.model_name}'. "
                "This requires internet access to huggingface.co on first use "
                "(or a pre-populated local HF cache). If you're in a sandboxed "
                "environment without internet access, use LSAEncoder instead "
                "(ir/embeddings/lsa_encoder.py, set via ir/embeddings/config.py)."
            ) from e

    def fit(self, corpus_texts: list[str]) -> None:
        # Pretrained model: nothing to fit. Still load it here so fit() always
        # surfaces a network error early (at index-build time) rather than
        # deferring the failure to the first encode() call.
        self._load_model()

    def encode(self, texts: list[str]) -> np.ndarray:
        self._load_model()
        vectors = self._model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
        return np.asarray(vectors, dtype=np.float32)

    def save(self, path: str) -> None:
        # Nothing to persist beyond the model name -- the pretrained weights
        # live in the HF cache, not in our data/processed/ directory.
        with open(path, "w") as f:
            f.write(self.model_name)

    def load(self, path: str) -> None:
        with open(path) as f:
            self.model_name = f.read().strip()
