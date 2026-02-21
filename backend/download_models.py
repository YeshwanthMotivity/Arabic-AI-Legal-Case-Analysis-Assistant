import os
from sentence_transformers import SentenceTransformer
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM, AutoModelForCausalLM, pipeline

MODEL_DIR = os.path.join(os.path.dirname(__file__), "models")
os.makedirs(MODEL_DIR, exist_ok=True)

def download_models():
    print(f"Downloading models to {MODEL_DIR}...")
    
    # 1. Similarity Model
    sim_model_name = 'sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2'
    sim_path = os.path.join(MODEL_DIR, "similarity_model")
    print(f"Downloading {sim_model_name}...")
    model = SentenceTransformer(sim_model_name)
    model.save(sim_path)
    print(f"Saved to {sim_path}")

    # 2. Summarization Model (Extractive - reused from SBERT)
    # The system uses the SBERT model for extractive summarization to ensure factual consistency.
    # No separate generative model (like mT5) is required.


    # 3. Local LLM (Qwen)
    llm_model_name = "Qwen/Qwen2.5-1.5B-Instruct"
    llm_path = os.path.join(MODEL_DIR, "llm")
    print(f"Downloading {llm_model_name} to {llm_path}...")
    
    tokenizer = AutoTokenizer.from_pretrained(llm_model_name)
    model = AutoModelForCausalLM.from_pretrained(llm_model_name, torch_dtype="auto", low_cpu_mem_usage=True)
    
    tokenizer.save_pretrained(llm_path)
    model.save_pretrained(llm_path)
    print(f"Saved LLM to {llm_path}")
    
    print("\n All models downloaded successfully for offline use.")

if __name__ == "__main__":
    download_models()
