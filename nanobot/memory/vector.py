"""
Vector store for semantic memory search in GigaBot.

Provides:
- Embedding generation (via LiteLLM or local)
- Vector storage (SQLite + sqlite-vec or in-memory)
- Semantic similarity search
"""

import json
import hashlib
from pathlib import Path
from typing import Any
from dataclasses import dataclass, field

import numpy as np

from nanobot.memory.store import MemoryEntry


@dataclass
class SearchResult:
    """Result from vector search."""
    entry: MemoryEntry
    score: float  # Similarity score (0.0 to 1.0)
    distance: float  # Raw distance


class VectorStore:
    """
    Vector store for semantic memory search.
    
    Storage options:
    - In-memory (default): Fast, no persistence
    - SQLite + sqlite-vec: Persistent, scalable
    - JSON file: Simple persistence
    """
    
    def __init__(
        self,
        dimension: int = 384,  # Default for all-MiniLM-L6-v2
        storage_path: Path | None = None,
        use_sqlite: bool = False,
    ):
        self.dimension = dimension
        self.storage_path = storage_path
        self.use_sqlite = use_sqlite
        
        # In-memory storage
        self._vectors: dict[str, np.ndarray] = {}
        self._entries: dict[str, MemoryEntry] = {}
        
        # Embedding cache
        self._embedding_cache: dict[str, np.ndarray] = {}
        
        # SQLite connection (if enabled)
        self._conn = None
        
        if storage_path:
            self._load_from_storage()
    
    def add(self, entry: MemoryEntry, embedding: np.ndarray | None = None) -> None:
        """
        Add an entry to the vector store.
        
        Args:
            entry: The memory entry to add.
            embedding: Pre-computed embedding, or None to generate.
        """
        if embedding is None:
            embedding = self.get_embedding(entry.content)
        
        self._vectors[entry.id] = embedding
        self._entries[entry.id] = entry
    
    def add_batch(
        self, 
        entries: list[MemoryEntry], 
        embeddings: list[np.ndarray] | None = None
    ) -> None:
        """Add multiple entries at once."""
        if embeddings is None:
            embeddings = [self.get_embedding(e.content) for e in entries]
        
        for entry, embedding in zip(entries, embeddings):
            self.add(entry, embedding)
    
    def search(
        self, 
        query: str, 
        k: int = 5,
        threshold: float = 0.0,
    ) -> list[SearchResult]:
        """
        Search for similar entries.
        
        Args:
            query: Search query text.
            k: Number of results to return.
            threshold: Minimum similarity score (0.0 to 1.0).
        
        Returns:
            List of SearchResults sorted by similarity.
        """
        if not self._vectors:
            return []
        
        query_embedding = self.get_embedding(query)
        
        results = []
        for entry_id, vector in self._vectors.items():
            distance = self._cosine_distance(query_embedding, vector)
            score = 1.0 - distance  # Convert distance to similarity
            
            if score >= threshold:
                results.append(SearchResult(
                    entry=self._entries[entry_id],
                    score=score,
                    distance=distance,
                ))
        
        # Sort by score descending
        results.sort(key=lambda x: x.score, reverse=True)
        
        return results[:k]
    
    def get_embedding(self, text: str) -> np.ndarray:
        """
        Get embedding for text.
        
        Uses caching to avoid redundant computations.
        """
        # Check cache
        cache_key = hashlib.md5(text.encode()).hexdigest()
        if cache_key in self._embedding_cache:
            return self._embedding_cache[cache_key]
        
        # Generate embedding
        embedding = self._generate_embedding(text)
        
        # Cache it
        self._embedding_cache[cache_key] = embedding
        
        return embedding
    
    def _generate_embedding(self, text: str) -> np.ndarray:
        """
        Generate embedding using available methods.
        
        Priority:
        1. LiteLLM embedding (if API key available)
        2. Sentence-transformers (if installed)
        3. Simple TF-IDF fallback
        """
        # Try LiteLLM
        try:
            return self._embed_litellm(text)
        except Exception:
            pass
        
        # Try sentence-transformers
        try:
            return self._embed_sentence_transformers(text)
        except Exception:
            pass
        
        # Fallback to simple method
        return self._embed_simple(text)
    
    def _embed_litellm(self, text: str) -> np.ndarray:
        """Generate embedding using LiteLLM."""
        import litellm
        
        response = litellm.embedding(
            model="text-embedding-3-small",
            input=text,
        )
        
        embedding = response.data[0].embedding
        return np.array(embedding, dtype=np.float32)
    
    def _embed_sentence_transformers(self, text: str) -> np.ndarray:
        """Generate embedding using sentence-transformers."""
        from sentence_transformers import SentenceTransformer
        
        # Use cached model
        if not hasattr(self, "_st_model"):
            self._st_model = SentenceTransformer("all-MiniLM-L6-v2")
        
        embedding = self._st_model.encode(text, convert_to_numpy=True)
        return embedding.astype(np.float32)
    
    def _embed_simple(self, text: str) -> np.ndarray:
        """
        Simple embedding fallback using word hashing.
        
        Not semantically meaningful but provides basic functionality.
        """
        # Tokenize
        words = text.lower().split()
        
        # Create vector using word hashes
        vector = np.zeros(self.dimension, dtype=np.float32)
        
        for word in words:
            # Hash word to get deterministic position
            h = int(hashlib.md5(word.encode()).hexdigest(), 16)
            pos = h % self.dimension
            vector[pos] += 1.0
        
        # Normalize
        norm = np.linalg.norm(vector)
        if norm > 0:
            vector = vector / norm
        
        return vector
    
    def _cosine_distance(self, a: np.ndarray, b: np.ndarray) -> float:
        """Calculate cosine distance between two vectors."""
        dot = np.dot(a, b)
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        
        if norm_a == 0 or norm_b == 0:
            return 1.0
        
        similarity = dot / (norm_a * norm_b)
        return 1.0 - similarity
    
    def save(self) -> None:
        """Save vector store to storage."""
        if not self.storage_path:
            return
        
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Save as JSON (vectors as lists)
        data = {
            "dimension": self.dimension,
            "vectors": {
                id_: vec.tolist() 
                for id_, vec in self._vectors.items()
            },
            "entries": {
                id_: {
                    "id": entry.id,
                    "content": entry.content,
                    "source": entry.source,
                    "timestamp": entry.timestamp.isoformat(),
                    "metadata": entry.metadata,
                    "importance": entry.importance,
                    "tags": entry.tags,
                }
                for id_, entry in self._entries.items()
            },
        }
        
        with open(self.storage_path, "w") as f:
            json.dump(data, f)
    
    def _load_from_storage(self) -> None:
        """Load vector store from storage."""
        if not self.storage_path or not self.storage_path.exists():
            return
        
        try:
            with open(self.storage_path) as f:
                data = json.load(f)
            
            self.dimension = data.get("dimension", self.dimension)
            
            # Load vectors
            for id_, vec_list in data.get("vectors", {}).items():
                self._vectors[id_] = np.array(vec_list, dtype=np.float32)
            
            # Load entries
            from datetime import datetime
            for id_, entry_data in data.get("entries", {}).items():
                self._entries[id_] = MemoryEntry(
                    id=entry_data["id"],
                    content=entry_data["content"],
                    source=entry_data["source"],
                    timestamp=datetime.fromisoformat(entry_data["timestamp"]),
                    metadata=entry_data.get("metadata", {}),
                    importance=entry_data.get("importance", 0.5),
                    tags=entry_data.get("tags", []),
                )
                
        except Exception:
            pass  # Start fresh on error
    
    def clear(self) -> None:
        """Clear all vectors and entries."""
        self._vectors.clear()
        self._entries.clear()
        self._embedding_cache.clear()
    
    @property
    def size(self) -> int:
        """Number of entries in the store."""
        return len(self._vectors)
