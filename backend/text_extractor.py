"""
Text Extractor for Arabic Legal Documents.

Extracts plain text from PDF and DOCX files for downstream analysis.
Supports:
- PDF via PyMuPDF (fitz) — handles Arabic/RTL text
- DOCX via python-docx — handles paragraphs and tables
- TXT — direct passthrough
"""

import os
import logging

logger = logging.getLogger(__name__)


def extract_from_pdf(file_bytes: bytes) -> str:
    """
    Extract text from PDF using pdfplumber (better for Arabic/RTL) 
    with a fallback to PyMuPDF.
    """
    import io
    
    # Method 1: pdfplumber (Better for RTL/Arabic logical order)
    try:
        import pdfplumber
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            text_parts = []
            for page in pdf.pages:
                # extract_text usually handles layout better than simple string extraction
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)
            
            if text_parts:
                full_text = "\n\n".join(text_parts)
                logger.info(f"Extracted {len(full_text)} chars using pdfplumber")
                return full_text
    except ImportError:
        logger.warning("pdfplumber not found, falling back to PyMuPDF")
    except Exception as e:
        logger.error(f"pdfplumber extraction failed: {e}, falling back to PyMuPDF")

    # Method 2: PyMuPDF (Faster, good fallback)
    try:
        import fitz  # PyMuPDF
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        text_parts = []
        seen_content = set() 
        
        for page_num in range(len(doc)):
            page = doc[page_num]
            # "text" mode is standard, but for Arabic sometimes "blocks" with sorting helps
            # However, sticking to standard text for now as baseline
            text = page.get_text("text").strip()
            
            if text:
                content_fingerprint = " ".join(text.split())[:1000]
                if content_fingerprint not in seen_content:
                    text_parts.append(text)
                    seen_content.add(content_fingerprint)
        
        full_text = "\n\n".join(text_parts)
        doc.close()
        logger.info(f"Extracted {len(full_text)} chars usinig PyMuPDF")
        return full_text
    except Exception as e:
        logger.error(f"PyMuPDF extraction failed: {e}")
        raise ValueError("Failed to extract text from PDF using both pdfplumber and PyMuPDF")


def extract_from_docx(file_bytes: bytes) -> str:
    """Extract text from DOCX bytes using python-docx."""
    try:
        from docx import Document
    except ImportError:
        raise ImportError("python-docx not installed. Run: pip install python-docx")
    
    import io
    doc = Document(io.BytesIO(file_bytes))
    
    text_parts = []
    
    # Extract paragraphs
    for para in doc.paragraphs:
        if para.text.strip():
            text_parts.append(para.text.strip())
    
    # Extract table content (legal docs often have tables)
    for table in doc.tables:
        for row in table.rows:
            row_text = " | ".join(cell.text.strip() for cell in row.cells if cell.text.strip())
            if row_text:
                text_parts.append(row_text)
    
    full_text = "\n".join(text_parts)
    logger.info(f"Extracted {len(full_text)} chars from DOCX ({len(doc.paragraphs)} paragraphs)")
    return full_text


def extract_text(filename: str, file_bytes: bytes) -> str:
    """
    Extract text from a file based on its extension.
    
    Args:
        filename: Original filename (used to detect type)
        file_bytes: Raw file content
        
    Returns:
        Extracted plain text
        
    Raises:
        ValueError: If file type is not supported
    """
    ext = os.path.splitext(filename)[1].lower()
    
    if ext == ".pdf":
        return extract_from_pdf(file_bytes)
    elif ext in (".docx",):
        return extract_from_docx(file_bytes)
    elif ext in (".txt", ".text"):
        # Try UTF-8 first, fall back to cp1256 (common Arabic encoding)
        try:
            return file_bytes.decode("utf-8")
        except UnicodeDecodeError:
            return file_bytes.decode("cp1256", errors="replace")
    elif ext == ".json":
        # Handle JSON files - convert to readable text
        try:
            import json
            data = json.loads(file_bytes.decode("utf-8"))
            # Convert JSON to readable text format
            return json.dumps(data, ensure_ascii=False, indent=2)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON file: {str(e)}")
    else:
        raise ValueError(f"Unsupported file type: {ext}. Supported: .pdf, .docx, .txt, .json")
