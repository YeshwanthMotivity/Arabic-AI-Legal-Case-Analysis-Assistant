import os
import logging
import warnings
import json
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# --- Log Cleaning Setup ---
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3" 
os.environ["TF_ENABLE_ONEDNN_OPTS"] = "0"

warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", category=FutureWarning)

# Configure logging
logging.basicConfig(
    level=getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper()),
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger(__name__)

# Server config
HOST = os.getenv("HOST", "127.0.0.1")
PORT = int(os.getenv("PORT", 5000))
RELOAD = os.getenv("RELOAD", "true").lower() == "true"

# Model config
MODEL_PATH = os.getenv("MODEL_PATH", "./models/similarity_model")
TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", 300))

from fastapi import FastAPI, HTTPException, UploadFile, File, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import asyncio # For robust async/await checking
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from typing import List
from models import (
    Case, SimilarityRequest, SimilarCaseResult, RelatedCase,
    SummarizeRequest, SummarizeResponse,
    AnalyzeRequest, AnalyzeResponse, CaseClassification,
    LegalPrinciple, TrendStats, Recommendation, SubType, SupportingPrinciple,
    DraftRequest, DraftResponse, QueryRequest, QueryResponse,
    ChatRequest, ChatResponse, ChatMessage, SuggestedAction, ClearChatRequest, ConversationSummary, ArchiveRequest,
    SaveConversationRequest
)
from data_loader import load_cases
from similarity_engine import SimilarityEngine
from summarizer_engine import SummarizerEngine
from classification_engine import classify_case, classifier
from legal_principles import extract_legal_principles
from trend_analyzer import analyze_trends
from recommendation_engine import generate_recommendation
from entity_extractor import EntityExtractor
from draft_engine import generate_draft
import uvicorn
from text_extractor import extract_text
from chat_engine import ChatEngine
from chat_storage import ChatStorage

app = FastAPI(title="Arabic AI Legal Case Analysis Assistant", version="2.0.0")

# CORS configuration from environment
CORS_ORIGINS = os.getenv(
    "CORS_ORIGINS", 
    "http://localhost:3000,http://127.0.0.1:3000"
).split(",")

ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
IS_PRODUCTION = ENVIRONMENT == "production"

# Allow CORS for React Frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=not IS_PRODUCTION,  # Don't allow credentials in production
    allow_methods=["GET", "POST", "PUT", "DELETE"],  #  Restrict to needed methods
    allow_headers=["Content-Type", "Authorization"],  #  Restrict headers
)

logger.info(f"CORS enabled for: {CORS_ORIGINS}")
logger.info(f"Environment: {ENVIRONMENT}")

# --- Rate Limiter Setup ---
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ── Global Exception Handler ──────────────────────────────────────────
@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    """Catch all unhandled exceptions and return safe error messages."""
    
    # Log full details server-side (for debugging)
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    
    # Return safe error to client (no stack trace)
    if isinstance(exc, HTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail}
        )
    
    # Generic safe message for unexpected errors
    return JSONResponse(
        status_code=500,
        content={
            "detail": "An internal error occurred. Please try again or contact support.",
            "error_type": exc.__class__.__name__  # Only class name, not full stack
        }
    )

# Global engines & data
similarity_engine = None
summarizer_engine = None
chat_engine = None
chat_storage = None
all_cases_global = []  # Keep reference for trend analysis

@app.on_event("startup")
async def startup_event():
    global similarity_engine, summarizer_engine, chat_engine, chat_storage, all_cases_global
    
    logger.info("Initializing AI Legal Intelligence Platform v2.0...")
    try:
        # Initialize Persistence Layer
        logger.info("Initializing Persistence Layer...")
        chat_storage = ChatStorage()
        # Load Data
        logger.info("Loading cases...")
        all_cases_global = load_cases()
        real_cases = [c for c in all_cases_global if c.is_real]
        logger.info(f"Loaded {len(all_cases_global)} cases ({len(real_cases)} real)")
        
        # Initialize Similarity Engine
        similarity_engine = SimilarityEngine()
        similarity_engine.build_index(real_cases) 
        
        # Initialize Classification Engine (Inject shared model)
        logger.info("Initializing Classification Engine...")
        classifier.set_model(similarity_engine.model)
        
        # Initialize Extractive Summarizer Engine
        logger.info("Loading Extractive Summarizer Engine...")
        summarizer_engine = SummarizerEngine()
        
        # Initialize Chat Engine
        logger.info("Loading Chat Engine...")
        chat_engine = ChatEngine()
        # Inject analysis capability into chat engine
        chat_engine.set_analyzer(execute_full_analysis)

        # Preload local LLM during startup to avoid first-chat cold start delays
        if getattr(chat_engine, "llm", None):
            logger.info("Preloading local LLM at startup...")
            try:
                await asyncio.to_thread(chat_engine.llm.load_model)
            except Exception as preload_error:
                logger.warning(f"LLM preload skipped due to error: {preload_error}")
        
        logger.info(" System ready. All engines loaded successfully.")
        logger.info("   Similarity Engine: READY")
        logger.info("    Summarizer Engine: READY")
        logger.info("    Chat Engine: READY")
        logger.info("   ️ Classification Engine: READY")
        logger.info("   ️ Legal Principles Engine: READY")
        logger.info("    Trend Analyzer: READY")
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
            "llm_loaded": bool(getattr(getattr(chat_engine, "llm", None), "pipeline", None)),
            "classification": True,
            "legal_principles": True,
            "trend_analyzer": True,
            "recommendation": True
        }
    }


