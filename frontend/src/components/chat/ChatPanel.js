import React, { useEffect, useRef } from 'react';

const ChatPanel = ({
    messages,
    loading,
    onSendMessage,
    onFileUpload,
    onSuggestedAction
}) => {
    const messagesEndRef = useRef(null);
    const [inputText, setInputText] = React.useState('');

    // Scroll to bottom on new messages
    useEffect(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }, [messages]);

    const handleKeyPress = (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleSend();
        }
    };

    const handleSend = () => {
        if (inputText.trim()) {
            onSendMessage(inputText);
            setInputText('');
        }
    };

    return (
        <div className="chat-panel d-flex flex-column h-100">
            {/* Messages Area */}
            <div className="chat-messages flex-grow-1 p-3 overflow-auto">
                {messages.map((msg) => (
                    <div key={msg.id} className={`message message-${msg.role} mb-3`}>
                        <div className={`d-flex ${msg.role === 'user' ? 'flex-row-reverse' : 'flex-row'}`}>
                            <div className="message-avatar mx-2">
                                {msg.role === 'user' ? '' : '️'}
                            </div>
                            <div className="message-bubble p-3 rounded"
                                style={{
                                    backgroundColor: msg.role === 'user' ? '#007bff' : '#f8f9fa',
                                    color: msg.role === 'user' ? 'white' : 'black',
                                    maxWidth: '85%'
                                }}>
                                <div className="message-text" style={{ whiteSpace: 'pre-line' }}>
                                    {msg.content}
                                    {msg.translation && (
                                        <div className="message-translation mt-2 pt-2 border-top border-white-50 small fst-italic text-start" dir="ltr">
                                            <span className="opacity-75">Translation:</span><br />
                                            {msg.translation}
                                        </div>
                                    )}
                                </div>

                                {/* Explainability Layer: Citations */}
                                {msg.citations && msg.citations.length > 0 && (
                                    <div className="citations-footer mt-3 pt-2 border-top border-secondary-subtle">
                                        <h6 className="small text-muted mb-2" style={{ fontSize: '0.75rem', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                                             Sources Used | المصادر:
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

                                {/* Suggested Actions */}
                                {msg.suggestedActions && msg.suggestedActions.length > 0 && (
                                    <div className="suggested-actions mt-3">
                                        {msg.suggestedActions.map((action, idx) => (
                                            <button
                                                key={idx}
                                                className="btn btn-sm btn-outline-primary me-2 mb-2"
                                                style={{ borderColor: msg.role === 'user' ? 'white' : '', color: msg.role === 'user' ? 'white' : '' }}
                                                onClick={() => onSuggestedAction(action.action)}
                                                disabled={loading}
                                            >
                                                {action.label}
                                            </button>
                                        ))}
                                    </div>
                                )}
                            </div>
                        </div>
                    </div>
                ))}

                {loading && (
                    <div className="message message-assistant mb-3">
                        <div className="d-flex flex-row">
                            <div className="message-avatar mx-2">️</div>
                            <div className="message-bubble p-3 rounded bg-light">
                                <div className="typing-indicator">
                                    <span>●</span> <span>●</span> <span>●</span>
                                </div>
                            </div>
                        </div>
                    </div>
                )}
                <div ref={messagesEndRef} />
            </div>

            {/* Input Area */}
            <div className="chat-input-area p-3 border-top bg-white">
                <div className="input-group">
                    <button
                        className="btn btn-outline-secondary"
                        onClick={() => document.getElementById('chat-file-input').click()}
                        title="Upload File"
                    >
                        
                    </button>
                    <input
                        type="file"
                        id="chat-file-input"
                        hidden
                        onChange={(e) => e.target.files[0] && onFileUpload(e.target.files[0])}
                        accept=".pdf,.docx,.txt"
                    />

                    <textarea
                        className="form-control"
                        placeholder="Type your question..."
                        value={inputText}
                        onChange={(e) => setInputText(e.target.value)}
                        onKeyPress={handleKeyPress}
                        disabled={loading}
                        rows={1}
                        style={{ resize: 'none' }}
                    />

                    <button
                        className="btn btn-primary"
                        onClick={handleSend}
                        disabled={loading || !inputText.trim()}
                    >
                        
                    </button>
                </div>
            </div>
        </div>
    );
};

export default ChatPanel;
