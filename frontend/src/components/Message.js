import React, { useState } from 'react';
import { Copy, RotateCcw, ThumbsUp, ThumbsDown } from 'lucide-react';
import ReactMarkdown from 'react-markdown';

/**
 * Message Component
 * Display single message with actions (copy, regenerate, feedback)
 * Supports rich content including markdown and citations
 */
export function Message({
  message,
  onCopy,
  onRegenerate,
  onFeedback,
  onActionClick,
  showActions = true
}) {
  const [copied, setCopied] = useState(false);
  const [feedbackGiven, setFeedbackGiven] = useState(null);

  const isUser = message.role === 'user';
  const messageClass = isUser ? 'user' : 'assistant';

  const handleCopy = () => {
    navigator.clipboard.writeText(message.content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
    onCopy?.(message.id);
  };

  const handleRegenerate = () => {
    onRegenerate?.(message.id);
  };

  const handleFeedback = (type) => {
    setFeedbackGiven(type);
    onFeedback?.(message.id, type);
  };

  return (
    <div className={`message ${messageClass}`}>
      {/* Avatar */}
      <div className="message-avatar">
        {isUser ? '👤' : '⚖️'}
      </div>

      {/* Message Content */}
      <div className="message-bubble">
        <div className="message-text">
          <ReactMarkdown>{message.content}</ReactMarkdown>
        </div>

        {/* Translation Block */}
        {message.translation && (
          <div className="message-translation">
            <div className="translation-divider"></div>
            <div className="translation-content">
              <ReactMarkdown>{message.translation}</ReactMarkdown>
            </div>
          </div>
        )}

        {/* Citations */}
        {message.citations && message.citations.length > 0 && (
          <div className="citations-container">
            {message.citations
              .filter(citation => 
                citation.source && 
                citation.source !== 'N/A' && 
                citation.article && 
                citation.article !== 'N/A' &&
                citation.text && 
                citation.text !== 'N/A'
              )
              .length > 0 && (
              <>
                <div className="citations-header">
                  المصادر | Sources:
                </div>
                {message.citations
                  .filter(citation => 
                    citation.source && 
                    citation.source !== 'N/A' && 
                    citation.article && 
                    citation.article !== 'N/A' &&
                    citation.text && 
                    citation.text !== 'N/A'
                  )
                  .map((citation, idx) => (
                  <div
                    key={idx}
                    className="citation-card"
                    style={{ marginBottom: '0.5rem' }}
                  >
                    <div className="citation-source">
                      <span className="citation-badge">
                        {citation.source ? citation.source.substring(0, 20) : 'Source'}
                      </span>
                      {citation.article && (
                        <span className="citation-article">
                          المادة {citation.article} | Article {citation.article}
                        </span>
                      )}
                    </div>
                    <div className="citation-text">
                      {citation.text}
                    </div>
                    {citation.metadata?.judgment && (
                      <div className="citation-judgment" style={{ marginTop: '0.5rem', fontSize: '0.85rem', color: 'var(--color-primary-dark)', borderLeft: '2px solid var(--color-primary)', paddingLeft: '0.5rem' }}>
                        <strong>المنطوق:</strong> {citation.metadata.judgment}
                        <div className="en-tiny"><strong>Ruling:</strong> {citation.metadata.judgment_en || 'Refer to translation block'}</div>
                      </div>
                    )}
                  </div>
                ))}
              </>
            )}
          </div>
        )}

        {/* Suggested Actions */}
        {message.suggested_actions && message.suggested_actions.length > 0 && !isUser && (
          <div className="suggested-actions-container">
            {message.suggested_actions.map((action, idx) => (
              <button
                key={idx}
                className="suggested-action-btn"
                onClick={() => onActionClick?.(action.action, action.label)}
              >
                <div className="btn-text-stack">
                  <span>{action.label}</span>
                  <span className="en-tiny">{action.action.replace(/_/g, ' ')}</span>
                </div>
              </button>
            ))}
          </div>
        )}

        {/* Message Time */}
        <div className="message-time">
          {new Date(message.timestamp).toLocaleTimeString('ar-SA')}
        </div>

        {/* Action Buttons (Now Inside Bubble) */}
        {showActions && !isUser && (
          <div className="message-actions">
            {/* Copy Button */}
            <button
              className="action-button"
              onClick={handleCopy}
              title={copied ? 'تم النسخ | Copied' : 'نسخ | Copy'}
            >
              <Copy size={12} className="btn-icon-spacing" />
              <div className="btn-text-stack">
                <span>{copied ? 'تم النسخ' : 'نسخ'}</span>
                <span className="en-tiny">{copied ? 'Copied' : 'Copy'}</span>
              </div>
            </button>

            {/* Regenerate Button */}
            <button
              className="action-button"
              onClick={handleRegenerate}
              title="إعادة توليد | Regenerate"
            >
              <RotateCcw size={12} className="btn-icon-spacing" />
              <div className="btn-text-stack">
                <span>إعادة توليد</span>
                <span className="en-tiny">Regenerate</span>
              </div>
            </button>

            {/* Feedback Buttons */}
            <div className="feedback-group">
              <button
                className={`action-button feedback-btn ${feedbackGiven === 'positive' ? 'active' : ''}`}
                onClick={() => handleFeedback('positive')}
                title="إجابة مفيدة | Helpful"
              >
                <ThumbsUp size={12} />
              </button>

              <button
                className={`action-button feedback-btn ${feedbackGiven === 'negative' ? 'active' : ''}`}
                onClick={() => handleFeedback('negative')}
                title="إجابة غير مفيدة | Not helpful"
              >
                <ThumbsDown size={12} />
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default Message;
