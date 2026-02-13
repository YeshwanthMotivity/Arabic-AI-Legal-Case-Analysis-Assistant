// ===================================
// PRODUCTION-READY REACT COMPONENTS
// Arabic Legal Assistant v2.0
// ===================================

// ===== 1. LAYOUT WRAPPER =====

// src/components/Layout.js
import React from 'react';

export const Layout = ({ children, sidebar, tools }) => {
  return (
    <div className="app-layout">
      {children}
    </div>
  );
};

// ===== 2. HEADER COMPONENT =====

// src/components/Header.js
import React, { useState } from 'react';
import { Settings, Menu, LogOut } from 'lucide-react';

export const Header = ({ 
  healthStatus = 'idle', 
  onSettings, 
  onMenu, 
  onLogout 
}) => {
  const getStatusColor = () => {
    switch(healthStatus) {
      case 'connected': return 'var(--color-success)';
      case 'connecting': return 'var(--color-warning)';
      case 'disconnected': return 'var(--color-error)';
      default: return 'var(--color-status-idle)';
    }
  };

  const getStatusText = () => {
    switch(healthStatus) {
      case 'connected': return 'Connected';
      case 'connecting': return 'Connecting...';
      case 'disconnected': return 'Disconnected';
      default: return 'Checking...';
    }
  };

  return (
    <header className="app-header">
      <div className="header-logo">
        <div className="header-logo-icon">⚖️</div>
        <div className="header-logo-text">
          <h1>Legal Assistant</h1>
          <p>AI-Powered Case Analysis</p>
        </div>
      </div>

      <div className="header-controls">
        <div 
          className="status-indicator"
          title={`Backend Status: ${getStatusText()}`}
        >
          <div 
            className={`status-dot ${healthStatus}`}
            style={{ backgroundColor: getStatusColor() }}
          />
          <span className="status-text">{getStatusText()}</span>
        </div>

        <button 
          className="btn-icon btn-icon-white"
          onClick={onSettings}
          aria-label="Settings"
        >
          <Settings size={20} />
        </button>

        <button 
          className="btn-icon btn-icon-white"
          onClick={onMenu}
          aria-label="Menu"
        >
          <Menu size={20} />
        </button>
      </div>
    </header>
  );
};

// ===== 3. SIDEBAR COMPONENT =====

// src/components/Sidebar.js
import React, { useState } from 'react';
import { Search, Plus, MoreVertical, Archive, Trash2 } from 'lucide-react';

export const Sidebar = ({
  conversations = [],
  currentConversationId = null,
  onNewChat,
  onSelectConversation,
  onDeleteConversation,
  onArchiveConversation
}) => {
  const [searchTerm, setSearchTerm] = useState('');
  const [expandedMenu, setExpandedMenu] = useState(null);

  const filteredConversations = conversations.filter(conv =>
    conv.title.toLowerCase().includes(searchTerm.toLowerCase()) ||
    conv.preview?.toLowerCase().includes(searchTerm.toLowerCase())
  );

  return (
    <aside className="app-sidebar">
      <div className="sidebar-header">
        <button 
          className="sidebar-new-chat"
          onClick={onNewChat}
          aria-label="Start new conversation"
        >
          <Plus size={18} />
          <span>New Chat</span>
        </button>
      </div>

      <div className="sidebar-search-wrapper" style={{ padding: 'var(--space-2) var(--space-4)' }}>
        <div style={{ 
          position: 'relative',
          display: 'flex',
          alignItems: 'center',
          gap: 'var(--space-2)'
        }}>
          <Search size={16} style={{ color: 'var(--color-text-tertiary)' }} />
          <input
            type="text"
            className="sidebar-search"
            placeholder="Search..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            style={{
              flex: 1,
              border: '1px solid var(--color-gray-300)',
              borderRadius: 'var(--radius-md)',
              padding: 'var(--space-2) var(--space-3)',
              fontSize: 'var(--font-size-sm)',
              backgroundColor: 'var(--color-bg-tertiary)',
            }}
          />
        </div>
      </div>

      <div className="sidebar-content">
        {filteredConversations.length === 0 ? (
          <div style={{
            padding: 'var(--space-6) var(--space-4)',
            textAlign: 'center',
            color: 'var(--color-text-tertiary)',
            fontSize: 'var(--font-size-sm)'
          }}>
            No conversations found
          </div>
        ) : (
          filteredConversations.map(conv => (
            <ConversationItem
              key={conv.id}
              conversation={conv}
              isActive={conv.id === currentConversationId}
              onSelect={() => onSelectConversation(conv.id)}
              onArchive={() => onArchiveConversation(conv.id)}
              onDelete={() => onDeleteConversation(conv.id)}
            />
          ))
        )}
      </div>
    </aside>
  );
};

