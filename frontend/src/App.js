import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import './App.css';
import { Layout } from './components/Layout';
import { Header } from './components/Header';
import { Sidebar } from './components/Sidebar';
import { Message } from './components/Message';
import { ChatInput } from './components/ChatInput';
import { ToolsPanel } from './components/ToolsPanel';
import { JudicialInsightsPanel } from './components/JudicialInsightsPanel';
import { ThinkingIndicator } from './components/StateIndicators';
import { SettingsModal } from './components/SettingsModal';
import { RelatedCaseModal } from './components/RelatedCaseModal';
import { jsPDF } from 'jspdf';
import { PanelLeft, PanelRight } from 'lucide-react';
import { getStorageItem, setStorageItem, isStorageAvailable } from './utils/storage';
import { getUiText } from './i18n/uiText';

// === AXIOS CONFIGURATION ===
const API_TIMEOUT_MS = Number(process.env.REACT_APP_API_TIMEOUT_MS || 300000);
axios.defaults.timeout = API_TIMEOUT_MS; // Default 5 minutes for local LLM workloads

// Define API_BASE — uses nginx proxy (/api → http://localhost:5000)
const API_BASE = "http://127.0.0.1:5000";  // local dev direct
// const API_BASE = "/api";

// Create axios instance with defaults
const apiClient = axios.create({
  baseURL: API_BASE,
  timeout: API_TIMEOUT_MS,
  headers: {
    'Content-Type': 'application/json',
  }
});

// Add request interceptor for error handling
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.code === 'ECONNABORTED') {
      console.error('Request timeout - backend not responding');
      return Promise.reject(new Error('Request timeout. Server is not responding. Please try again.'));
    }
    return Promise.reject(error);
  }
);

// ===== ERROR BOUNDARY COMPONENT =====
class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = {
      hasError: false,
      error: null,
      errorInfo: null
    };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true };
  }

  componentDidCatch(error, errorInfo) {
    // Log to console for debugging
    console.error('ErrorBoundary caught:', error, errorInfo);

    // Update state to show error UI
    this.setState({
      error,
      errorInfo
    });

    // Optional: Send to error tracking service (e.g., Sentry)
    // logErrorToService(error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div style={{
          padding: '20px',
          textAlign: 'center',
          backgroundColor: '#ffe6e6',
          color: '#cc0000',
          minHeight: '100vh',
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'center',
          alignItems: 'center',
          fontFamily: 'Arial, sans-serif'
        }}>
          <h1>️ Something Went Wrong</h1>
          <p>The application encountered an error. Please refresh the page to continue.</p>

          {process.env.NODE_ENV === 'development' && this.state.error && (
            <details style={{
              textAlign: 'left',
              backgroundColor: '#f5f5f5',
              padding: '10px',
              borderRadius: '5px',
              marginTop: '20px',
              maxWidth: '600px'
            }}>
              <summary>Error Details (Development Only)</summary>
              <pre style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
                {this.state.error.toString()}
                {this.state.errorInfo?.componentStack}
              </pre>
            </details>
          )}

          <button
            onClick={() => window.location.reload()}
            style={{
              marginTop: '20px',
              padding: '10px 20px',
              backgroundColor: '#0066cc',
              color: 'white',
              border: 'none',
              borderRadius: '5px',
              cursor: 'pointer'
            }}
          >
            Refresh Page
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}

