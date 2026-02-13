import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import {
  Upload, Send, FileText, Sparkles, X,
  CheckCircle2, TrendingUp, Scale,
  Settings
} from 'lucide-react';
import './App.css';

function App() {
  // Chat State
  const [messages, setMessages] = useState([]);
  const [inputText, setInputText] = useState('');
  const [loading, setLoading] = useState(false);
  const [selectedFile, setSelectedFile] = useState(null);
  const [healthStatus, setHealthStatus] = useState("checking");
  const [analysis, setAnalysis] = useState(null);
  const [showDetailedView, setShowDetailedView] = useState(false);
  const [showSettings, setShowSettings] = useState(false);
  const [theme] = useState('light');

  const messagesEndRef = useRef(null);
  const fileInputRef = useRef(null);
  const greetingSent = useRef(false);
  const API_BASE = "http://127.0.0.1:5000";

  // Scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Check health on mount
  useEffect(() => {
    checkHealth();
    const interval = setInterval(checkHealth, 10000);

    // Send greeting message
    if (!greetingSent.current && messages.length === 0) {
      greetingSent.current = true;
      addAssistantMessage(
        "مرحباً بك! 👋 أنا مساعدك القانوني الذكي.\n\nيمكنني مساعدتك في:\n• 📊 تحليل القضايا (Case Analysis)\n• ⚖️ تصنيف القضايا (Classification)\n• 💡 التوصيات (Recommendations)\n• 🔍 البحث في السوابق (Precedent Search)\n\n---\n\nWelcome! 👋 I am your AI Legal Assistant.\n\nI can help you with:\n• Legal Case Analysis\n• Case Classification\n• Recommendations\n• Similar Case Interpretation",
        "greeting",
        [
          { label: "📤 رفع ملف قضية | Upload Case", action: "upload", icon: "upload" },
          { label: "💬 طرح سؤال | Ask Question", action: "ask_question", icon: "message" }
        ]
      );
    }

    return () => clearInterval(interval);
  }, []);

  const checkHealth = async () => {
    try {
      await axios.get(`${API_BASE}/health`, { timeout: 3000 });
      setHealthStatus("connected");
    } catch (err) {
      setHealthStatus("disconnected");
    }
  };

  const addUserMessage = (text, fileData = null) => {
    const newMessage = {
      id: Date.now(),
      role: 'user',
      content: text,
      fileData: fileData,
      timestamp: new Date().toISOString()
    };
    setMessages(prev => [...prev, newMessage]);
    return newMessage.id;
  };

  const addAssistantMessage = (text, intent = '', suggestedActions = [], citations = []) => {
    const newMessage = {
      id: Date.now(),
      role: 'assistant',
      content: text,
      intent: intent,
      suggestedActions: suggestedActions,
      citations: citations, // Explainability Layer
      timestamp: new Date().toISOString()
    };
    setMessages(prev => [...prev, newMessage]);
  };

  const sendChatMessage = async (userMessage) => {
    if (!userMessage.trim()) return;

    const userMsgId = addUserMessage(userMessage);
    setInputText('');
    setLoading(true);

    try {
      const response = await axios.post(`${API_BASE}/chat`, {
        message: userMessage,
        analysis_data: analysis,
        case_text: analysis ? "Case analyzed" : null
      });
      setHealthStatus("connected"); // Force status sync on success

      const { text, intent, suggested_actions, citations, user_translation } = response.data;

      // Update user message with translation if available
      if (user_translation) {
        setMessages(prev => prev.map(msg =>
          msg.id === userMsgId ? { ...msg, translation: user_translation } : msg
        ));
      }

      addAssistantMessage(text, intent, suggested_actions || [], citations || []);

    } catch (error) {
      console.error("Chat error:", error);
      addAssistantMessage(
        "عذراً، حدث خطأ في معالجة طلبك. يرجى المحاولة مجدداً.\n\nSorry, an error occurred processing your request.",
        "error",
        [{ label: "🔄 إعادة المحاولة", action: "retry" }]
      );
    } finally {
      setLoading(false);
    }
  };

  const handleFileChange = (e) => {
    if (e.target.files && e.target.files[0]) {
      const file = e.target.files[0];
      setSelectedFile(file);
    }
  };

  const handleFileUpload = async () => {
    if (!selectedFile) return;

    addUserMessage(`رفع الملف: ${selectedFile.name}`, {
      name: selectedFile.name,
      size: selectedFile.size
    });
    setLoading(true);

    const formData = new FormData();
    formData.append("file", selectedFile);

    try {
      const response = await axios.post(`${API_BASE}/upload-analyze`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });

      setAnalysis(response.data);
      setHealthStatus("connected"); // Force status sync on success
      setSelectedFile(null);

      addAssistantMessage(
        `✅ تم تحليل الملف بنجاح!\n\n📋 نوع القضية: ${response.data.classification.name_ar}\n\n---\n\n✅ File analyzed successfully!\n\n📋 Case Type: ${response.data.classification.name_en}`,
        "file_analyzed",
        [
          { label: "📊 Details | عرض التفاصيل", action: "show_details", icon: "details" },
          { label: "📝 Summary | ملخص القضية", action: "case_summary", icon: "summary" },
          { label: "💡 Recommendations | التوصيات", action: "recommendations", icon: "recommend" },
          { label: "🔍 Similar Cases | قضايا مشابهة", action: "similar_cases", icon: "search" }
        ]
      );

    } catch (error) {
      console.error("Upload error:", error);
      addAssistantMessage(
        `❌ خطأ في رفع الملف\n\n${error.response?.data?.detail || error.message}\n\nError uploading file`,
        "error",
        [{ label: "🔄 حاول مرة أخرى", action: "upload" }]
      );
    } finally {
      setLoading(false);
    }
  };

  const handleSuggestedAction = (action) => {
    switch (action) {
      case "upload":
        fileInputRef.current?.click();
        break;
      case "ask_question":
        document.querySelector('.chat-input')?.focus();
        break;
      case "case_summary":
        sendChatMessage("قدم لي ملخصاً شاملاً للقضية");
        break;
      case "show_details":
        setShowDetailedView(true);
        break;
      case "recommendations":
        sendChatMessage("ما هي التوصيات القانونية لهذه القضية؟");
        break;
      case "similar_cases":
        sendChatMessage("اعرض لي قضايا مشابهة");
        break;
      case "legal_principles":
        sendChatMessage("ما هي المبادئ القانونية المتعلقة بهذه القضية؟");
        break;
      case "retry":
        if (messages.length >= 2) {
          const lastUserMsg = [...messages].reverse().find(m => m.role === 'user');
          if (lastUserMsg) sendChatMessage(lastUserMsg.content);
        }
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

  const getStatusColor = () => {
    switch (healthStatus) {
      case 'connected': return '#10b981';
      case 'disconnected': return '#ef4444';
      default: return '#f59e0b';
    }
  };

  const getStatusText = () => {
    switch (healthStatus) {
      case 'connected': return 'متصل';
      case 'disconnected': return 'غير متصل';
      default: return 'جاري الفحص...';
    }
  };

  return (
    <div className={`app-container theme-${theme}`}>
      {/* Header */}
      <header className="app-header">
        <div className="header-left">
          <div className="logo-section">
            <div className="logo-icon">
              <Scale size={28} />
            </div>
            <div className="header-text">
              <h1>المساعد القانوني الذكي</h1>
              <p>AI Legal Assistant</p>
            </div>
          </div>
        </div>

        <div className="header-right">
          <div className="status-indicator">
            <div
              className="status-dot"
              style={{ backgroundColor: getStatusColor() }}
            />
            <span className="status-text">{getStatusText()}</span>
          </div>

          <button
            className="icon-btn"
            onClick={() => setShowSettings(!showSettings)}
            title="Settings"
          >
            <Settings size={20} />
          </button>
        </div>
      </header>

      {/* Main Chat Area */}
      <main className="chat-main">
        <div className="messages-container">
          {messages.map((msg) => (
            <div key={msg.id} className={`message-wrapper message-${msg.role}`}>
              <div className="message-avatar">
                {msg.role === 'user' ? (
                  <div className="avatar user-avatar">👤</div>
                ) : (
                  <div className="avatar assistant-avatar">
                    <Scale size={20} />
                  </div>
                )}
              </div>

              <div className="message-bubble">
                {msg.fileData && (
                  <div className="file-attachment">
                    <FileText size={16} />
                    <span>{msg.fileData.name}</span>
                    <span className="file-size">
                      ({(msg.fileData.size / 1024).toFixed(1)} KB)
                    </span>
                  </div>
                )}

                <div className="message-content">
                  {msg.content && msg.content.includes("---") ? (
                    (() => {
                      const parts = msg.content.split("---");
                      const arabicText = parts[0].trim();
                      const englishText = parts.slice(1).join("---").trim();
                      return (
                        <>
                          <div className="text-arabic" dir="rtl">{arabicText}</div>
                          <div className="translation-separator"></div>
                          <div className="text-english" dir="ltr">{englishText}</div>
                        </>
                      );
                    })()
                  ) : (
                    <>
                      <div className="message-text">
                        {msg.content}
                      </div>
                      {msg.translation && (
                        <>
                          <div className="translation-separator"></div>
                          <div className="text-english" dir="ltr">{msg.translation}</div>
                        </>
                      )}
                    </>
                  )}
                </div>

                {/* Explainability Layer: Citations */}
                {msg.citations && msg.citations.length > 0 && (
                  <div className="citations-footer mt-3 pt-2 border-top border-secondary-subtle">
                    <h6 className="small text-muted mb-2" style={{ fontSize: '0.75rem', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                      📚 Sources Used | المصادر:
                    </h6>
                    <div className="d-flex flex-wrap gap-2">
                      {msg.citations.map((cite, idx) => (
                        <div key={idx} className="citation-card p-2 bg-white rounded border" style={{ minWidth: '180px', maxWidth: '100%', flex: '1 1 auto', boxShadow: '0 1px 2px rgba(0,0,0,0.05)' }}>
                          <div className="d-flex justify-content-between align-items-center mb-1">
                            <span className="badge bg-light text-dark border">{cite.source}</span>
                            <span className="badge bg-success-subtle text-success small">Art. {cite.article_number}</span>
                          </div>
                          <p className="small text-secondary mb-0 text-end" style={{ fontSize: '0.8rem', lineHeight: '1.4', maxHeight: '60px', overflow: 'hidden' }} title={cite.text}>
                            {cite.text}
                          </p>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {msg.suggestedActions && msg.suggestedActions.length > 0 && (
                  <div className="action-buttons">
                    {msg.suggestedActions.map((action, idx) => (
                      <button
                        key={idx}
                        className="action-chip"
                        onClick={() => handleSuggestedAction(action.action)}
                        disabled={loading}
                      >
                        {action.label}
                      </button>
                    ))}
                  </div>
                )}

                <div className="message-time">
                  {new Date(msg.timestamp).toLocaleTimeString('ar-SA', {
                    hour: '2-digit',
                    minute: '2-digit'
                  })}
                </div>
              </div>
            </div>
          ))}

          {loading && (
            <div className="message-wrapper message-assistant">
              <div className="message-avatar">
                <div className="avatar assistant-avatar">
                  <Scale size={20} />
                </div>
              </div>
              <div className="message-bubble typing-bubble">
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
      </main>

      {/* Input Area */}
      <footer className="chat-footer">
        {selectedFile && (
          <div className="file-preview">
            <div className="file-info">
              <FileText size={18} />
              <span className="file-name">{selectedFile.name}</span>
              <span className="file-size">
                {(selectedFile.size / 1024).toFixed(1)} KB
              </span>
            </div>
            <div className="file-actions">
              <button
                className="btn-upload"
                onClick={handleFileUpload}
                disabled={loading}
              >
                <Upload size={16} />
                تحليل
              </button>
              <button
                className="btn-cancel"
                onClick={() => setSelectedFile(null)}
              >
                <X size={16} />
              </button>
            </div>
          </div>
        )}

        <div className="input-container">
          <input
            type="file"
            ref={fileInputRef}
            onChange={handleFileChange}
            accept=".pdf,.docx,.txt"
            style={{ display: 'none' }}
          />

          <button
            className="attach-btn"
            onClick={() => fileInputRef.current?.click()}
            disabled={loading}
            title="إرفاق ملف"
          >
            <Upload size={20} />
          </button>

          <textarea
            className="chat-input"
            value={inputText}
            onChange={(e) => setInputText(e.target.value)}
            onKeyPress={handleKeyPress}
            placeholder="اكتب سؤالك هنا... (Type your question here...)"
            disabled={loading}
            rows="1"
          />

          <button
            className="send-btn"
            onClick={() => sendChatMessage(inputText)}
            disabled={loading || !inputText.trim()}
            title="إرسال"
          >
            <Send size={20} />
          </button>
        </div>
      </footer>

      {/* Detailed Analysis Modal */}
      {showDetailedView && analysis && (
        <div className="modal-overlay" onClick={() => setShowDetailedView(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2>
                <Sparkles size={24} />
                Detailed Case Analysis | تحليل القضية التفصيلي
              </h2>
              <button
                className="modal-close"
                onClick={() => setShowDetailedView(false)}
              >
                <X size={24} />
              </button>
            </div>

            <div className="modal-body">
              {/* Classification Card */}
              <div className="info-card">
                <div className="card-header">
                  <FileText size={20} />
                  <h3>Case Classification | تصنيف القضية</h3>
                </div>
                <div className="card-body">
                  <div className="classification-info">
                    <div className="classification-name">
                      <p className="arabic">{analysis.classification.name_ar}</p>
                      <p className="english">{analysis.classification.name_en}</p>
                    </div>
                  </div>
                </div>
              </div>

              {/* Statistics Card */}
              {analysis.trends && (
                <div className="info-card">
                  <div className="card-header">
                    <TrendingUp size={20} />
                    <h3>Statistics & Trends | الإحصائيات والاتجاهات</h3>
                  </div>
                  <div className="card-body">
                    <div className="stats-grid">
                      <div className="stat-item">
                        <div className="stat-label">Plaintiff Win Rate | نسبة فوز المدعي</div>
                        <div className="stat-value success">
                          {analysis.trends.plaintiff_win_rate}%
                        </div>
                      </div>
                      <div className="stat-item">
                        <div className="stat-label">Average Compensation | متوسط التعويض</div>
                        <div className="stat-value primary">
                          {analysis.trends.average_compensation.toLocaleString()} ر.س
                        </div>
                      </div>
                      {analysis.trends.median_duration && (
                        <div className="stat-item">
                          <div className="stat-label">Average Duration | متوسط المدة</div>
                          <div className="stat-value">
                            {analysis.trends.median_duration} يوم
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              )}

              {/* Recommendation Card */}
              {analysis.recommendation && (
                <div className="info-card recommendation-card">
                  <div className="card-header">
                    <CheckCircle2 size={20} />
                    <h3>Legal Recommendation | التوصية القانونية</h3>
                  </div>
                  <div className="card-body">
                    <p className="recommendation-text">
                      {analysis.recommendation.recommendation_ar}
                    </p>
                    <p className="recommendation-text english" style={{ fontStyle: 'italic', opacity: 0.8, fontSize: '0.9rem', borderTop: '1px solid #eee', marginTop: '10px', paddingTop: '10px' }}>
                      {analysis.recommendation.recommendation_en}
                    </p>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )
      }
    </div >
  );
}

export default App;
