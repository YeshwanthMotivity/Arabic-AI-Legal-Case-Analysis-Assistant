import React, { useState } from 'react';
import { Copy, RotateCcw, ThumbsUp, ThumbsDown } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import { FileAttachment } from './FileAttachment';

const hasArabic = (value = '') => /[\u0600-\u06FF]/.test(String(value));

const getLocalizedActionLabel = (label, action, language) => {
  const raw = (label || '').toString().trim();
  if (!raw) return (action || '').toString().replace(/_/g, ' ');

  const parts = raw.split('|').map(part => part.trim()).filter(Boolean);
  if (parts.length === 1) return parts[0];

  const ar = parts.find(part => hasArabic(part));
  const en = parts.find(part => !hasArabic(part));
  if (language === 'ar') return ar || parts[0];
  return en || parts[0];
};

const getPreferredMessageText = (message, language) => {
  const content = (message.content || '').toString();
  if (language === 'en' && message.translation) {
    return message.translation.toString();
  }
  return content;
};

/**
 * Message Component
 * Display single message with actions (copy, regenerate, feedback).
 */
export function Message({
  message,
  onCopy,
  onRegenerate,
  onFeedback,
  onActionClick,
  showActions = true,
  language = 'ar'
}) {
  const [copied, setCopied] = useState(false);
  const [feedbackGiven, setFeedbackGiven] = useState(null);

  const isUser = message.role === 'user';
  const messageClass = isUser ? 'user' : 'assistant';
  const localizedContent = getPreferredMessageText(message, language);

  const labels = language === 'ar'
    ? {
      sources: 'المصادر',
      article: 'المادة',
      ruling: 'المنطوق',
      copy: 'نسخ',
      copied: 'تم النسخ',
      regenerate: 'إعادة توليد',
      helpful: 'إجابة مفيدة',
      notHelpful: 'إجابة غير مفيدة'
    }
    : {
      sources: 'Sources',
      article: 'Article',
      ruling: 'Ruling',
      copy: 'Copy',
      copied: 'Copied',
      regenerate: 'Regenerate',
      helpful: 'Helpful',
      notHelpful: 'Not helpful'
    };

  const handleCopy = () => {
    navigator.clipboard.writeText(localizedContent);
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
      <div className="message-avatar">
        {isUser ? '' : '⚖️'}
      </div>

      <div className="message-bubble">
        <div className="message-text">
          {message.fileData && (
            <div style={{ marginBottom: '10px' }}>
              <FileAttachment file={message.fileData} />
            </div>
          )}
          <ReactMarkdown>{localizedContent}</ReactMarkdown>
        </div>

        {message.citations && message.citations.length > 0 && String(message.intent || '').startsWith('draft') && (
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
                    {labels.sources}
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
                            {citation.source ? citation.source.substring(0, 20) : labels.sources}
                          </span>
                          {citation.article && (
                            <span className="citation-article">
                              {labels.article} {citation.article}
                            </span>
                          )}
                        </div>
                        <div className="citation-text">
                          {citation.text}
                        </div>
                        {citation.metadata?.judgment && (
                          <div className="citation-judgment" style={{ marginTop: '0.5rem', fontSize: '0.85rem', color: 'var(--color-primary-dark)', borderLeft: '2px solid var(--color-primary)', paddingLeft: '0.5rem' }}>
                            <strong>{labels.ruling}:</strong> {language === 'ar'
                              ? citation.metadata.judgment
                              : (citation.metadata.judgment_en || citation.metadata.judgment)}
                          </div>
                        )}
                      </div>
                    ))}
                </>
              )}
          </div>
        )}

        {message.suggested_actions && message.suggested_actions.length > 0 && !isUser && (
          <div className="suggested-actions-container">
            {message.suggested_actions.map((action, idx) => (
              <button
                key={idx}
                className="suggested-action-btn"
                onClick={() => onActionClick?.(action.action, action.label, message.id)}
              >
                <div className="btn-text-stack">
                  <span>{getLocalizedActionLabel(action.label, action.action, language)}</span>
                </div>
              </button>
            ))}
          </div>
        )}

        <div className="message-time">
          {new Date(message.timestamp).toLocaleTimeString(language === 'ar' ? 'ar-SA' : 'en-US')}
        </div>

        {showActions && !isUser && (
          <div className="message-actions">
            <button
              className="action-button"
              onClick={handleCopy}
              title={copied ? labels.copied : labels.copy}
            >
              <Copy size={12} className="btn-icon-spacing" />
              <div className="btn-text-stack">
                <span>{copied ? labels.copied : labels.copy}</span>
              </div>
            </button>

            <button
              className="action-button"
              onClick={handleRegenerate}
              title={labels.regenerate}
            >
              <RotateCcw size={12} className="btn-icon-spacing" />
              <div className="btn-text-stack">
                <span>{labels.regenerate}</span>
              </div>
            </button>

            <div className="feedback-group">
              <button
                className={`action-button feedback-btn ${feedbackGiven === 'positive' ? 'active' : ''}`}
                onClick={() => handleFeedback('positive')}
                title={labels.helpful}
              >
                <ThumbsUp size={12} />
              </button>

              <button
                className={`action-button feedback-btn ${feedbackGiven === 'negative' ? 'active' : ''}`}
                onClick={() => handleFeedback('negative')}
                title={labels.notHelpful}
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
