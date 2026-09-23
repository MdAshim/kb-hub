import numpy as np
import pytest
from django.conf import settings

from knowledge.embedder import Embedder


@pytest.mark.slow
def test_real_embedder_produces_normalized_vectors_of_the_configured_dim():
    embedder = Embedder()

    doc_vectors = embedder.embed_documents(["Jane Smith is the CEO.", "John Doe is the CFO."])
    assert doc_vectors.shape == (2, settings.EMBEDDING_DIM)
    assert doc_vectors.dtype == np.float32
    assert np.allclose(np.linalg.norm(doc_vectors, axis=1), 1.0, atol=1e-3)

    query_vector = embedder.embed_query("Who is the CEO?")
    assert query_vector.shape == (settings.EMBEDDING_DIM,)
    assert abs(float(np.linalg.norm(query_vector)) - 1.0) < 1e-3
