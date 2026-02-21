import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import 'bootstrap/dist/css/bootstrap.min.css';
import './App.css';

function App() {
  // Chat State
  const [messages, setMessages] = useState([]);
  const [inputText, setInputText] = useState('');
  const [loading, setLoading] = useState(false);
  const [selectedFile, setSelectedFile] = useState(null);
  const [healthStatus, setHealthStatus] = useState("Checking...");
  const [analysis, setAnalysis] = useState(null);
  const [showDetailedView, setShowDetailedView] = useState(false);
  
  const messagesEndRef = useRef(null);
  const API_BASE = "http://127.0.0.1:5000";

  // Scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Check health on mount
  useEffect(() => {
    checkHealth();
    const interval = setInterval(checkHealth, 5000);
    
    // Send greeting message
    if (messages.length === 0) {
      addAssistantMessage(
        "مرحباً! أنا مساعدك القانوني الذكي المتخصص في تحليل القضايا السعودية.\n\nللبدء، يمكنك:\n1. رفع ملف قضية (PDF, DOCX)\n2. لصق نص القضية مباشرة\n3. طرح أسئلة حول القضايا\n\n---\n\nHello! I'm your AI Legal Assistant specializing in Saudi legal case analysis.\n\nTo get started, you can:\n1. Upload a case file (PDF, DOCX)\n2. Paste case text directly\n3. Ask questions about cases",
        "greeting",
        []
      );
    }
    
    return () => clearInterval(interval);
  }, []);

  const checkHealth = async () => {
    try {
      const res = await axios.get(`${API_BASE}/health`);
      setHealthStatus("Connected ");
    } catch (err) {
      setHealthStatus("Disconnected ");
    }
  };

  const addUserMessage = (text) => {
    const newMessage = {
      id: Date.now(),
      role: 'user',
      content: text,
      timestamp: new Date().toISOString()
    };
    setMessages(prev => [...prev, newMessage]);
  };

  const addAssistantMessage = (text, intent = '', suggestedActions = []) => {
    const newMessage = {
      id: Date.now(),
      role: 'assistant',
      content: text,
      intent: intent,
      suggestedActions: suggestedActions,
      timestamp: new Date().toISOString()
    };
    setMessages(prev => [...prev, newMessage]);
  };

  const sendChatMessage = async (userMessage) => {
    if (!userMessage.trim()) return;

    // Add user message to chat
    addUserMessage(userMessage);
    setInputText('');
    setLoading(true);

    try {
      const response = await axios.post(`${API_BASE}/chat`, {
        message: userMessage,
        analysis_data: analysis,
        case_text: analysis ? "Case analyzed" : null
      });

      const { text, intent, suggested_actions } = response.data;
      addAssistantMessage(text, intent, suggested_actions);

    } catch (error) {
      console.error("Chat error:", error);
      addAssistantMessage(
        "عذراً، حدث خطأ في معالجة طلبك. يرجى المحاولة مجدداً.\n\nSorry, an error occurred. Please try again.",
        "error",
        []
      );
    } finally {
      setLoading(false);
    }
  };

  const handleFileChange = (e) => {
    if (e.target.files && e.target.files[0]) {
      setSelectedFile(e.target.files[0]);
    }
  };

  const handleFileUpload = async () => {
    if (!selectedFile) return;

    addUserMessage(` رفع ملف: ${selectedFile.name}\nUploading file: ${selectedFile.name}`);
    setLoading(true);
    setSelectedFile(null);

    const formData = new FormData();
    formData.append("file", selectedFile);

    try {
      const response = await axios.post(`${API_BASE}/upload-analyze`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });

      setAnalysis(response.data);

      addAssistantMessage(
        `تم تحليل الملف بنجاح! \n\nنوع القضية: ${response.data.classification.name_ar}\nدرجة الثقة: ${(response.data.classification.confidence * 100).toFixed(0)}%\n\n---\n\nFile analyzed successfully! \n\nCase Type: ${response.data.classification.name_en}\nConfidence: ${(response.data.classification.confidence * 100).toFixed(0)}%\n\nيمكنك الآن طرح أسئلة حول القضية أو...\nYou can now ask questions about the case or...`,
        "file_analyzed",
        [
          { label: "عرض التفاصيل الكاملة", action: "show_details" },
          { label: "ملخص القضية", action: "case_summary" },
          { label: "توصيات", action: "recommendations" }
        ]
      );

    } catch (error) {
      console.error("Upload error:", error);
      addAssistantMessage(
        `خطأ في رفع الملف: ${error.response?.data?.detail || error.message}\n\nFile upload error: ${error.response?.data?.detail || error.message}`,
        "error",
        []
      );
    } finally {
      setLoading(false);
    }
  };

  const handleSuggestedAction = (action) => {
    switch (action) {
      case "upload":
        document.getElementById("file-input").click();
        break;
      case "case_summary":
        sendChatMessage("ملخص القضية (case summary)");
        break;
      case "show_details":
        setShowDetailedView(!showDetailedView);
        break;
      case "recommendations":
        sendChatMessage("التوصيات (recommendations)");
        break;
      case "similar_cases":
        sendChatMessage("قضايا مشابهة (similar cases)");
        break;
      case "legal_principles":
        sendChatMessage("المبادئ القانونية (legal principles)");
        break;
      case "draft_claim":
        sendChatMessage("كتابة لائحة دعوى (write claim draft)");
        break;
      case "draft_defense":
        sendChatMessage("كتابة مذكرة دفاع (write defense memo)");
        break;
      default:
        sendChatMessage(action);
    }
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendChatMessage(inputText);
    }
  };

  return (
    <div className="chat-container" dir="rtl">
      {/* Header */}
      <div className="chat-header">
        <div className="header-content">
          <h1>️ المساعد القانوني الذكي</h1>
          <p>AI Legal Assistant v2.0</p>
        </div>
        <button
          className={`btn btn-sm ${healthStatus.includes("Connected") ? "btn-success" : "btn-danger"}`}
          onClick={checkHealth}
        >
          {healthStatus}
        </button>
      </div>

      {/* Messages Area */}
      <div className="chat-messages">
        {messages.map((msg) => (
          <div key={msg.id} className={`message message-${msg.role}`}>
            <div className="message-avatar">
              {msg.role === 'user' ? '' : '️'}
            </div>
            <div className="message-content">
              <div className="message-text">
                {msg.content}
              </div>
              
              {/* Suggested Actions */}
              {msg.suggestedActions && msg.suggestedActions.length > 0 && (
                <div className="suggested-actions mt-2">
                  {msg.suggestedActions.map((action, idx) => (
                    <button
                      key={idx}
                      className="btn btn-sm btn-outline-primary action-btn"
                      onClick={() => handleSuggestedAction(action.action)}
                      disabled={loading}
                    >
                      {action.label}
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>
        ))}
        {loading && (
          <div className="message message-assistant">
            <div className="message-avatar">️</div>
            <div className="message-content">
              <div className="typing-indicator">
                <span></span>
                <span></span>
                <span></span>
              </div>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Detailed View Modal */}
      {showDetailedView && analysis && (
        <div className="detailed-view-modal">
          <div className="detailed-view-content">
            <button 
              className="btn-close-modal"
              onClick={() => setShowDetailedView(false)}
            >
              
            </button>
            
            {/* Classification */}
            <div className="detail-card">
              <h5 className="detail-title">️ تصنيف القضية</h5>
              <p><strong>{analysis.classification.name_ar}</strong></p>
              <p className="text-muted">{analysis.classification.name_en}</p>
              <p className="small">درجة الثقة: {(analysis.classification.confidence * 100).toFixed(0)}%</p>
            </div>

            {/* Trends */}
            {analysis.trends && (
              <div className="detail-card">
                <h5 className="detail-title"> الإحصائيات</h5>
                <div className="row">
                  <div className="col-6">
                    <p className="stat-label">نسبة فوز المدعي</p>
                    <p className="stat-value">{analysis.trends.plaintiff_win_rate}%</p>
                  </div>
                  <div className="col-6">
                    <p className="stat-label">متوسط التعويض</p>
                    <p className="stat-value">{analysis.trends.average_compensation.toLocaleString()}</p>
                  </div>
                </div>
              </div>
            )}

            {/* Recommendation */}
            {analysis.recommendation && (
              <div className="detail-card">
                <h5 className="detail-title"> التوصية</h5>
                <p>{analysis.recommendation.recommendation_ar}</p>
                <p className="small text-muted mt-2">Confidence: {(analysis.recommendation.confidence * 100).toFixed(0)}%</p>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Input Area */}
      <div className="chat-input-area">
        <div className="input-actions">
          <input
            type="file"
            id="file-input"
            hidden
            onChange={handleFileChange}
            accept=".pdf,.docx,.txt"
          />
          <button
            className="btn btn-sm btn-outline-secondary"
            onClick={() => document.getElementById("file-input").click()}
            title="رفع ملف"
          >
            
          </button>
          
          {selectedFile && (
            <button
              className="btn btn-sm btn-success"
              onClick={handleFileUpload}
              disabled={loading}
            >
               {selectedFile.name}
            </button>
          )}
        </div>

        <div className="input-wrapper">
          <textarea
            className="chat-input"
            value={inputText}
            onChange={(e) => setInputText(e.target.value)}
            onKeyPress={handleKeyPress}
            placeholder="اكتب سؤالك... (Type your question...)"
            disabled={loading}
            rows="2"
          />
          <button
            className="btn-send"
            onClick={() => sendChatMessage(inputText)}
            disabled={loading || !inputText.trim()}
            title="إرسال"
          >
            
          </button>
        </div>
      </div>
    </div>
  );
}

export default App;
