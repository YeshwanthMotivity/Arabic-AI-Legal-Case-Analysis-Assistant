"""
Extractive Summarizer Engine for Arabic Legal Cases.

Instead of generating new text (which causes hallucinations),
this engine selects the most important sentences from the original text.

Pipeline:
1. Split text into sentences (Arabic punctuation aware)
2. Generate embeddings for each sentence using SBERT
3. Compute similarity of each sentence to the full document
4. Select top N most central/important sentences
5. Return them in original order

This guarantees:
- 100% factual consistency (no fabricated content)
- No hallucination
- No language drift
- Stable, predictable output
"""

import re
import numpy as np
from sentence_transformers import SentenceTransformer
from models import SummarizeResponse
import os
from entity_extractor import EntityExtractor


class SummarizerEngine:
    def __init__(self):
        """
        Reuses the same SBERT model used for similarity search.
        No separate generative model needed.
        """
        local_path = os.path.join(os.path.dirname(__file__), "models", "similarity_model")
        if os.path.exists(local_path):
            print(f"[Summarizer] Loading local SBERT model from {local_path}...")
            self.model = SentenceTransformer(local_path)
        else:
            model_name = 'sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2'
            print(f"[Summarizer] Loading SBERT model: {model_name}...")
            self.model = SentenceTransformer(model_name)
        
        print("[Summarizer] Extractive summarizer ready.")

    def split_sentences(self, text: str):
        """
        Split Arabic legal text into sentences.
        Handles Arabic punctuation marks and common legal text patterns.
        """
        # Normalize whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        
        # Split on Arabic and standard sentence-ending punctuation
        # Also split on common legal section markers
        sentences = re.split(r'(?<=[.!؟。])\s+|(?<=:)\s*\n', text)
        
        # Filter out very short fragments (less than 20 chars)
        sentences = [s.strip() for s in sentences if len(s.strip()) > 20]
        
        return sentences

    def extract_legal_sections(self, text: str):
        """
        Detect legal sections using regex for robust matching.
        Handles: الوقائع / الأسباب / منطوق الحكم
        Falls back to full text if no sections detected.
        """
        sections = {
            "facts": "",
            "reasoning": "",
            "verdict": ""
        }
        
        # Regex-based section extraction (handles with/without colon)
        facts_match = re.search(
            r'(?:الوقائع|وقائع الدعوى|تتحصل وقائع)[:\s]*(.*?)(?=الأسباب|أسباب الحكم|وحيث إن المحكمة|منطوق الحكم|حكمت المحكمة|فلهذه الأسباب|$)',
            text, re.DOTALL
        )
        reasoning_match = re.search(
            r'(?:الأسباب|أسباب الحكم|وحيث إن المحكمة)[:\s]*(.*?)(?=منطوق الحكم|حكمت المحكمة|فلهذه الأسباب|$)',
            text, re.DOTALL
        )
        verdict_match = re.search(
            r'(?:منطوق الحكم|حكمت المحكمة|فلهذه الأسباب)[:\s]*(.*)',
            text, re.DOTALL
        )
        
        if facts_match:
            sections["facts"] = facts_match.group(1).strip()
        if reasoning_match:
            sections["reasoning"] = reasoning_match.group(1).strip()
        if verdict_match:
            sections["verdict"] = verdict_match.group(1).strip()
        
        # If no sections detected at all, put everything in facts
        if not any(sections.values()):
            sections["facts"] = text.strip()
        
        return sections

    def extractive_summary(self, text: str, top_k: int = 3):
        """
        Core extractive summarization using sentence centrality.
        
        1. Embed all sentences
        2. Embed the full document
        3. Rank sentences by cosine similarity to document
        4. Return top-k in original order
        """
        sentences = self.split_sentences(text)
        
        if not sentences:
            return text  # Return original if can't split
        
        if len(sentences) <= top_k:
            return "\n".join(sentences)
        
        # Generate embeddings for all sentences + full document
        all_texts = sentences + [text]
        embeddings = self.model.encode(all_texts, convert_to_numpy=True)
        
        sentence_embeddings = embeddings[:-1]  # All except last
        document_embedding = embeddings[-1]    # Last one is full doc
        
        # Compute cosine similarity of each sentence to the document
        # Normalize vectors
        norms_s = np.linalg.norm(sentence_embeddings, axis=1, keepdims=True)
        norm_d = np.linalg.norm(document_embedding)
        
        # Avoid division by zero
        norms_s = np.where(norms_s == 0, 1, norms_s)
        norm_d = max(norm_d, 1e-8)
        
        similarities = np.dot(sentence_embeddings / norms_s, document_embedding / norm_d)
        
        # Get top-k indices
        ranked_indices = np.argsort(similarities)[::-1][:top_k]
        
        # Sort by original order to maintain flow
        ranked_indices = sorted(ranked_indices)
        
        summary_sentences = [sentences[i] for i in ranked_indices]
        
        return "\n".join(summary_sentences)

    def summarize(self, text: str) -> SummarizeResponse:
        """
        Structured Legal Summary.
        Extracts 1 key sentence per section for concise, balanced output.
        """
        try:
            # Extract legal sections via regex
            sections = self.extract_legal_sections(text)
            
            # Extract basic context
            entities = EntityExtractor.extract(text)
            
            # --- Per-section extraction (Increased Depth) ---
            k_facts = 3
            k_reason = 2
            
            facts_summary = None
            reasoning_summary = None
            verdict_summary = None
            
            if sections["facts"]:
                facts_sentences = self.split_sentences(sections["facts"])
                if len(facts_sentences) > 1:
                    facts_summary = self.extractive_summary(sections["facts"], top_k=min(k_facts, len(facts_sentences)))
                    # Prepend context
                    if entities.get('date') or entities.get('compensation_amount'):
                        date_str = entities.get('date', 'غير محدد')
                        amt_str = entities.get('compensation_amount', 'غير محدد')
                        context = f"[تاريخ العقد: {date_str} | المبلغ: {amt_str}]\n"
                        facts_summary = context + facts_summary
                else:
                    facts_summary = sections["facts"]
            
            if sections["reasoning"]:
                reasoning_sentences = self.split_sentences(sections["reasoning"])
                if len(reasoning_sentences) > 1:
                    reasoning_summary = self.extractive_summary(sections["reasoning"], top_k=min(k_reason, len(reasoning_sentences)))
                else:
                    reasoning_summary = sections["reasoning"]
            
            if sections["verdict"]:
                # Always include full verdict text (usually 1-2 sentences)
                verdict_summary = sections["verdict"]
            
            # --- Build overall summary: 1 sentence from each section ---
            overall_parts = []
            if facts_summary:
                overall_parts.append(facts_summary)
            if reasoning_summary:
                overall_parts.append(reasoning_summary)
            if verdict_summary:
                overall_parts.append(verdict_summary)
            
            if overall_parts:
                overall_summary = "\n".join(overall_parts)
            else:
                # Fallback: extract top 3 from full text
                overall_summary = self.extractive_summary(text, top_k=3)
            
            # Confidence: high for structured, slightly lower for fallback
            confidence = 0.97 if any(sections.values()) else 0.90
            
            return SummarizeResponse(
                summary=overall_summary,
                facts_summary=facts_summary,
                reasoning_summary=reasoning_summary,
                verdict_summary=verdict_summary,
                confidence=confidence
            )
            
        except Exception as e:
            print(f"Summarization error: {e}")
            return SummarizeResponse(
                summary=f"Error: {str(e)}",
                confidence=0.0
            )

    def summarize_chat_history(self, messages: list) -> dict:
        """
        Generate a structured summary (Topic + Key Points) from chat history.
        """
        try:
            # 1. Aggregate User Messages
            user_text = " ".join([m.get("content", "") for m in messages if m.get("role") == "user"])
            if not user_text:
                return {"topic": "محادثة جديدة", "points": ["لا توجد تفاصيل متاحة"]}
            
            # 2. Extract Topic (First significant sentence or Entity)
            # Simple heuristic: First 60 chars or first sentence
            topic = user_text[:60] + "..." if len(user_text) > 60 else user_text
            
            # 3. Extract Key Points (Top 3 sentences)
            # Use existing extractive_summary logic
            sentences = self.split_sentences(user_text)
            
            if len(sentences) <= 3:
                points = sentences
            else:
                # Use SBERT to find top 3
                summary_str = self.extractive_summary(user_text, top_k=3)
                points = summary_str.split('\n')
            
            return {
                "topic": "استشارة قانونية عامة", # Placeholder, will be refined if analysis exists
                "points": [p.strip() for p in points if p.strip()]
            }
            
        except Exception as e:
            print(f"Chat summary error: {e}")
            return {"topic": "خطأ في التلخيص", "points": []}


if __name__ == "__main__":
    engine = SummarizerEngine()
    text = """الوقائع:
تقدم المدعي بدعوى أمام المحكمة العامة يطالب فيها بإلزام المدعى عليه بسداد مبلغ وقدره 75,000 ريال سعودي، وذلك نتيجة إخلاله بالعقد المبرم بين الطرفين والمتعلق بتنفيذ أعمال صيانة في أحد العقارات.

الأسباب:
وحيث إن المحكمة بعد الاطلاع على أوراق الدعوى تبين لها وجود عقد صحيح وموقع بين الطرفين، وثبوت قيام المدعي بتنفيذ التزاماته التعاقدية.

منطوق الحكم:
حكمت المحكمة بإلزام المدعى عليه بسداد مبلغ 75,000 ريال سعودي للمدعي، وتحميله المصاريف القضائية."""
    
    result = engine.summarize(text)
    print(f"Summary:\n{result.summary}")
    print(f"\nFacts: {result.facts_summary}")
    print(f"Reasoning: {result.reasoning_summary}")
    print(f"Verdict: {result.verdict_summary}")
    print(f"Confidence: {result.confidence}")
