import os
import logging
import warnings
import json
from datetime import datetime

# --- Log Cleaning Setup ---
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3" 
os.environ["TF_ENABLE_ONEDNN_OPTS"] = "0"

warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", category=FutureWarning)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger(__name__)

from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from typing import List
from models import (
    Case, SimilarityRequest, SimilarCaseResult, RelatedCase,
    SummarizeRequest, SummarizeResponse,
    AnalyzeRequest, AnalyzeResponse, CaseClassification,
    LegalPrinciple, TrendStats, Recommendation, SubType, SupportingPrinciple,
    DraftRequest, DraftResponse, QueryRequest, QueryResponse,
    ChatRequest, ChatResponse, ChatMessage, SuggestedAction, ClearChatRequest, ConversationSummary, ArchiveRequest
)
from data_loader import load_cases
from similarity_engine import SimilarityEngine
from summarizer_engine import SummarizerEngine
from classification_engine import classify_case
from legal_principles import extract_legal_principles
from trend_analyzer import analyze_trends
from recommendation_engine import generate_recommendation
from entity_extractor import EntityExtractor
from draft_engine import generate_draft
import uvicorn
from text_extractor import extract_text
from chat_engine import ChatEngine

app = FastAPI(title="Arabic AI Legal Case Analysis Assistant", version="2.0.0")

# Allow CORS for React Frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global engines & data
similarity_engine = None
summarizer_engine = None
chat_engine = None
all_cases_global = []  # Keep reference for trend analysis

@app.on_event("startup")
async def startup_event():
    global similarity_engine, summarizer_engine, chat_engine, all_cases_global
    
    logger.info("Initializing AI Legal Intelligence Platform v2.0...")
    try:
        # Load Data
        logger.info("Loading cases...")
        all_cases_global = load_cases()
        real_cases = [c for c in all_cases_global if c.is_real]
        logger.info(f"Loaded {len(all_cases_global)} cases ({len(real_cases)} real)")
        
        # Initialize Similarity Engine
        similarity_engine = SimilarityEngine()
        similarity_engine.build_index(real_cases) 
        
        # Initialize Extractive Summarizer Engine
        logger.info("Loading Extractive Summarizer Engine...")
        summarizer_engine = SummarizerEngine()
        
        # Initialize Chat Engine
        logger.info("Loading Chat Engine...")
        chat_engine = ChatEngine()
        # Inject analysis capability into chat engine
        chat_engine.set_analyzer(execute_full_analysis)
        
        logger.info("✅ System ready. All engines loaded successfully.")
        logger.info("   Similarity Engine: READY")
        logger.info("   📝 Summarizer Engine: READY")
        logger.info("   💬 Chat Engine: READY")
        logger.info("   🏷️ Classification Engine: READY")
        logger.info("   ⚖️ Legal Principles Engine: READY")
        logger.info("   📊 Trend Analyzer: READY")
        logger.info("   Recommendation Engine: READY")
    except Exception as e:
        logger.error(f"CRITICAL STARTUP ERROR: {e}", exc_info=True)


@app.get("/health")
async def health_check():
    return {
        "status": "ok",
        "version": "2.0.0",
        "engines": {
            "similarity": similarity_engine is not None,
            "summarizer": summarizer_engine is not None,
            "chat": chat_engine is not None,
            "classification": True,
            "legal_principles": True,
            "trend_analyzer": True,
            "recommendation": True
        }
    }


# ── Similarity Endpoint ───────────────────────────────────────────────

