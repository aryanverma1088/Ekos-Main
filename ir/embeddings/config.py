"""
Single switch controlling which dense encoder implementation is used
throughout the project (scripts/build_dense_index.py, evaluation/*, the
/search API). Change ENCODER_TYPE to "sentence_transformer" once running
with internet access -- see ir/embeddings/st_encoder.py for details.
"""

ENCODER_TYPE = "lsa"  # "lsa" | "sentence_transformer"


def get_encoder():
    if ENCODER_TYPE == "lsa":
        from .lsa_encoder import LSAEncoder
        return LSAEncoder()
    elif ENCODER_TYPE == "sentence_transformer":
        from .st_encoder import SentenceTransformerEncoder
        return SentenceTransformerEncoder()
    else:
        raise ValueError(f"Unknown ENCODER_TYPE: {ENCODER_TYPE}")
