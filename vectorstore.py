import os
import faiss
import numpy as np
import pickle
from typing import List, Dict, Tuple
from sentence_transformers import SentenceTransformer

class VectorStore:
    def __init__(self, model_name: str, index_dir: str = "data/index"):
        self.model_name = model_name
        self.index_dir = index_dir
        os.makedirs(index_dir, exist_ok=True)
        self.model = SentenceTransformer(model_name)
        self.dim = self.model.get_sentence_embedding_dimension()
        self.index = None
        self.meta: List[Dict] = []

    def _paths(self):
        return (os.path.join(self.index_dir, "faiss.index"),
                os.path.join(self.index_dir, "meta.pkl"))

    def build(self, docs: List[str], metadatas: List[Dict]):
        embs = self.model.encode(docs, show_progress_bar=True, convert_to_numpy=True, normalize_embeddings=True)
        self.index = faiss.IndexFlatIP(self.dim)  # cosine via normalized vectors
        self.index.add(embs)
        self.meta = metadatas

    def save(self):
        ipath, mpath = self._paths()
        faiss.write_index(self.index, ipath)
        with open(mpath, "wb") as f:
            pickle.dump({"meta": self.meta, "model": self.model_name}, f)

    def load(self):
        ipath, mpath = self._paths()
        self.index = faiss.read_index(ipath)
        with open(mpath, "rb") as f:
            d = pickle.load(f)
            self.meta = d["meta"]
            assert d["model"] == self.model_name

    def is_built(self) -> bool:
        ipath, mpath = self._paths()
        return os.path.exists(ipath) and os.path.exists(mpath)

    def search(self, query: str, docs: List[str], k: int = 6) -> List[Tuple[str, Dict, float]]:
        q = self.model.encode([query], convert_to_numpy=True, normalize_embeddings=True)
        sims, idxs = self.index.search(q, k)
        out = []
        for i, score in zip(idxs[0], sims[0]):
            out.append((docs[i], self.meta[i], float(score)))
        return out