@app.post("/similar", response_model=List[SimilarCaseResult])
async def find_similar_cases(request: SimilarityRequest):
    logger.info(f"Similarity request: {request.text[:50]}...")
    if not similarity_engine:
        raise HTTPException(status_code=503, detail="Similarity engine not initialized")
        
    try:
        import math
        results = similarity_engine.search(request.text, top_k=request.top_k)
        
        response = []
        for case, distance in results:
            # Gaussian similarity: exp(-d²/2σ²) with σ=15 tuned for SBERT L2 distances
            # This maps typical SBERT L2 range (0-30) to intuitive 0-100% scores
            similarity = math.exp(-(distance ** 2) / (2 * 15 ** 2))
            percentage = round(similarity * 100, 2)
            
            response.append(SimilarCaseResult(
                case_id=case.case_id,
                similarity_score=percentage,
                preview=case.facts[:200] + "..." 
            ))
        logger.info(f"Found {len(response)} similar cases.")
        return response
    except Exception as e:
        logger.error(f"Similarity error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ── Summarize Endpoint ────────────────────────────────────────────────

@app.post("/summarize", response_model=SummarizeResponse)
async def summarize_case(request: SummarizeRequest):
    logger.info(f"Summarization request (Length: {len(request.text)} chars)")
    
    if not summarizer_engine:
        raise HTTPException(status_code=503, detail="Summarizer engine not initialized")
         
    try:
        summary_result = summarizer_engine.summarize(request.text)
        logger.info(f"Extractive summary complete. Confidence: {summary_result.confidence}")
        return summary_result
    except Exception as e:
        logger.error(f"Summarization FAILED: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


async def execute_full_analysis(text: str, top_k: int = 5) -> AnalyzeResponse:
    """Standalone logic for full legal analysis pipeline."""
    if not similarity_engine:
        raise ValueError("Similarity engine not initialized")
    
    # Step 0: Extract Entities
    logger.info("Step 0/5: Extracting entities...")
    entities = EntityExtractor.extract(text)

    # Step 1: Classify case type
    logger.info("Step 1/5: Classifying case type...")
    classification_raw = classify_case(text)
    classification = CaseClassification(
        case_type=classification_raw["case_type"],
        name_ar=classification_raw["name_ar"],
        name_en=classification_raw["name_en"],
        confidence=classification_raw["confidence"],
        matched_keywords=classification_raw["matched_keywords"],
        sub_types=[SubType(**st) for st in classification_raw.get("sub_types", [])]
    )
    
    # Step 2: Extract legal principles
    logger.info("Step 2/5: Extracting legal principles...")
    principles_raw = extract_legal_principles(text)
    principles = [LegalPrinciple(**p) for p in principles_raw]
    
    # Step 3: Find similar cases
    logger.info("Step 3/5: Finding similar cases...")
    import math
    similar_results = similarity_engine.search(text, top_k=top_k)
    
    related_cases_list = []
    for case, distance in similar_results:
        # Gaussian similarity: exp(-d²/2σ²) with σ=15 tuned for SBERT L2 distances
        similarity = math.exp(-(distance ** 2) / (2 * 15 ** 2))
        percentage = round(similarity * 100, 2)
        
        related_cases_list.append(RelatedCase(
            case=case,
            similarity_score=percentage,
            preview=case.facts[:200] + "..."
        ))
    
    # Step 4: Analyze trends
    logger.info("Step 4/5: Analyzing trends...")
    similar_cases = [rc.case for rc in related_cases_list]
    trends_raw = analyze_trends(similar_cases)
    trends = TrendStats(**trends_raw)
    
    # Step 5: Generate recommendation
    logger.info("Step 5/5: Generating recommendation...")
    recommendation_raw = generate_recommendation(
        trends_raw, classification_raw, principles_raw, entities
    )
    recommendation = Recommendation(
        recommendation_ar=recommendation_raw["recommendation_ar"],
        recommendation_en=recommendation_raw["recommendation_en"],
        direction=recommendation_raw["direction"],
        confidence=recommendation_raw["confidence"],
        disclaimer_ar=recommendation_raw["disclaimer_ar"],
        disclaimer_en=recommendation_raw["disclaimer_en"],
        supporting_principles=[
            SupportingPrinciple(**sp) for sp in recommendation_raw.get("supporting_principles", [])
        ],
        based_on_sample_size=recommendation_raw["based_on_sample_size"],
        reliability=recommendation_raw["reliability"]
    )
    
    return AnalyzeResponse(
        classification=classification,
        legal_principles=principles,
        trends=trends,
        recommendation=recommendation,
        entities=entities,
        text=text,
        related_cases=related_cases_list
    )

@app.post("/analyze", response_model=AnalyzeResponse)
async def analyze_case(request: AnalyzeRequest):
    """API endpoint for full legal analysis."""
    logger.info(f"Full analysis request (Length: {len(request.text)} chars)")
    try:
        return await execute_full_analysis(request.text, request.top_k)
    except Exception as e:
        logger.error(f"Analysis FAILED: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ── Legal Draft Endpoint (NEW) ────────────────────────────────────────

@app.post("/draft", response_model=DraftResponse)
async def generate_legal_draft_endpoint(request: DraftRequest):
    """
    Generate a legal draft (Claim/Defense) based on analysis data.
    """
    logger.info(f"Draft request for {request.case_type} ({request.party_role})")
    try:
        from draft_engine import generate_draft
        draft = generate_draft(
            case_type=request.case_type,
            classification_confidence=request.classification_confidence,
            legal_principles=[p.dict() for p in request.legal_principles], 
            recommendation=request.recommendation.dict(),
            party_role=request.party_role,
            entities=request.entities # NEW
        )
        return draft
    except Exception as e:
        logger.error(f"Draft generation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ── Interactive Query Endpoint (NEW) ──────────────────────────────────

@app.post("/query", response_model=QueryResponse)
async def process_user_query(request: QueryRequest):
    """
    Process a structured user query based on existing analysis.
    """
    logger.info(f"Query request: {request.query_type}")
    try:
        from query_engine import process_query
        response = process_query(request.query_type, request.analysis_data)
        return response
    except Exception as e:
        logger.error(f"Query processing failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))




# ── Document Upload Endpoint ──────────────────────────────────────────

@app.post("/upload")
async def upload_document(file: UploadFile = File(...)):
    """
    Upload a document (PDF, DOCX, TXT) and extract its text.
    """
    logger.info(f"Received upload request: filename='{file.filename}', content_type='{file.content_type}'")
    
    # Basic validation
    allowed_types = [
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "text/plain",
        "application/json"
    ]
    
    # Simple extension check as fallback
    ext = os.path.splitext(file.filename)[1].lower() if file.filename else ""
    
    # Check for legacy .doc files
    if ext == ".doc":
        logger.warning(f"Rejected .doc file: {file.filename}")
        raise HTTPException(status_code=400, detail="Legacy word files (.doc) are not supported. Please save as .docx and try again.")

    if ext not in [".pdf", ".docx", ".txt", ".json"] and file.content_type not in allowed_types:
        logger.warning(f"Unsupported file type: ext='{ext}', content_type='{file.content_type}'")
        raise HTTPException(status_code=400, detail=f"Invalid file type. Allowed: PDF, DOCX, TXT, JSON. Got: {file.content_type} (ext: {ext})")
    
    # Max file size: 10MB
    MAX_SIZE = 10 * 1024 * 1024
    content = await file.read()
    
    if len(content) > MAX_SIZE:
        logger.warning(f"File too large: {len(content)} bytes")
        raise HTTPException(status_code=413, detail="File too large. Maximum size is 10MB.")
    
    try:
        text = extract_text(file.filename, content)
        
        if not text.strip():
            logger.warning(f"Empty text extracted from {file.filename}")
            raise HTTPException(status_code=400, detail="Could not extract text from file (it might be a scanned image without OCR) or file is empty.")
             
        logger.info(f"Successfully extracted {len(text)} chars from {file.filename}")
        return {"filename": file.filename, "text": text}
        
    except ValueError as ve:
        logger.warning(f"Value error during extraction: {ve}")
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.error(f"Upload failed for {file.filename}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"File upload error: {str(e)}")


@app.post("/upload-analyze", response_model=AnalyzeResponse)
async def upload_analyze_document(file: UploadFile = File(...)):
    """
    Upload a document and immediately run the full analysis pipeline.
    """
    # 1. Extract text
    upload_result = await upload_document(file)
    text = upload_result["text"]
    
    # 2. Run analysis
    # Construct AnalyzeRequest
    analyze_req = AnalyzeRequest(text=text, top_k=5)
    
    # Call analyze_case directly
    return await analyze_case(analyze_req)


# ── Analytics Endpoint (Dataset-wide Statistics) ──────────────────────

@app.get("/analytics")
async def get_analytics():
    """
    Dataset-wide statistics for the analytics dashboard.
    Labeled as 'Dataset-based simulation' per user requirement.
    """
    logger.info("Analytics request")
    
    try:
        real_cases = [c for c in all_cases_global if c.is_real]
        
        # Classify all cases
        from classification_engine import classify_case as cc
        from trend_analyzer import detect_outcome, extract_compensation_amount, filter_outliers
        
        type_distribution = {}
        outcome_distribution = {"plaintiff_win": 0, "plaintiff_loss": 0, "dismissed": 0, "jurisdictional": 0, "unknown": 0}
        compensations = []
        
        for case in real_cases:
            # Classify
            full_text = case.facts + " " + case.legal_reasoning + " " + case.judgment
            cls = cc(full_text)
            ctype = cls["name_ar"]
            type_distribution[ctype] = type_distribution.get(ctype, 0) + 1
            
            # Outcome
            outcome = detect_outcome(case.judgment)
            outcome_distribution[outcome] = outcome_distribution.get(outcome, 0) + 1
            
            # Compensation
            amount = extract_compensation_amount(case.judgment)
            if amount and amount > 0:
                compensations.append(amount)
        
        filtered_comp = filter_outliers(compensations)
        avg_comp = sum(filtered_comp) / len(filtered_comp) if filtered_comp else 0
        
        return {
            "data_source": "Dataset-based simulation (not live judiciary data)",
            "total_cases": len(real_cases),
            "case_type_distribution": type_distribution,
            "outcome_distribution": outcome_distribution,
            "compensation_stats": {
                "average": round(avg_comp, 2),
                "min": min(filtered_comp) if filtered_comp else 0,
                "max": max(filtered_comp) if filtered_comp else 0,
                "count": len(compensations),
                "filtered_count": len(filtered_comp)
            }
        }
    except Exception as e:
        logger.error(f"Analytics error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ── Chat Endpoint (NEW - Chatbot Interface) ───────────────────────────

@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Main chat endpoint for conversational interactions.
    Accepts user messages and optional analysis context.
    """
    global chat_engine
    
    if not chat_engine:
        raise HTTPException(status_code=503, detail="Chat engine not initialized")
    
    try:
        logger.info(f"Chat request: {request.message[:50]}...")
        logger.info(f"Message length: {len(request.message)}, Has analysis: {request.analysis_data is not None}")
        
        # Convert analysis_data if provided
        analysis_dict = request.analysis_data.dict() if request.analysis_data else None
        
        # Process message through chat engine
        response = await chat_engine.process_message(
            user_message=request.message,
            analysis_data=analysis_dict,
            case_text=request.case_text
        )
        
        # Log translation for debugging
        if "user_translation" in response:
            logger.info(f"User translation generated: {response['user_translation'][:50]}...")
        else:
            logger.warning("No user translation generated for this message.")
        
        logger.info(f"Detected intent: {response.get('intent')}")
        logger.info(f"Response text (first 50 chars): {response['text'][:50]}...")
        
        # Convert response to ChatResponse model
        suggested_actions = [
            SuggestedAction(**action) if isinstance(action, dict) else action
            for action in response.get("suggested_actions", [])
        ]
        
        return ChatResponse(
            text=response["text"],
            intent=response["intent"],
            suggested_actions=suggested_actions,
            timestamp=datetime.now().isoformat(),
            user_translation=response.get("user_translation"),
            assistant_translation=response.get("assistant_translation"),
            citations=response.get("citations", []),
            metadata=response.get("metadata", {}),
            analysis_data=response.get("analysis_data"),
            error=response.get("error")
        )
        
    except Exception as e:
        logger.error(f"Chat error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/chat/history")
async def get_chat_history():
    """Retrieve conversation history."""
    global chat_engine
    
    if not chat_engine:
        raise HTTPException(status_code=503, detail="Chat engine not initialized")
    
    try:
        history = chat_engine.get_conversation_history()
        return {"messages": history}
    except Exception as e:
        logger.error(f"History retrieval error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/chat/context")
async def get_chat_context():
    """Get current chat context summary."""
    global chat_engine
    
    if not chat_engine:
        raise HTTPException(status_code=503, detail="Chat engine not initialized")
    
    try:
        context = chat_engine.get_context_summary()
        return ConversationSummary(**context)
    except Exception as e:
        logger.error(f"Context retrieval error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/chat/clear")
async def clear_chat(request: ClearChatRequest):
    """Clear chat history and context."""
    global chat_engine
    
    if not chat_engine:
        raise HTTPException(status_code=503, detail="Chat engine not initialized")
    
    try:
        chat_engine.clear_conversation()
        return {"status": "cleared", "message": "Chat history cleared successfully"}
    except Exception as e:
        logger.error(f"Clear chat error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/conversations/archive")
async def archive_conversation(request: ArchiveRequest):
    """Archive a conversation to persistent storage."""
    try:
        archive_file = "conversations_archive.json"
        
        # Load existing
        archives = []
        if os.path.exists(archive_file):
            with open(archive_file, "r", encoding="utf-8") as f:
                try:
                    archives = json.load(f)
                except:
                    archives = []
        
        # Add new archive
        entry = request.dict()
        entry["archived_at"] = datetime.now().isoformat()
        archives.append(entry)
        
        # Save
        with open(archive_file, "w", encoding="utf-8") as f:
            json.dump(archives, f, ensure_ascii=False, indent=2)
            
        logger.info(f"Archived conversation {request.conversation_id}")
        return {"status": "success", "message": "Conversation archived successfully"}
        
    except Exception as e:
        logger.error(f"Archive error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=5000, reload=False)