# ── Similarity Endpoint ───────────────────────────────────────────────

@app.post("/similar", response_model=List[SimilarCaseResult])
@limiter.limit("20/minute")
async def find_similar_cases(request: Request, sim_req: SimilarityRequest):
    logger.info(f"Similarity request: {sim_req.text[:50]}...")
    if not similarity_engine:
        raise HTTPException(status_code=503, detail="Similarity engine not initialized")
        
    try:
        import math
        results = similarity_engine.search(sim_req.text, top_k=sim_req.top_k)
        
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
        raise HTTPException(status_code=500, detail="Failed to find similar cases. Please try again.")


# ── Summarize Endpoint ────────────────────────────────────────────────

@app.post("/summarize", response_model=SummarizeResponse)
@limiter.limit("20/minute")
async def summarize_case(request: Request, sum_req: SummarizeRequest):
    logger.info(f"Summarization request (Length: {len(sum_req.text)} chars)")
    
    if not summarizer_engine:
        raise HTTPException(status_code=503, detail="Summarizer engine not initialized")
         
    try:
        summary_result = summarizer_engine.summarize(sum_req.text)
        logger.info(f"Extractive summary complete. Confidence: {summary_result.confidence}")
        return summary_result
    except Exception as e:
        logger.error(f"Summarization FAILED: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to summarize text. Please try again.")


async def execute_full_analysis(text: str, top_k: int = 5) -> AnalyzeResponse:
    """Standalone logic for full legal analysis pipeline."""
    if not similarity_engine:
        raise ValueError("Similarity engine not initialized")
    
    logger.info("Starting concurrent Execution of Steps 0-3...")
    import math
    import concurrent.futures

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        future_entities = executor.submit(EntityExtractor.extract, text)
        future_classification = executor.submit(classify_case, text)
        future_principles = executor.submit(extract_legal_principles, text)
        future_similar = executor.submit(similarity_engine.search, text, top_k)

        entities = future_entities.result()
        classification_raw = future_classification.result()
        principles_raw = future_principles.result()
        similar_results = future_similar.result()

    classification = CaseClassification(
        case_type=classification_raw["case_type"],
        name_ar=classification_raw["name_ar"],
        name_en=classification_raw["name_en"],
        confidence=classification_raw["confidence"],
        matched_keywords=classification_raw["matched_keywords"],
        sub_types=[SubType(**st) for st in classification_raw.get("sub_types", [])]
    )
    
    principles = [LegalPrinciple(**p) for p in principles_raw]
    
    
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
    
    # Step 4: Analyze trends (filtering out self-reference)
    logger.info("Step 4/5: Analyzing trends...")
    similar_cases_for_trends = []
    for rc in related_cases_list:
        # Check if identical (distance ~ 0) or text is identical
        # rc.similarity_score is typically 100.0 for identical
        if rc.similarity_score < 99.5: 
             similar_cases_for_trends.append(rc.case)
    
    trends_raw = analyze_trends(similar_cases_for_trends)
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
    
    # Phase 2 Computations: Judicial Intelligence
    win_rate = trends.plaintiff_win_rate
    
    # Appeal Risk
    appeal_risk = "Low"
    if win_rate < 40:
        appeal_risk = "High"
    elif win_rate < 70:
        appeal_risk = "Medium"
        
    # Case Strength
    case_strength = "Strong"
    if win_rate < 40:
        case_strength = "Weak"
    elif win_rate < 70:
        case_strength = "Moderate"
        
    # Contradictions Analyzer
    contradictions = []
    # If the claimed amount is unusually high compared to averages
    if entities.get('compensation_amount') and trends.average_compensation > 0:
        import re
        try:
            claimed_str = re.sub(r'[^\d.]', '', str(entities['compensation_amount']))
            if claimed_str:
                claimed_amt = float(claimed_str)
                if claimed_amt > trends.average_compensation * 2.5:
                    contradictions.append(f"المبلغ المطالب به ({claimed_amt:,.0f} ريال) أعلى بكثير من متوسط التعويض المعتاد ({trends.average_compensation:,.0f} ريال).")
        except:
            pass
            
    # If type is labor but no salary extracted
    dispute_type = entities.get('dispute_type', '')
    if dispute_type == 'عمالي' and not entities.get('salary'):
        contradictions.append("لم يتم العثور على توثيق للراتب الأساسي رغم تصنيف النزاع كنزاع عمالي.")
        
    if not contradictions:
        if related_cases_list:
            contradictions.append("تتطابق وقائع القضية بشكل متسق مع السوابق القضائية دون تناقضات جوهرية.")
        else:
            contradictions.append("لم يتم رصد تناقضات جوهرية في النص المرفق.")

    return AnalyzeResponse(
        classification=classification,
        legal_principles=principles,
        trends=trends,
        recommendation=recommendation,
        entities=entities,
        text=text,
        related_cases=related_cases_list,
        case_strength=case_strength,
        appeal_risk=appeal_risk,
        contradictions=contradictions
    )

