"""
Single switch controlling which reranker implementation is used. Change to
"cross_encoder" once running with internet access -- see
ir/reranking/cross_encoder_reranker.py.
"""

RERANKER_TYPE = "tfidf_fallback"  # "tfidf_fallback" | "cross_encoder"


def get_reranker():
    if RERANKER_TYPE == "tfidf_fallback":
        from .tfidf_reranker import TfidfRerankerFallback
        return TfidfRerankerFallback()
    elif RERANKER_TYPE == "cross_encoder":
        from .cross_encoder_reranker import CrossEncoderReranker
        return CrossEncoderReranker()
    else:
        raise ValueError(f"Unknown RERANKER_TYPE: {RERANKER_TYPE}")
