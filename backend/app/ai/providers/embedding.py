import httpx
from app.core.config import settings


class EmbeddingError(RuntimeError):
    pass


class OpenAIEmbeddings:
    def embed(self, texts: list[str], timeout_seconds: int = 60) -> list[list[float]]:
        if not settings.openai_api_key:
            raise EmbeddingError("OPENAI_API_KEY is required for document embeddings")
        response = httpx.post("https://api.openai.com/v1/embeddings",
            headers={"Authorization": f"Bearer {settings.openai_api_key}"},
            json={"model": settings.embedding_model, "input": texts, "dimensions": 1536}, timeout=timeout_seconds)
        response.raise_for_status()
        return [row["embedding"] for row in sorted(response.json()["data"], key=lambda row: row["index"])]


class MockEmbeddings:
    """Deterministic test-only vectors; never displayed as a real AI run."""
    def embed(self, texts: list[str]) -> list[list[float]]:
        import hashlib
        result = []
        for text in texts:
            vector = [0.0] * 1536
            for token in text.lower().split():
                index = int.from_bytes(hashlib.sha256(token.encode()).digest()[:4], "big") % 1536
                vector[index] += 1.0
            result.append(vector)
        return result


def embedding_provider():
    if settings.embedding_provider == "openai":
        return OpenAIEmbeddings()
    if settings.embedding_provider == 'ollama':
        from app.ai.providers.ollama import OllamaEmbeddings
        return OllamaEmbeddings()
    if settings.embedding_provider == "mock":
        return MockEmbeddings()
    raise EmbeddingError("Unsupported embedding provider")
