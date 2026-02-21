import faiss
import numpy as np
import pickle
import os
from sentence_transformers import SentenceTransformer
from typing import List, Dict, Any

class LegalResearchEngine:
    def __init__(self, model_name: str = 'sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2'):
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        self.model_dir = os.path.join(self.base_dir, "models", "law_index")
        self.index_path = os.path.join(self.model_dir, "law.index")
        self.metadata_path = os.path.join(self.model_dir, "law_metadata.pkl")
        
        # Load Model
        # Reuse existing model instance if possible or load new
        print(f"Loading Legal Research Model: {model_name}...")
        self.model = SentenceTransformer(model_name)
        
        # Load Index & Metadata
        if os.path.exists(self.index_path) and os.path.exists(self.metadata_path):
            try:
                self.index = faiss.read_index(self.index_path)
                with open(self.metadata_path, 'rb') as f:
                    self.metadata = pickle.load(f)
                print(f" Legal Research Engine loaded. {len(self.metadata)} articles indexed.")
            except Exception as e:
                print(f" Error loading Legal Research Engine: {e}")
                self.index = None
                self.metadata = []
        else:
            print(f"Warning: Legal Research Engine index not found at {self.model_dir}")
            self.index = None
            self.metadata = []

    def search(self, query: str, top_k: int = 3) -> List[Dict[str, Any]]:
        """
        Search for relevant legal articles.
        Returns a list of dictionaries containing the article and similarity score.
        """
        if not self.index or not self.metadata:
            return []
            
        # Encode query
        embedding = self.model.encode([query], convert_to_numpy=True)
        
        # Search index
        distances, indices = self.index.search(embedding, top_k)
        
        results = []
        for i, idx in enumerate(indices[0]):
            if idx != -1 and idx < len(self.metadata):
                article = self.metadata[idx]
                distance = float(distances[0][i])
                
                # Convert L2 distance to a 0-100 confidence score
                # 0 distance = 100% match. typical distances for this model are 0-15.
                # similarity = exp(-distance^2 / 2sigma^2)
                sigma = 10 
                similarity = np.exp(-(distance ** 2) / (2 * sigma ** 2))
                confidence = round(similarity * 100, 2)
                
                results.append({
                    "article": article,
                    "score": confidence,
                    "distance": distance
                })
        
        # Sort by score descending
        results.sort(key=lambda x: x['score'], reverse=True)
        return results

if __name__ == "__main__":
    # Test
    engine = LegalResearchEngine()
    q = "الفصل التعسفي في العقد غير محدد المدة"
    results = engine.search(q)
    print(f"Query: {q}")
    for res in results:
        print(f"[{res['score']}%] Article {res['article']['article_number']}: {res['article']['text_ar'][:50]}...")
