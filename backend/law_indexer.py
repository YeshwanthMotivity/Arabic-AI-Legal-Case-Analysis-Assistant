import json
import os
import faiss
import numpy as np
import pickle
from sentence_transformers import SentenceTransformer
from typing import List, Dict

# Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "..", "data", "laws")
OUTPUT_DIR = os.path.join(BASE_DIR, "models", "law_index")
LABOR_LAW_PATH = os.path.join(DATA_DIR, "labor_law.json")

# Model
MODEL_NAME = 'sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2'

def load_laws() -> List[Dict]:
    """Load law data from JSON files."""
    laws = []
    if os.path.exists(LABOR_LAW_PATH):
        print(f"Loading {LABOR_LAW_PATH}...")
        with open(LABOR_LAW_PATH, 'r', encoding='utf-8') as f:
            laws.extend(json.load(f))
    else:
        print(f"Warning: {LABOR_LAW_PATH} not found.")
    return laws

def build_index():
    """Build and save FAISS index for laws."""
    # Ensure output directory exists
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    # 1. Load Data
    laws = load_laws()
    if not laws:
        print("No laws found to index.")
        return

    print(f"Loaded {len(laws)} articles.")

    # 2. Load Model
    print(f"Loading model: {MODEL_NAME}...")
    model = SentenceTransformer(MODEL_NAME)

    # 3. Generate Embeddings
    print("Generating embeddings...")
    # Combine text for indexing: Category + Arabic Text + English Text (for broader matching)
    documents = [
        f"{law.get('category', '')}: {law['text_ar']} {law.get('text_en', '')}" 
        for law in laws
    ]
    
    embeddings = model.encode(documents, convert_to_numpy=True, show_progress_bar=True)
    
    # 4. Build Index
    print("Building FAISS index...")
    dimension = embeddings.shape[1]
    index = faiss.IndexFlatL2(dimension)
    index.add(embeddings)
    
    # 5. Save Index and Metadata
    index_path = os.path.join(OUTPUT_DIR, "law.index")
    metadata_path = os.path.join(OUTPUT_DIR, "law_metadata.pkl")
    
    print(f"Saving index to {index_path}...")
    faiss.write_index(index, index_path)
    
    print(f"Saving metadata to {metadata_path}...")
    with open(metadata_path, 'wb') as f:
        pickle.dump(laws, f)
        
    print(" indexing complete!")

if __name__ == "__main__":
    build_index()
