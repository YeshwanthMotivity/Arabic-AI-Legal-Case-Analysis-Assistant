#  Quick Start - Chatbot Version

## Step 1: Start the Backend

```bash
cd backend
python main.py
```

**Expected Output:**
```
 System ready. All engines loaded successfully.
    Chat Engine: READY
    Similarity Engine: READY
    Summarizer Engine: READY
   ...
```

## Step 2: Start the Frontend

Open a **new terminal/command prompt**:

```bash
cd frontend
npm start
```

**Browser will open at:** `http://localhost:3000`

## Step 3: Start Chatting! 

### Upload a Case:
1. Click the  button
2. Select a PDF, DOCX, or TXT file
3. Bot analyzes automatically

### Or Ask Directly:
- Type in Arabic or English
- Bot understands legal case questions
- Get instant analysis and recommendations

---

## Example Prompts

**In Arabic:**
- "ملخص القضية" - Case summary
- "ما نوع هذه القضية؟" - What type of case?
- "قضايا مشابهة" - Similar cases
- "ما احتمالية النجاح؟" - Success probability?
- "كتابة لائحة دعوى" - Write claim draft

**In English:**
- "summarize the case" 
- "what's the classification?"
- "find similar cases"
- "legal principles"
- "success rate?"
- "generate draft"

---

## Features Available in Chat

 Case Analysis & Classification  
 Similar Case Search  
 Legal Principle Extraction  
 Trend Analysis & Statistics  
 Success Probability  
 Compensation Analysis  
 Legal Draft Generation  
 Multi-turn Conversations  
 Context Memory  
 Bilingual Support (AR/EN)  

---

## Troubleshooting

**Backend won't start?**
```bash
# Make sure dependencies are installed
pip install -r requirements.txt
```

**Frontend won't start?**
```bash
# Make sure npm packages are installed
npm install
```

**Chat not responding?**
- Check backend is running: http://127.0.0.1:5000/health
- Should say: "Connected "

---

## Documents

- **Full Guide:** See `CHATBOT_GUIDE.md` for complete documentation
- **Original README:** See `README.md` for system architecture

Enjoy your new legal chatbot! 