@app.post("/analyze", response_model=AnalyzeResponse)
@limiter.limit("5/minute")
async def analyze_case(request: Request, analyze_req: AnalyzeRequest):
    """API endpoint for full legal analysis."""
    logger.info(f"Full analysis request (Length: {len(analyze_req.text)} chars)")
    try:
        return await execute_full_analysis(analyze_req.text, analyze_req.top_k)
    except Exception as e:
        logger.error(f"Analysis FAILED: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to run full analysis. Please try again.")


# ── Legal Draft Endpoint (NEW) ────────────────────────────────────────

@app.post("/draft", response_model=DraftResponse)
@limiter.limit("5/minute")
async def generate_legal_draft_endpoint(request: Request, draft_req: DraftRequest):
    """
    Generate a legal draft (Claim/Defense) based on analysis data.
    """
    logger.info(f"Draft request for {draft_req.case_type} ({draft_req.party_role})")
    try:
        from draft_engine import generate_draft
        
        # Robust check: if generate_draft is async, await it. If sync, call directly.
        if asyncio.iscoroutinefunction(generate_draft):
            try:
                # Add a timeout for safety
                draft = await asyncio.wait_for(
                    generate_draft(
                        case_type=draft_req.case_type,
                        classification_confidence=draft_req.classification_confidence,
                        legal_principles=[p.dict() for p in draft_req.legal_principles], 
                        recommendation=draft_req.recommendation.dict(),
                        party_role=draft_req.party_role,
                        entities=draft_req.entities
                    ),
                    timeout=TIMEOUT
                )
            except asyncio.TimeoutError:
                logger.error("Draft generation timed out")
                raise HTTPException(status_code=504, detail="Draft generation timed out")
        else:
            # Synchronous call
            draft = generate_draft(
                case_type=draft_req.case_type,
                classification_confidence=draft_req.classification_confidence,
                legal_principles=[p.dict() for p in draft_req.legal_principles], 
                recommendation=draft_req.recommendation.dict(),
                party_role=draft_req.party_role,
                entities=draft_req.entities
            )
            
        logger.info(f"Draft generated successfully for {draft_req.case_type}")
        return draft

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Draft FAILED: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to generate draft. Please check your input.")


# ── Interactive Query Endpoint (NEW) ──────────────────────────────────

@app.post("/query", response_model=QueryResponse)
@limiter.limit("20/minute")
async def process_user_query(request: Request, query_req: QueryRequest):
    """
    Process a structured user query based on existing analysis.
    """
    logger.info(f"Query request: {query_req.query_type}")
    try:
        from query_engine import process_query
        response = process_query(query_req.query_type, query_req.analysis_data)
        return response
    except Exception as e:
        logger.error(f"Query processing failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to process query. Please try again.")




# ── Document Upload Endpoint ──────────────────────────────────────────