function App() {
  // ... existing code ...
  // Chat State
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);
  const [selectedFile, setSelectedFile] = useState(null);
  const [healthStatus, setHealthStatus] = useState("checking");
  const [analysis, setAnalysis] = useState(null);
  const [panels, setPanels] = useState({ sidebar: true, tools: true, insights: false });

  const togglePanel = (panelName) => {
    setPanels(prev => ({ ...prev, [panelName]: !prev[panelName] }));
  };

  // Settings State
  const [showSettings, setShowSettings] = useState(false);
  const [fontSize, setFontSize] = useState(() => getStorageItem('fontSize', 'medium'));
  const [language, setLanguage] = useState(() => getStorageItem('language', 'ar'));
  const [viewingCase, setViewingCase] = useState(null);
  const uiText = getUiText(language);

  const getGreetingPayload = () => {
    const arUi = getUiText('ar');
    const enUi = getUiText('en');
    return {
      text: `${arUi.emptyWelcomeTitle}\n\n${arUi.emptyWelcomeSubtitle}`,
      translation: `${enUi.emptyWelcomeTitle}\n\n${enUi.emptyWelcomeSubtitle}`,
      actions: [
        { label: 'Upload Case | \u0631\u0641\u0639 \u0642\u0636\u064a\u0629', action: 'upload' },
        { label: 'Paste Text | \u0644\u0635\u0642 \u0646\u0635', action: 'paste_text' }
      ]
    };
  };

  const pushGreetingMessage = () => {
    const greeting = getGreetingPayload();
    addAssistantMessage(greeting.text, 'greeting', [], greeting.translation, greeting.actions);
  };

  // Conversation management
  const [conversations, setConversations] = useState([]);
  const [currentConversationId, setCurrentConversationId] = useState(null);

  // Load conversation list from backend on mount
  useEffect(() => {
    const fetchConversations = async () => {
      try {
        const response = await apiClient.get('/conversations');
        setConversations(response.data);
      } catch (error) {
        console.error("Failed to load conversations:", error);
      }
    };
    fetchConversations();
  }, []);

  const messagesEndRef = useRef(null);
  const greetingSent = useRef(false);
  // API_BASE is now defined at module level for apiClient


  // Scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);



  // Check health on mount with lifecycle management
  useEffect(() => {
    checkHealth(); // Initial check

    // Poll every 30 seconds only if visible
    const interval = setInterval(() => {
      if (document.visibilityState === 'visible') {
        checkHealth();
      }
    }, 30000);

    // Immediate check when returning to tab
    const handleVisibilityChange = () => {
      if (document.visibilityState === 'visible') {
        checkHealth();
      }
    };

    document.addEventListener('visibilitychange', handleVisibilityChange);

    return () => {
      clearInterval(interval);
      document.removeEventListener('visibilitychange', handleVisibilityChange);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Send greeting message only once
  useEffect(() => {
    if (!greetingSent.current && messages.length === 0) {
      greetingSent.current = true;
      pushGreetingMessage();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Theme Management
  const [theme, setTheme] = useState(() => getStorageItem('theme', 'light'));

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    setStorageItem('theme', theme);
  }, [theme]);

  // Font Size Management
  useEffect(() => {
    document.documentElement.setAttribute('data-font-size', fontSize);
    setStorageItem('fontSize', fontSize);
  }, [fontSize]);

  // Language Management
  useEffect(() => {
    document.documentElement.setAttribute('data-language', language);
    document.documentElement.setAttribute('lang', language === 'ar' ? 'ar' : 'en');
    document.documentElement.setAttribute('dir', 'rtl');
    setStorageItem('language', language);
  }, [language]);

  // ------------------------------------------------------------------
  // PERSISTENCE LOGIC (Debounced Save)
  // ------------------------------------------------------------------
  useEffect(() => {
    if (!currentConversationId || messages.length === 0) return;

    const saveConversation = async () => {
      try {
        console.log('[PERSIST_START] Saving conversation:', currentConversationId);

        // Prepare payload with safe defaults
        const cleanMessages = messages.map(m => ({
          ...m,
          fileData: m.fileData || null,
          citations: m.citations || [],
          suggested_actions: m.suggested_actions || []
        }));

        // Determine title
        const existingConv = conversations.find(c => c.id === currentConversationId);
        let title = existingConv?.title || "محادثة جديدة";
        let preview = "محادثة نصية";

        // Auto-generate title from first user message if Untitled
        if ((!title || title === "محادثة جديدة") && messages.some(m => m.role === 'user')) {
          const firstUserMsg = messages.find(m => m.role === 'user');
          if (firstUserMsg) {
            title = firstUserMsg.content.substring(0, 40) + (firstUserMsg.content.length > 40 ? '...' : '');
            preview = firstUserMsg.content.substring(0, 60);
          }
        }

        // If analysis exists, use its classification as title
        if (analysis && analysis.classification) {
          title = analysis.classification.name_ar;
          preview = `درجة الثقة: ${(analysis.classification.confidence * 100).toFixed(0)}%`;
        }

        console.log('[PERSIST_SEND] Posting conversation to backend:', { id: currentConversationId, title, preview });

        const saveResponse = await apiClient.post('/conversations', {
          id: String(currentConversationId),
          title: title,
          preview: preview,
          messages: cleanMessages,
          analysis: analysis || null
        });

        console.log('[PERSIST_RESPONSE] Backend confirmed:', saveResponse.data);

        if (saveResponse.data.verification === 'verified') {
          console.log('[PERSIST_VERIFIED] Conversation saved and verified by backend');

          // Update local list to match (optimistic update)
          // Update local list with backend data (including summary)
          const savedSummary = saveResponse.data.summary;

          setConversations(prev => {
            const exists = prev.find(c => c.id === currentConversationId);
            if (exists) {
              console.log('[PERSIST_UPDATE_EXISTING] Updating existing conversation in list', savedSummary);
              return prev.map(c => c.id === currentConversationId ? {
                ...c,
                title,
                preview,
                timestamp: new Date().toISOString(),
                summary: savedSummary // Update summary from backend
              } : c);
            } else {
              console.log('[PERSIST_ADD_NEW] Adding new conversation to list');
              return [{
                id: currentConversationId,
                title,
                preview,
                timestamp: new Date().toISOString(),
                archived: false,
                summary: savedSummary // Add summary from backend
              }, ...prev];
            }
          });

          console.log('[PERSIST_SUCCESS] Conversation persistence complete');
        } else {
          console.warn('[PERSIST_WARNING] Backend did not return verification flag', saveResponse.data);
        }

      } catch (error) {
        console.error('[PERSIST_ERROR] Failed to save conversation:', error);

        // Provide user feedback about save failure
        if (error.response?.status === 500) {
          console.error('[PERSIST_ERROR] Server error - conversation may not be saved');
        } else if (error.message.includes('timeout')) {
          console.error('[PERSIST_ERROR] Save timeout - server not responding');
        }
      }
    };

    // Debounce save to avoid spamming backend on every keystroke/token
    const timeoutId = setTimeout(saveConversation, 1000);
    return () => clearTimeout(timeoutId);

    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [messages, analysis, currentConversationId]);

  const toggleTheme = () => {
    setTheme(prev => prev === 'light' ? 'dark' : 'light');
  };

  const handleFontSizeChange = (size) => {
    setFontSize(size);
  };

  const checkHealth = async () => {
    try {
      await apiClient.get('/health');
      setHealthStatus("connected");
    } catch (err) {
      setHealthStatus(err.message.includes('timeout') ? "timeout" : "disconnected");
    }
  };

  // eslint-disable-next-line no-unused-vars
  const refreshConversationList = async () => {
    // Explicitly refresh the conversation list from backend
    try {
      console.log('[REFRESH_LIST] Manually refreshing conversation list from backend');
      const response = await apiClient.get('/conversations');
      console.log('[REFRESH_LIST_SUCCESS] Retrieved', response.data.length, 'conversations');
      setConversations(response.data);
      return response.data;
    } catch (error) {
      console.error('[REFRESH_LIST_ERROR] Failed to refresh conversation list:', error);
      return null;
    }
  };

  const handleClearData = () => {
    setMessages([]);
    setConversations([]);
    setAnalysis(null);
    setSelectedFile(null);
    setCurrentConversationId(null);
    greetingSent.current = false;

    // Call backend to wipe DB
    apiClient.delete('/conversations').catch(err => console.error("Failed to clear backend history:", err));

    // Also clear backend context
    apiClient.post('/chat/clear', { confirm: true }).catch(err => console.error(err));


    // Send greeting again after clear
    setTimeout(() => {
      pushGreetingMessage();
    }, 500);

    setShowSettings(false);
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

  const addAssistantMessage = (text, intent = '', citations = [], translation = null, suggestedActions = [], parentMsgId = null) => {
    if (parentMsgId) {
      setMessages(prev => prev.map(msg => {
        if (msg.id === parentMsgId) {
          return {
            ...msg,
            content: msg.content + "\n\n---\n\n" + text,
            citations: [...(msg.citations || []), ...citations],
            suggested_actions: suggestedActions
          };
        }
        return msg;
      }));
      return;
    }

    const newMessage = {
      id: Date.now(),
      role: 'assistant',
      content: text,
      translation: translation,
      intent: intent,
      citations: citations,
      suggested_actions: suggestedActions,
      timestamp: new Date().toISOString()
    };
    setMessages(prev => [...prev, newMessage]);
  };

  const sendChatMessage = async (userMessage, displayMessage = null, parentMsgId = null) => {
    if (!userMessage.trim()) return;

    let fileData = null;
    let shownMessage = userMessage;

    // Check if displayMessage is a File object (from ChatInput)
    if (displayMessage && typeof displayMessage === 'object' && displayMessage.name) {
      fileData = {
        name: displayMessage.name,
        size: displayMessage.size,
        type: displayMessage.type
      };
      // Preserve the user's text message
      shownMessage = userMessage;
    } else if (displayMessage) {
      // Fallback for string display overrides
      shownMessage = displayMessage.toString().trim();
    }

    let msgId = null;
    if (!parentMsgId) {
      msgId = addUserMessage(shownMessage, fileData);
    }
    setLoading(true);

    try {
      const response = await apiClient.post('/chat', {
        message: userMessage,
        analysis_data: analysis,
        case_text: analysis?.text || null,
        language: language
      });
      setHealthStatus("connected");

      const { text, citations, user_translation, assistant_translation, suggested_actions, intent: respIntent, analysis_data: respAnalysis } = response.data;

      // Update analysis context if backend provides an updated one (auto-analysis)
      if (respAnalysis) {
        setAnalysis(respAnalysis);
      }

      // Update user message with translation if available
      if (user_translation && msgId) {
        setMessages(prev => prev.map(msg =>
          msg.id === msgId ? { ...msg, translation: user_translation } : msg
        ));
      }

      addAssistantMessage(text, respIntent || '', citations || [], assistant_translation, suggested_actions || [], parentMsgId);

      // If this was the first message of a new chat, ensure ID is set before saving
      if (!currentConversationId) {
        const newId = Date.now().toString();
        setCurrentConversationId(newId);
        // The useEffect hook will pick this up and save to backend
      }


    } catch (error) {
      console.error("Chat error:", error);

      let errorMessage = language === 'ar'
        ? "عذراً، حدث خطأ في معالجة طلبك."
        : "Sorry, an error occurred processing your request.";
      if (error.message.includes('timeout')) {
        errorMessage = language === 'ar'
          ? "انتهت مهلة الاتصال. الخادم لا يستجيب."
          : "Connection timeout. Server is not responding.";
        setHealthStatus("timeout");
      } else {
        setHealthStatus("error");
      }

      addAssistantMessage(
        errorMessage,
        "error",
        [],
        null,
        [
          { label: language === 'ar' ? 'حاول مرة أخرى' : 'Try Again', action: "retry" },
          { label: language === 'ar' ? 'رفع قضية' : 'Upload Case', action: "upload" }
        ]
      );
    } finally {
      setLoading(false);
    }
  };

  const handleFileUpload = async (file) => {
    setSelectedFile(file);
    addUserMessage(`${language === 'ar' ? 'رفع الملف' : 'Uploaded file'}: ${file.name}`, {
      name: file.name,
      size: file.size
    });
    setLoading(true);

    const formData = new FormData();
    formData.append("file", file);

    try {
      const response = await apiClient.post('/upload-analyze', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });

      setAnalysis(response.data);
      setHealthStatus("connected");
      setSelectedFile(null);

      const confidence = (response.data.classification.confidence * 100).toFixed(0);

      const caseType = language === 'ar'
        ? response.data.classification.name_ar
        : response.data.classification.name_en;
      const fileAnalyzedMessage = language === 'ar'
        ? `تم تحليل الملف بنجاح!\n\nنوع القضية: ${caseType}\nدرجة الثقة: ${confidence}%`
        : `File analyzed successfully!\n\nCase type: ${caseType}\nConfidence: ${confidence}%`;
      addAssistantMessage(fileAnalyzedMessage, "file_analyzed");

      // Add to conversations if new
      if (!currentConversationId) {
        const newConvId = String(Date.now());
        setCurrentConversationId(newConvId);
        // useEffect will handle saving this new conversation state to backend
      }


    } catch (error) {
      console.error("Upload error:", error);
      const uploadError = error.response?.data?.detail || error.message;
      const uploadErrorMessage = language === 'ar'
        ? `خطأ في رفع الملف\n\n${uploadError}`
        : `Error uploading file\n\n${uploadError}`;
      addAssistantMessage(uploadErrorMessage, "error");
    } finally {
      setLoading(false);
    }
  };

  const handleNewChat = () => {
    // Reset backend context
    apiClient.post('/chat/clear', { confirm: true }).catch(err => console.error(err));

    setCurrentConversationId(null);
    setMessages([]);
    setAnalysis(null);
    setSelectedFile(null);
    greetingSent.current = false;

    // Trigger greeting again
    setTimeout(() => {
      pushGreetingMessage();
    }, 100);
  };

  const handleSelectConversation = async (convId) => {
    try {
      setLoading(true);
      // Fetch full conversation details from backend
      const response = await apiClient.get(`/conversations/${convId}`);
      const { messages: loadedMessages, analysis: loadedAnalysis } = response.data;

      setCurrentConversationId(convId);
      setMessages(loadedMessages || []);
      setAnalysis(loadedAnalysis || null);

      // Mark greeting as sent if we have messages so it doesn't re-trigger
      if (loadedMessages && loadedMessages.length > 0) {
        greetingSent.current = true;
      }
    } catch (error) {
      console.error("Failed to load conversation:", error);
    } finally {
      setLoading(false);
    }
  };


  const handleDeleteConversation = async (convId) => {
    setConversations(prev => prev.filter(c => c.id !== convId));

    try {
      await apiClient.delete(`/conversations/${convId}`);
    } catch (err) {
      console.error("Failed to delete conversation:", err);
    }

    if (currentConversationId === convId) {
      handleNewChat();
    }
  };


  const handleArchiveConversation = async (convId) => {
    // 1. Optimistic UI update
    setConversations(prev =>
      prev.map(c => c.id === convId ? { ...c, archived: true } : c)
        .filter(c => !c.archived)
    );

    // 2. Call backend to soft delete
    try {
      await apiClient.delete(`/conversations/${convId}`); // Using delete for now as archive endpoint logic was generic
      console.log("Conversation archived/deleted on backend");
    } catch (error) {
      console.error("Failed to archive conversation:", error);
    }
  };

  const extractLocalizedLabel = (label, fallbackAction) => {
    const raw = (label || '').toString();
    if (!raw) return fallbackAction || '';
    const parts = raw.split('|').map(p => p.trim()).filter(Boolean);
    const arabicPart = parts.find(p => /[\u0600-\u06FF]/.test(p));
    const englishPart = parts.find(p => !/[\u0600-\u06FF]/.test(p));
    if (language === 'ar') return arabicPart || parts[0] || fallbackAction || '';
    return englishPart || parts[0] || fallbackAction || '';
  };

  const handleSuggestedAction = (action, label, parentMsgId) => {
    const normalizedAction = (action || '').toString().trim().toLowerCase();
    const localizedLabel = extractLocalizedLabel(label, normalizedAction);
    console.log("Suggested action clicked:", normalizedAction, label, parentMsgId);

    switch (normalizedAction) {
      case 'upload':
        // Trigger file input or show prompt
        document.querySelector('input[type="file"]')?.click();
        break;
      case 'paste_text':
      case 'learn_more':
      case 'full_analysis':
      case 'similar_cases':
      case 'recommendations':
      case 'draft_claim':
      case 'draft_defense':
      case 'draft_appeal':
      case 'draft_enforcement':
      case 'legal_principles':
      case 'trends':
      case 'case_summary':
      case 'outcome':
      case 'compensation':
      case 'entities':
        // Send the action string directly to trigger exact intent matching
        sendChatMessage(normalizedAction, localizedLabel, parentMsgId);
        break;
      default:
        sendChatMessage(normalizedAction || label || '', localizedLabel, parentMsgId);
        break;
    }
  };

  const handleMessageAction = (msgId, action) => {
    const message = messages.find(m => m.id === msgId);
    if (!message) return;

    switch (action) {
      case 'copy':
        navigator.clipboard.writeText(message.content);
        break;
      case 'regenerate':
        sendChatMessage(message.content);
        break;
      default:
        break;
    }
  };

  return (
    <Layout showSidebar={panels.sidebar} showTools={panels.tools} showInsights={panels.insights}>
      {!isStorageAvailable() && (
        <div style={{
          padding: '10px',
          backgroundColor: '#fff3cd',
          color: '#856404',
          textAlign: 'center',
          borderBottom: '1px solid #ffeeba'
        }}>
          ️ Storage disabled (private mode or quota exceeded). Data may not persist.
        </div>
      )}
      {/* Header */}
      <Header
        healthStatus={healthStatus}
        onSettings={() => setShowSettings(true)}
        onToggleInsights={() => togglePanel('insights')}
        insightsVisible={panels.insights}
        language={language}
        onToggleLanguage={() => setLanguage(prev => (prev === 'ar' ? 'en' : 'ar'))}
        text={uiText}
      />

      {/* Sidebar - Conversations */}
      <Sidebar
        conversations={conversations}
        currentId={currentConversationId}
        onNewChat={handleNewChat}
        onSelect={handleSelectConversation}
        onDelete={handleDeleteConversation}
        onArchive={handleArchiveConversation}
        onClearHistory={handleClearData}
        language={language}
        text={uiText}
      />

      {/* Main Content Area */}
      <main className="app-main">
        {/* Edge Toggle Buttons */}
        <button
          className={`edge-toggle sidebar-trigger ${!panels.sidebar ? 'collapsed' : ''}`}
          onClick={() => togglePanel('sidebar')}
          title={panels.sidebar ? uiText.toggleSidebarHide : uiText.toggleSidebarShow}
        >
          <PanelRight size={18} />
        </button>

        <button
          className={`edge-toggle tools-trigger ${!panels.tools && !panels.insights ? 'collapsed' : ''}`}
          onClick={() => {
            if (panels.insights && !panels.tools) { togglePanel('insights'); }
            else { togglePanel('tools'); }
          }}
          title={panels.tools || panels.insights ? uiText.toggleToolsHide : uiText.toggleToolsShow}
        >
          <PanelLeft size={18} />
        </button>

        <div className="chat-messages-container">
          {messages.length === 0 ? (
            <div className="chat-empty-state">
              <div className="chat-empty-icon"></div>
              <h2 className="chat-empty-title">{uiText.emptyWelcomeTitle}</h2>
              <p className="chat-empty-subtitle">{uiText.emptyWelcomeSubtitle}</p>
            </div>
          ) : (
            messages.map((msg) => (
              <Message
                key={msg.id}
                message={msg}
                language={language}
                onCopy={() => handleMessageAction(msg.id, 'copy')}
                onRegenerate={() => handleMessageAction(msg.id, 'regenerate')}
                onFeedback={(id, type) => console.log('Feedback:', id, type)}
                onActionClick={handleSuggestedAction}
                showActions={msg.role === 'assistant'}
              />
            ))
          )}

          {/* Loading State */}
          {loading && (
            <div className="chat-loading-wrapper">
              <div className="chat-loading-icon"></div>
              <div className="thinking-text">
                <ThinkingIndicator message={uiText.loadingText} />
                <div className="en-tiny">{uiText.loadingText}</div>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Chat Input */}
        <ChatInput
          onSend={sendChatMessage}
          onFileUpload={handleFileUpload}
          disabled={loading}
          maxChars={2000}
          showSlashCommands={true}
          language={language}
        />
      </main>

      {/* Judicial Insights Panel */}
      {panels.insights && (
        <JudicialInsightsPanel
          analysis={analysis}
          language={language}
          text={uiText}
        />
      )}

      {/* Tools Panel */}
      {panels.tools && (
        <ToolsPanel
          uploadedCase={analysis ? {
            name: selectedFile?.name || uiText.uploadedCaseName,
            type: analysis.classification.name_ar,
            pages: messages.filter(m => m.fileData).length > 0 ? 'متعدد' : '1',
            timestamp: new Date().toISOString(),
            keywords: [
              analysis.classification.name_ar,
              uiText.uploadedCaseTypeKeyword
            ]
          } : null}
          relatedCases={analysis?.related_cases || []}
          onExport={() => {
            try {
              const doc = new jsPDF();

              // Document Setup
              doc.setFontSize(18);
              doc.text("Legal Case Analysis", 10, 10);

              doc.setFontSize(10);
              doc.text(`Generated: ${new Date().toLocaleString()}`, 10, 20);
              doc.line(10, 22, 200, 22); // Horizontal line

              let y = 30;
              const lineHeight = 7;
              const pageHeight = doc.internal.pageSize.height;
              const maxWidth = 190;

              // 1. Case Info
              if (analysis) {
                doc.setFontSize(14);
                doc.text("Case Details", 10, y);
                y += 8;

                doc.setFontSize(11);
                doc.text(`Title: ${analysis.classification.name_ar}`, 10, y);
                y += lineHeight;
                doc.text(`Type: ${analysis.classification.name_en}`, 10, y);
                y += lineHeight;
                doc.text(`File: ${selectedFile?.name || 'N/A'}`, 10, y);
                y += 15;
              }

              // 2. Chat History
              doc.setFontSize(14);
              doc.text("Conversation History", 10, y);
              y += 10;

              doc.setFontSize(10);

              messages.forEach((msg) => {
                if (y > pageHeight - 20) { doc.addPage(); y = 20; }
                doc.setFont(undefined, 'bold');
                const role = msg.role === 'user' ? 'User' : 'Assistant';
                doc.text(`${role}:`, 10, y);
                y += 5;

                doc.setFont(undefined, 'normal');
                const splitText = doc.splitTextToSize(msg.content, maxWidth);
                splitText.forEach(line => {
                  if (y > pageHeight - 10) { doc.addPage(); y = 20; }
                  doc.text(line, 10, y);
                  y += 5;
                });
                y += 10;
              });

              doc.save(`case-analysis-${currentConversationId || Date.now()}.pdf`);
            } catch (err) {
              console.error("PDF Export failed:", err);
              alert(uiText.exportFail);
            }
          }}
          onRegenerate={() => {
            const lastUserMessage = messages.filter(m => m.role === 'user').pop();
            if (lastUserMessage) {
              sendChatMessage(lastUserMessage.content);
            }
          }}
          onCopyAll={() => {
            const content = messages.map(m => `${m.role}: ${m.content}`).join('\n\n');
            navigator.clipboard.writeText(content);
          }}
          onViewCase={(caseId) => {
            const rawCase = analysis?.related_cases?.find(rc => (rc.case?.case_id === caseId || rc.id === caseId));

            if (rawCase && rawCase.case) {
              setViewingCase({
                id: rawCase.case.case_id,
                title: rawCase.case.case_id,
                type: rawCase.case.court,
                year: '2024',
                similarity: rawCase.similarity_score / 100,
                preview: rawCase.preview || rawCase.case.facts.substring(0, 300) + '...',
                principles: [rawCase.case.legal_reasoning.substring(0, 300) + "..."]
              });
            } else if (rawCase) {
              setViewingCase(rawCase);
            } else {
              setViewingCase({
                id: caseId,
                title: uiText.fallbackCaseTitle,
                type: uiText.fallbackCaseType,
                year: '2024',
                similarity: 0.85,
                abstract: uiText.fallbackCaseAbstract,
                principles: [
                  uiText.fallbackPrinciple1,
                  uiText.fallbackPrinciple2,
                  uiText.fallbackPrinciple3
                ]
              });
            }
          }}
          language={language}
          text={uiText}
        />
      )}

      {/* Settings Modal */}
      <SettingsModal
        isOpen={showSettings}
        onClose={() => setShowSettings(false)}
        theme={theme}
        onToggleTheme={toggleTheme}
        fontSize={fontSize}
        onFontSizeChange={handleFontSizeChange}
        onClearData={handleClearData}
        text={uiText}
      />

      {/* Related Case Modal */}
      <RelatedCaseModal
        isOpen={!!viewingCase}
        onClose={() => setViewingCase(null)}
        caseData={viewingCase}
        language={language}
        text={uiText}
      />
    </Layout>
  );
}

export default function AppWithErrorBoundary() {
  return (
    <ErrorBoundary>
      <App />
    </ErrorBoundary>
  );
}


