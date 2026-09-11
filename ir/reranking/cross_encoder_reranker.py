"""
Real cross-encoder reranker using sentence-transformers' CrossEncoder.
REQUIRES internet access (or a pre-populated local HF cache) to download
`cross-encoder/ms-marco-MiniLM-L-6-v2` on first use. See ir/reranking/base.py.
"""
from .base import Reranker

DEFAULT_MODEL_NAME = "cross-encoder/ms-marco-MiniLM-L-6-v2"


class CrossEncoderReranker(Reranker):
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
            from sentence_transformers import CrossEncoder
        except ImportError as e:
            raise RuntimeError(
                "sentence-transformers is not installed. Run: pip install sentence-transformers"
            ) from e
        try:
            self._model = CrossEncoder(self.model_name)
        except Exception as e:
            raise RuntimeError(
                f"Could not load cross-encoder model '{self.model_name}'. Requires internet "
                "access to huggingface.co on first use (or a pre-populated local HF cache). "
                "In a sandboxed environment without internet access, use TfidfRerankerFallback "
                "instead (ir/reranking/tfidf_reranker.py, set via ir/reranking/config.py)."
            ) from e

    def rerank(self, query: str, candidates: list[tuple[int, str]]) -> list[tuple[int, float]]:
        if not candidates:
            return []
        self._load_model()

        chunk_ids = [cid for cid, _ in candidates]
        texts = [text for _, text in candidates]

        pairs = [[query, text] for text in texts]
        scores = self._model.predict(pairs)

        scored = list(zip(chunk_ids, [float(s) for s in scores]))
        return sorted(scored, key=lambda x: x[1], reverse=True)
