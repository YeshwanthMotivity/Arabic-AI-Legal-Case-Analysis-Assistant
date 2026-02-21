import faiss
import numpy as np
import os
from sentence_transformers import SentenceTransformer
from typing import List, Tuple
from models import Case

class SimilarityEngine:
    def __init__(self, model_name: str = 'sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2'):
        # Check for local model first
        local_path = os.path.join(os.path.dirname(__file__), "models", "similarity_model")
        if os.path.exists(local_path):
            print(f"Loading local embedding model from {local_path}...")
            self.model = SentenceTransformer(local_path)
        else:
            print(f"Loading embedding model: {model_name}...")
            self.model = SentenceTransformer(model_name)
            
        self.index = None
        self.cases: List[Case] = []
        self.embeddings = None
        
    def build_index(self, cases: List[Case]):
        """
        Build FAISS index from a list of cases.
        Uses the 'facts' field for embedding generation as it contains the core case details.
        """
        self.cases = cases
        if not cases:
            print("No cases to index.")
            return

        print(f"Generating embeddings for {len(cases)} cases...")
        # Extract facts for embedding
        texts = [case.facts for case in cases]
        
        # Generate embeddings
        self.embeddings = self.model.encode(texts, convert_to_numpy=True)
        
        # Initialize FAISS index
        dimension = self.embeddings.shape[1]
        self.index = faiss.IndexFlatL2(dimension)
        self.index.add(self.embeddings)
        print(f"Index built with {self.index.ntotal} vectors.")

    def search(self, query_text: str, top_k: int = 3) -> List[Tuple[Case, float]]:
        """
        Search for similar cases.
        Returns a list of (Case, distance) tuples. 
        Note: FAISS L2 distance: lower is better/closer.
        """
        if self.index is None:
            raise ValueError("Index not built. Call build_index first.")
            
        query_embedding = self.model.encode([query_text], convert_to_numpy=True)
        distances, indices = self.index.search(query_embedding, top_k)
        
        results = []
        for i, idx in enumerate(indices[0]):
            if idx != -1 and idx < len(self.cases):
                results.append((self.cases[idx], float(distances[0][i])))
                
        return results

if __name__ == "__main__":
    # Test script
    from data_loader import load_cases
    
    engine = SimilarityEngine()
    cases = load_cases(filter_real_only=True) # Use only real cases for index as per recommendation
    engine.build_index(cases)
    
    if cases:
        test_query = cases[0].facts[:200]
        results = engine.search(test_query)
        print("Search Results:")
        for case, score in results:
            print(f"- {case.case_id} (Score: {score:.4f})")
