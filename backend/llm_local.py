import logging
import os

import torch
from transformers import TextIteratorStreamer, pipeline

logger = logging.getLogger(__name__)


class LocalLLM:
    def __init__(self, model_id: str = "Qwen/Qwen2.5-1.5B-Instruct"):
        local_path = os.path.join(os.path.dirname(__file__), "models", "llm")
        if os.path.isdir(local_path):
            self.model_id = local_path
            logger.info(f"Using local LLM path: {self.model_id}")
        else:
            self.model_id = model_id
            logger.info(f"Local path not found, using model ID: {self.model_id}")

        self.pipeline = None
        self.max_new_tokens = int(os.getenv("LLM_MAX_NEW_TOKENS", "1536"))
        self.max_input_tokens = int(os.getenv("LLM_MAX_INPUT_TOKENS", "2048"))
        self.num_threads = int(os.getenv("LLM_NUM_THREADS", "4"))

    def load_model(self):
        """Load model once and reuse it."""
        if self.pipeline is not None:
            return

        logger.info(f"Loading local LLM: {self.model_id}...")
        try:
            torch.set_num_threads(self.num_threads)

            device = "cuda" if torch.cuda.is_available() else "cpu"
            logger.info(f"Using device: {device}")

            dtype = torch.float16 if device == "cuda" else torch.float32
            local_files_only = os.path.isdir(self.model_id)

            self.pipeline = pipeline(
                "text-generation",
                model=self.model_id,
                device_map="auto" if device == "cuda" else None,
                dtype=dtype,
                model_kwargs={"low_cpu_mem_usage": True},
                local_files_only=local_files_only,
            )
            gen_cfg = self.pipeline.model.generation_config
            gen_cfg.do_sample = False
            gen_cfg.temperature = 1.0
            gen_cfg.top_p = 1.0
            gen_cfg.top_k = 50
            logger.info(f"Local LLM loaded successfully with {self.num_threads} threads.")
        except Exception as e:
            logger.error(f"Failed to load Local LLM: {e}")
            raise

    def _build_inputs(self, prompt: str, system_prompt: str = None):
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        tokenized = self.pipeline.tokenizer.apply_chat_template(
            messages,
            tokenize=True,
            add_generation_prompt=True,
            return_tensors="pt",
        )

        # Some tokenizer versions return a BatchEncoding, others return a Tensor.
        if hasattr(tokenized, "input_ids"):
            input_ids = tokenized.input_ids
        elif isinstance(tokenized, dict):
            input_ids = tokenized.get("input_ids")
        else:
            input_ids = tokenized

        if input_ids is None:
            raise RuntimeError("Tokenizer output does not contain input_ids")

        input_ids = input_ids.to(self.pipeline.device)

        if input_ids.shape[-1] > self.max_input_tokens:
            input_ids = input_ids[:, -self.max_input_tokens :]
        attention_mask = torch.ones_like(input_ids, device=input_ids.device)
        return input_ids, attention_mask

    async def generate_stream(self, prompt: str, system_prompt: str = None, max_new_tokens: int = None):
        if not self.pipeline:
            self.load_model()

        from threading import Thread

        input_ids, attention_mask = self._build_inputs(prompt, system_prompt)
        token_limit = max_new_tokens if max_new_tokens is not None else self.max_new_tokens

        streamer = TextIteratorStreamer(self.pipeline.tokenizer, skip_prompt=True, skip_special_tokens=True)
        generation_kwargs = dict(
            input_ids=input_ids,
            attention_mask=attention_mask,
            streamer=streamer,
            max_new_tokens=token_limit,
            do_sample=False,
            use_cache=True,
            num_return_sequences=1,
            pad_token_id=self.pipeline.tokenizer.eos_token_id,
        )

        thread = Thread(target=self.pipeline.model.generate, kwargs=generation_kwargs)
        thread.start()

        for new_text in streamer:
            yield new_text

    def generate(self, prompt: str, system_prompt: str = None, max_new_tokens: int = None) -> str:
        if not self.pipeline:
            self.load_model()

        try:
            input_ids, attention_mask = self._build_inputs(prompt, system_prompt)
            token_limit = max_new_tokens if max_new_tokens is not None else self.max_new_tokens
            logger.info(
                "LLM generate called (input_tokens=%s, max_new_tokens=%s)",
                int(input_ids.shape[-1]),
                int(token_limit),
            )

            output_ids = self.pipeline.model.generate(
                input_ids=input_ids,
                attention_mask=attention_mask,
                max_new_tokens=token_limit,
                do_sample=False,
                use_cache=True,
                num_return_sequences=1,
                pad_token_id=self.pipeline.tokenizer.eos_token_id,
            )
            generated_ids = output_ids[0][input_ids.shape[-1] :]
            output_text = self.pipeline.tokenizer.decode(generated_ids, skip_special_tokens=True).strip()
            logger.info("LLM generate completed (output_chars=%s)", len(output_text))
            return output_text
        except Exception as e:
            logger.error("LLM generation error: %r", e, exc_info=True)
            return "Sorry, a model generation error occurred."

    def generate_recommendations(self, case_analysis: dict, data_availability: dict) -> str:
        """Generate recommendation text with strict anti-hallucination instructions."""
        data_context = self._build_data_availability_context(data_availability)
        prompt = (
            "Based on the case analysis below, provide recommendation guidance.\n\n"
            "IMPORTANT DATA AVAILABILITY:\n"
            f"{data_context}\n\n"
            "CASE ANALYSIS:\n"
            f"{case_analysis}\n\n"
            "RULES:\n"
            "1) Never invent statistics or percentages.\n"
            "2) Use only provided values.\n"
            "3) If insufficient data, explicitly say so and provide principle-based guidance only.\n"
            "4) Do not imply trend certainty without sample support.\n"
            "5) Separate data-driven claims from general legal guidance.\n"
        )
        output = self.generate(prompt, system_prompt=self._get_safe_analysis_system_prompt())

        # Optional post-generation validation guard.
        try:
            from llm_output_validator import LLMOutputValidator

            validator = LLMOutputValidator(data_availability)
            check = validator.validate_output(output)
            if not check.get("is_valid", True):
                return (
                    "Insufficient validated data for statistical statements. "
                    "Providing only principle-based recommendation guidance."
                )
        except Exception:
            # Keep runtime robust if validator is unavailable.
            pass
        return output

    def _build_data_availability_context(self, data_availability: dict) -> str:
        total_cases = int(data_availability.get("total_cases_available", 0))
        possible = data_availability.get("statistics_possible", [])
        impossible = data_availability.get("statistics_impossible", {})
        possible_text = "\n".join(f"- {item}" for item in possible) if possible else "- None"
        impossible_text = (
            "\n".join(f"- {k} (min {v})" for k, v in impossible.items())
            if impossible
            else "- None"
        )
        return (
            f"Total cases available: {total_cases}\n"
            f"Statistics possible:\n{possible_text}\n"
            f"Statistics not possible:\n{impossible_text}"
        )

    def _get_safe_analysis_system_prompt(self) -> str:
        return (
            "You are a legal analysis assistant focused on accuracy.\n"
            "Do not fabricate statistics, case counts, rates, or precedent claims.\n"
            "When data is insufficient, state this clearly and provide general legal principles only.\n"
        )
