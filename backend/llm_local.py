import torch
from transformers import pipeline
import logging
import os

logger = logging.getLogger(__name__)

class LocalLLM:
    def __init__(self, model_id="Qwen/Qwen2.5-1.5B-Instruct"):
        # Check if model exists locally in models/llm
        local_path = os.path.join(os.path.dirname(__file__), "models", "llm")
        if os.path.exists(local_path):
            self.model_id = local_path
            logger.info(f"Using local LLM path: {self.model_id}")
        else:
            self.model_id = model_id
            logger.info(f"Local path not found, using model ID: {self.model_id}")
            
        self.pipeline = None
        self.tokenizer = None
        
    def load_model(self):
        """Loads the model if not already loaded."""
        if self.pipeline:
            return

        logger.info(f"Loading local LLM: {self.model_id}...")
        try:
            # CPU Optimization: Threading control
            # This prevents PyTorch from saturating all cores and blocking the loop
            torch.set_num_threads(4) 
            torch.set_num_interop_threads(1)
            
            # Determine device
            device = "cuda" if torch.cuda.is_available() else "cpu"
            logger.info(f"Using device: {device}")
            
            # Use pipeline for simplicity
            torch_dtype = torch.float16 if device == "cuda" else torch.float32
            
            self.pipeline = pipeline(
                "text-generation",
                model=self.model_id,
                device_map="auto" if device == "cuda" else None,
                torch_dtype=torch_dtype,
                model_kwargs={"low_cpu_mem_usage": True}
            )
            logger.info("Local LLM loaded successfully with CPU threading optimizations.")
            
        except Exception as e:
            logger.error(f"Failed to load Local LLM: {e}")
            raise e

    def _sync_generate(self, prompt: str, system_prompt: str = None, max_new_tokens=120) -> str:
        """Synchronous generation wrapped in inference mode."""
        if not self.pipeline:
            self.load_model()
            
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        
        messages.append({"role": "user", "content": prompt})
        
        try:
            # CPU Optimization: Greedy decoding (do_sample=False) is much faster
            # Wrapping in inference_mode saves memory/overhead
            with torch.inference_mode():
                outputs = self.pipeline(
                    messages,
                    max_new_tokens=max_new_tokens,
                    do_sample=False, # GREEDY Decoding (Fastest on CPU)
                    use_cache=True,
                    pad_token_id=self.pipeline.tokenizer.eos_token_id
                )
            
            generated = outputs[0]["generated_text"]
            if isinstance(generated, list):
                return generated[-1]["content"]
            elif isinstance(generated, str):
                return generated
            return str(generated)
            
        except Exception as e:
            logger.error(f"Generation error: {e}")
            return "عذراً، حدث خطأ أثناء إنشاء النص. (Model generation error)"

    async def generate(self, prompt: str, system_prompt: str = None, max_new_tokens=120) -> str:
        """
        Asynchronous wrapper to prevent blocking the main FastAPI thread.
        """
        import asyncio
        from concurrent.futures import ThreadPoolExecutor
        
        # Use a singleton executor to prevent thread explosion
        if not hasattr(self, '_executor'):
            self._executor = ThreadPoolExecutor(max_workers=1)
            
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self._executor, 
            self._sync_generate, 
            prompt, 
            system_prompt, 
            max_new_tokens
        )