// Helper: Conversation Item
const ConversationItem = ({
  conversation,
  isActive,
  onSelect,
  onArchive,
  onDelete
}) => {
  const [showMenu, setShowMenu] = useState(false);

  const formatTime = (timestamp) => {
    const date = new Date(timestamp);
    const now = new Date();
    const diffHours = (now - date) / (1000 * 60 * 60);

    if (diffHours < 1) return 'Now';
    if (diffHours < 24) return `Today`;
    if (diffHours < 48) return `Yesterday`;
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
  };

  return (
    <div
      className={`conversation-item ${isActive ? 'active' : ''}`}
      style={{
        position: 'relative'
      }}
    >
      <div 
        style={{ flex: 1, cursor: 'pointer' }}
        onClick={onSelect}
      >
        <div className="conversation-title">{conversation.title}</div>
        {conversation.preview && (
          <div className="conversation-preview">{conversation.preview}</div>
        )}
        <div className="conversation-time">{formatTime(conversation.updatedAt)}</div>
      </div>

      <button
        className="btn-icon"
        style={{
          position: 'absolute',
          right: 'var(--space-2)',
          top: '50%',
          transform: 'translateY(-50%)',
          opacity: showMenu ? 1 : 0.5,
          transition: 'opacity var(--duration-base)',
        }}
        onClick={() => setShowMenu(!showMenu)}
        aria-label="Conversation menu"
      >
        <MoreVertical size={16} />
      </button>

      {showMenu && (
        <div style={{
          position: 'absolute',
          right: 0,
          top: '100%',
          marginTop: 'var(--space-1)',
          backgroundColor: 'white',
          borderRadius: 'var(--radius-md)',
          border: '1px solid var(--color-gray-300)',
          boxShadow: 'var(--shadow-lg)',
          zIndex: 'var(--z-dropdown)',
          minWidth: '160px',
        }}>
          <button
            style={{
              width: '100%',
              padding: 'var(--space-2) var(--space-3)',
              border: 'none',
              background: 'none',
              textAlign: 'right',
              cursor: 'pointer',
              fontSize: 'var(--font-size-sm)',
              display: 'flex',
              alignItems: 'center',
              gap: 'var(--space-2)',
              color: 'var(--color-text-primary)',
            }}
            onClick={() => {
              onArchive();
              setShowMenu(false);
            }}
          >
            <Archive size={16} />
            Archive
          </button>
          <button
            style={{
              width: '100%',
              padding: 'var(--space-2) var(--space-3)',
              border: 'none',
              background: 'none',
              textAlign: 'right',
              cursor: 'pointer',
              fontSize: 'var(--font-size-sm)',
              display: 'flex',
              alignItems: 'center',
              gap: 'var(--space-2)',
              color: 'var(--color-error)',
              borderTop: '1px solid var(--color-gray-200)',
            }}
            onClick={() => {
              onDelete();
              setShowMenu(false);
            }}
          >
            <Trash2 size={16} />
            Delete
          </button>
        </div>
      )}
    </div>
  );
};

// ===== 4. CHAT MESSAGE COMPONENT =====

// src/components/Message.js
import React, { useState } from 'react';
import { Copy, RefreshCw, ThumbsUp, ThumbsDown, ChevronDown } from 'lucide-react';