@app.post("/upload")
@limiter.limit("2/minute")
async def upload_document(request: Request, file: UploadFile = File(...)):
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
@limiter.limit("5/minute")
async def upload_analyze_document(request: Request, file: UploadFile = File(...)):
    """
    Upload a document and immediately run the full analysis pipeline.
    """
    # 1. Extract text
    upload_result = await upload_document(request, file)
    text = upload_result["text"]
    
    # 2. Run analysis
    # Call execute_full_analysis directly to avoid rate limit double-counting and request arg issues
    return await execute_full_analysis(text, top_k=5)


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
@limiter.limit("10/minute")
async def chat(request: Request, chat_req: ChatRequest):
    """
    Main chat endpoint for conversational interactions.
    Accepts user messages and optional analysis context.
    """
    global chat_engine
    
    if not chat_engine:
        raise HTTPException(status_code=503, detail="Chat engine not initialized")
    
    try:
        logger.info(f"Chat request: {chat_req.message[:50]}...")
        logger.info(f"Message length: {len(chat_req.message)}, Has analysis: {chat_req.analysis_data is not None}")
        
        # Convert analysis_data if provided
        analysis_dict = chat_req.analysis_data.dict() if chat_req.analysis_data else None
        
        # Process message through chat engine
        response = await chat_engine.process_message(
            user_message=chat_req.message,
            analysis_data=analysis_dict,
            case_text=chat_req.case_text
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
        intent_value = response.get("intent", "")
        citations = response.get("citations", [])
        if not str(intent_value).startswith("draft"):
            citations = []
        
        return ChatResponse(
            text=response["text"],
            intent=intent_value,
            suggested_actions=suggested_actions,
            timestamp=datetime.now().isoformat(),
            user_translation=response.get("user_translation"),
            assistant_translation=response.get("assistant_translation"),
            citations=citations,
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
        raise HTTPException(status_code=500, detail="Failed to archive conversation. Please try again.")


# ── Conversation Persistence Endpoints ────────────────────────────────

@app.get("/conversations")
async def list_conversations(limit: int = 50, offset: int = 0):
    """List recent conversations with logging."""
    if not chat_storage:
        logger.error("[API_LIST] Storage not initialized")
        raise HTTPException(status_code=503, detail="Storage not initialized")
    
    logger.debug(f"[API_LIST] GET /conversations - limit: {limit}, offset: {offset}")
    conversations = chat_storage.get_all_conversations(limit, offset)
    logger.info(f"[API_LIST] Returning {len(conversations)} conversations")
    return conversations


@app.get("/conversations/{conversation_id}")
async def get_conversation(conversation_id: str):
    """Get full conversation details with logging."""
    if not chat_storage:
        logger.error("[API_GET] Storage not initialized")
        raise HTTPException(status_code=503, detail="Storage not initialized")
    
    logger.debug(f"[API_GET] GET /conversations/{conversation_id}")
    conv = chat_storage.get_conversation(conversation_id)
    if not conv:
        logger.warning(f"[API_GET] Conversation not found: {conversation_id}")
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    logger.info(f"[API_GET] Returning conversation {conversation_id}")
    return conv


@app.post("/conversations")
async def save_conversation(req: SaveConversationRequest):
    """Save or update a conversation with verification."""
    if not chat_storage:
        logger.error("[API_SAVE] Storage not initialized")
        raise HTTPException(status_code=503, detail="Storage not initialized")
    
    logger.info(f"[API_SAVE] POST /conversations - id: {req.id}")
    
    # Generate detailed summary if missing or just keeping it fresh
    summary_data = None
    if summarizer_engine and req.messages:
        # Generate structured summary (Topic + Points)
        # Pass full message history so we can extract user intent
        summary_data = summarizer_engine.summarize_chat_history(req.messages)
        
        # If analysis exists, refine the topic
        if req.analysis and 'classification' in req.analysis:
            summary_data['topic'] = req.analysis['classification'].get('name_ar', summary_data['topic'])

    # Save conversation
    success = chat_storage.save_conversation(
        req.id, 
        req.title, 
        req.preview, 
        req.messages, 
        req.analysis,
        summary_data # New field
    )
    
    if not success:
        logger.error(f"[API_SAVE] Failed to save conversation {req.id}")
        raise HTTPException(status_code=500, detail="Failed to save conversation")
    
    # Verify the save by loading it back
    verification = chat_storage.get_conversation(req.id)
    if not verification:
        logger.error(f"[API_SAVE] Verification failed - conversation not found after save: {req.id}")
        raise HTTPException(status_code=500, detail="Conversation saved but verification failed")
    
    logger.info(f"[API_SAVE] Successfully saved and verified conversation {req.id}")
    
    return {
        "status": "success",
        "id": req.id,
        "title": req.title,
        "verification": "verified",
        "timestamp": datetime.now().isoformat(),
        "message_count": len(req.messages),
        "summary": summary_data
    }


@app.delete("/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str):
    """Delete a conversation permanently."""
    if not chat_storage:
        raise HTTPException(status_code=503, detail="Storage not initialized")
        
    success = chat_storage.delete_conversation(conversation_id)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to delete conversation")
        
    return {"status": "deleted", "id": conversation_id}


@app.delete("/conversations")
async def clear_all_conversations():
    """Clear all active conversations."""
    if not chat_storage:
        raise HTTPException(status_code=503, detail="Storage not initialized")
        
    success = chat_storage.clear_all()
    if not success:
        raise HTTPException(status_code=500, detail="Failed to clear history")
        
    return {"status": "cleared_all"}



if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=5000, reload=False)