export const Message = ({
  message,
  onCopy,
  onRegenerate,
  onFeedback,
  showActions = true
}) => {
  const [showCitations, setShowCitations] = useState(false);
  const [copiedFeedback, setCopiedFeedback] = useState(null);

  const handleCopy = () => {
    if (onCopy) {
      onCopy(message.content);
      setCopiedFeedback('copied');
      setTimeout(() => setCopiedFeedback(null), 2000);
    }
  };

  const handleFeedback = (type) => {
    if (onFeedback) {
      onFeedback(message.id, type);
      setCopiedFeedback(type);
      setTimeout(() => setCopiedFeedback(null), 2000);
    }
  };

  return (
    <div className={`message ${message.role}`}>
      <div className="message-avatar">
        {message.role === 'user' ? 'U' : 'L'}
      </div>

      <div style={{ flex: 1 }}>
        <div className="message-bubble">
          <div className="message-text">
            {message.content}
          </div>

          {message.citations && message.citations.length > 0 && (
            <div style={{
              marginTop: 'var(--space-3)',
              paddingTop: 'var(--space-3)',
              borderTop: '1px solid rgba(0, 0, 0, 0.1)',
            }}>
              <button
                onClick={() => setShowCitations(!showCitations)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 'var(--space-2)',
                  background: 'none',
                  border: 'none',
                  cursor: 'pointer',
                  color: 'var(--color-text-secondary)',
                  fontSize: 'var(--font-size-xs)',
                  fontWeight: 'var(--font-weight-medium)',
                  padding: 0,
                  marginBottom: showCitations ? 'var(--space-2)' : 0,
                }}
              >
                <span>📚 {message.citations.length} Sources</span>
                <ChevronDown 
                  size={14}
                  style={{
                    transform: showCitations ? 'rotate(180deg)' : 'rotate(0)',
                    transition: 'transform var(--duration-base)',
                  }}
                />
              </button>

              {showCitations && (
                <div style={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
                  gap: 'var(--space-2)',
                  marginTop: 'var(--space-2)',
                }}>
                  {message.citations.map((citation, idx) => (
                    <CitationCard key={idx} citation={citation} />
                  ))}
                </div>
              )}
            </div>
          )}

          {message.suggestedActions && message.suggestedActions.length > 0 && (
            <div className="message-actions">
              {message.suggestedActions.map((action, idx) => (
                <button
                  key={idx}
                  className="action-button"
                  onClick={() => {
                    if (action.onClick) action.onClick();
                  }}
                >
                  {action.label}
                </button>
              ))}
            </div>
          )}
        </div>

        {showActions && message.role === 'assistant' && (
          <div style={{
            display: 'flex',
            gap: 'var(--space-2)',
            marginTop: 'var(--space-2)',
            fontSize: 'var(--font-size-xs)',
          }}>
            <button
              className="btn-ghost"
              onClick={handleCopy}
              title="Copy to clipboard"
              aria-label="Copy message"
              style={{
                padding: 'var(--space-1) var(--space-2)',
                fontSize: 'var(--font-size-xs)',
              }}
            >
              <Copy size={14} />
              {copiedFeedback === 'copied' ? 'Copied!' : 'Copy'}
            </button>

            <button
              className="btn-ghost"
              onClick={onRegenerate}
              title="Regenerate response"
              aria-label="Regenerate"
              style={{
                padding: 'var(--space-1) var(--space-2)',
                fontSize: 'var(--font-size-xs)',
              }}
            >
              <RefreshCw size={14} />
              Regenerate
            </button>

            <div style={{ marginLeft: 'auto', display: 'flex', gap: 'var(--space-2)' }}>
              <button
                className="btn-icon"
                onClick={() => handleFeedback('helpful')}
                title="Mark as helpful"
                aria-label="Mark as helpful"
                style={{
                  color: copiedFeedback === 'helpful' ? 'var(--color-success)' : 'var(--color-text-tertiary)',
                }}
              >
                <ThumbsUp size={14} />
              </button>
              <button
                className="btn-icon"
                onClick={() => handleFeedback('unhelpful')}
                title="Mark as unhelpful"
                aria-label="Mark as unhelpful"
                style={{
                  color: copiedFeedback === 'unhelpful' ? 'var(--color-error)' : 'var(--color-text-tertiary)',
                }}
              >
                <ThumbsDown size={14} />
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

// Helper: Citation Card
const CitationCard = ({ citation }) => {
  return (
    <div className="citation-card">
      <div className="citation-source">
        <span className="citation-badge">{citation.source}</span>
        <span className="citation-article">Art. {citation.article_number}</span>
      </div>
      <p className="citation-text" title={citation.text}>
        {citation.text}
      </p>
    </div>
  );
};

// ===== 5. STATE INDICATORS =====

// src/components/StateIndicators.js
import React from 'react';

export const ThinkingIndicator = () => (
  <div className="state-indicator state-thinking">
    AI is thinking...
  </div>
);

export const StreamingIndicator = ({ wordCount = 0, timeElapsed = 0 }) => (
  <div className="state-indicator state-streaming">
    ● Streaming... {wordCount} words • {timeElapsed}s
  </div>
);

export const ErrorIndicator = ({ message, onRetry }) => (
  <div className="state-indicator state-error">
    <span>⚠️ {message}</span>
    {onRetry && (
      <button
        onClick={onRetry}
        style={{
          background: 'none',
          border: 'none',
          color: 'inherit',
          cursor: 'pointer',
          textDecoration: 'underline',
          marginLeft: 'var(--space-2)',
        }}
      >
        Retry
      </button>
    )}
  </div>
);

export const SuccessIndicator = ({ message }) => (
  <div className="state-indicator state-success">
    ✓ {message}
  </div>
);

// ===== 6. TOOLS PANEL =====

// src/components/ToolsPanel.js
import React from 'react';
import { Download, Copy, RotateCcw, FileText } from 'lucide-react';

export const ToolsPanel = ({
  uploadedCase = null,
  relatedCases = [],
  onExport,
  onRegenerate,
  onCopyAll,
  onViewCase
}) => {
  return (
    <aside className="app-tools">
      <div className="tools-header">📊 Tools & Context</div>

      <div className="tools-content">
        {uploadedCase && (
          <div className="tool-section">
            <h3 className="tool-section-title">Uploaded Document</h3>
            <div className="card">
              <div className="card-body">
                <div style={{ marginBottom: 'var(--space-2)' }}>
                  <div style={{
                    fontWeight: 'var(--font-weight-semibold)',
                    marginBottom: 'var(--space-1)',
                  }}>
                    {uploadedCase.name}
                  </div>
                  <small style={{ color: 'var(--color-text-tertiary)' }}>
                    {uploadedCase.pages} pages • {uploadedCase.type}
                  </small>
                </div>
                {uploadedCase.keywords && (
                  <div style {{
                    display: 'flex',
                    flexWrap: 'wrap',
                    gap: 'var(--space-1)',
                  }}>
                    {uploadedCase.keywords.slice(0, 5).map((kw, idx) => (
                      <span key={idx} className="badge badge-accent">
                        {kw}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        {relatedCases.length > 0 && (
          <div className="tool-section">
            <h3 className="tool-section-title">Related Cases ({relatedCases.length})</h3>
            {relatedCases.map(caseItem => (
              <div
                key={caseItem.id}
                className="tool-item"
                onClick={() => onViewCase?.(caseItem)}
                style={{ cursor: 'pointer' }}
              >
                <div style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                }}>
                  <span>📋 Case {caseItem.number}</span>
                  <span style={{
                    fontSize: 'var(--font-size-xs)',
                    color: 'var(--color-success)',
                    fontWeight: 'var(--font-weight-semibold)',
                  }}>
                    {caseItem.similarity}%
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}

        <div className="tool-section">
          <h3 className="tool-section-title">Quick Actions</h3>
          <button
            className="tool-item"
            onClick={onRegenerate}
            style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}
          >
            <RotateCcw size={14} /> Regenerate
          </button>
          <button
            className="tool-item"
            onClick={onCopyAll}
            style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}
          >
            <Copy size={14} /> Copy All
          </button>
          <button
            className="tool-item"
            onClick={onExport}
            style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}
          >
            <Download size={14} /> Export PDF
          </button>
        </div>
      </div>
    </aside>
  );
};

// ===== 7. INPUT COMPONENT =====

// src/components/ChatInput.js
import React, { useState, useRef, useEffect } from 'react';
import { Send, Paperclip } from 'lucide-react';

export const ChatInput = ({
  placeholder = "Type your question or /command...",
  onSend,
  onFileUpload,
  disabled = false,
  maxChars = 2000
}) => {
  const [text, setText] = useState('');
  const [showCommands, setShowCommands] = useState(false);
  const textareaRef = useRef(null);
  const fileInputRef = useRef(null);

  // Auto-expand textarea
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      const newHeight = Math.min(textareaRef.current.scrollHeight, 150);
      textareaRef.current.style.height = newHeight + 'px';
    }
  }, [text]);

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
      e.preventDefault();
      if (text.trim()) {
        onSend(text);
        setText('');
      }
    }
  };

  const handleSend = () => {
    if (text.trim()) {
      onSend(text);
      setText('');
    }
  };

  const commands = [
    { label: 'Summarize', value: '/summarize' },
    { label: 'Analyze', value: '/analyze' },
    { label: 'Compare', value: '/compare' },
    { label: 'Extract Facts', value: '/extract' },
    { label: 'Evaluate Evidence', value: '/evidence' },
    { label: 'Generate Draft', value: '/draft' },
  ];

  return (
    <div className="input-wrapper">
      <div className="input-group">
        <textarea
          ref={textareaRef}
          className="message-input"
          value={text}
          onChange={(e) => {
            setText(e.target.value.slice(0, maxChars));
            setShowCommands(e.target.value.includes('/'));
          }}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
          disabled={disabled}
          aria-label="Message input"
        />

        <div style={{
          display: 'flex',
          gap: 'var(--space-2)',
          alignItems: 'flex-end',
        }}>
          <button
            className="btn-icon"
            onClick={() => fileInputRef.current?.click()}
            disabled={disabled}
            title="Attach file"
            aria-label="Attach file"
          >
            <Paperclip size={20} />
          </button>

          <button
            className="btn-primary"
            onClick={handleSend}
            disabled={disabled || !text.trim()}
            type="button"
            aria-label="Send message"
          >
            <Send size={18} />
          </button>
        </div>

        <input
          ref={fileInputRef}
          type="file"
          style={{ display: 'none' }}
          onChange={(e) => {
            if (e.target.files?.[0]) {
              onFileUpload(e.target.files[0]);
            }
          }}
          accept=".pdf,.docx,.txt"
          aria-hidden="true"
        />
      </div>

      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        paddingTop: 'var(--space-2)',
        fontSize: 'var(--font-size-xs)',
        color: 'var(--color-text-tertiary)',
      }}>
        <div>
          {showCommands && (
            <div style={{
              display: 'flex',
              gap: 'var(--space-2)',
              flexWrap: 'wrap',
            }}>
              {commands.map(cmd => (
                <button
                  key={cmd.value}
                  className="badge badge-primary"
                  onClick={() => {
                    setText(cmd.value + ' ');
                    setShowCommands(false);
                  }}
                  style={{
                    opacity: text.includes(cmd.value) ? 0.5 : 1,
                    cursor: 'pointer',
                  }}
                >
                  {cmd.label}
                </button>
              ))}
            </div>
          )}
        </div>

        <span>
          {text.length} / {maxChars}
        </span>
      </div>
    </div>
  );
};

// ===== 8. MOBILE NAVIGATION =====

// src/components/MobileNavigation.js
import React from 'react';
import { MessageCircle, Archive, Settings } from 'lucide-react';

export const MobileNavigation = ({ active = 'chat', onChange }) => {
  const tabs = [
    { id: 'chat', icon: MessageCircle, label: 'Chat' },
    { id: 'history', icon: Archive, label: 'History' },
    { id: 'tools', icon: Settings, label: 'Tools' },
  ];

  return (
    <nav style={{
      display: 'flex',
      justifyContent: 'space-around',
      alignItems: 'center',
      padding: 'var(--space-2) 0',
      borderTop: '1px solid var(--color-gray-200)',
      backgroundColor: 'var(--color-bg-secondary)',
      position: 'fixed',
      bottom: 0,
      left: 0,
      right: 0,
    }}>
      {tabs.map(tab => {
        const Icon = tab.icon;
        const isActive = active === tab.id;
        return (
          <button
            key={tab.id}
            onClick={() => onChange(tab.id)}
            className={isActive ? 'active' : ''}
            style={{
              flex: 1,
              padding: 'var(--space-3)',
              background: 'none',
              border: 'none',
              cursor: 'pointer',
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              gap: 'var(--space-1)',
              color: isActive ? 'var(--color-primary)' : 'var(--color-text-tertiary)',
              transition: 'color var(--duration-base)',
            }}
            aria-label={tab.label}
            aria-current={isActive ? 'page' : undefined}
          >
            <Icon size={24} />
            <span style={{ fontSize: 'var(--font-size-xs)' }}>{tab.label}</span>
          </button>
        );
      })}
    </nav>
  );
};

// ===== EXPORT ALL =====

export {
  Header,
  Sidebar,
  Message,
  ToolsPanel,
  ChatInput,
  MobileNavigation,
  ThinkingIndicator,
  StreamingIndicator,
  ErrorIndicator,
  SuccessIndicator,
};
