import React from 'react';
import { X, BookOpen, Scale, FileText, ExternalLink } from 'lucide-react';

/**
 * RelatedCaseModal Component
 * Displays detailed information about a related legal case.
 */
export function RelatedCaseModal({
    isOpen,
    onClose,
    caseData,
    language,
    text
}) {
    if (!isOpen || !caseData) return null;

    return (
        <div className="settings-modal-overlay" onClick={onClose}>
            <div className="settings-modal related-case-modal" onClick={e => e.stopPropagation()}>
                <div className="settings-header">
                    <div className="modal-title-wrapper" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <Scale size={20} className="text-primary" />
                        <h2>{text.modalCaseDetails}</h2>
                    </div>
                    <button className="btn-icon" onClick={onClose}>
                        <X size={20} />
                    </button>
                </div>

                <div className="settings-content">
                    {/* Case Header */}
                    <section className="related-case-header-section">
                        <h3 className="case-main-title">{caseData.title}</h3>
                        <div className="case-meta-badges" style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                            <span className="badge badge-primary">{caseData.type || 'SABIC'}</span>
                            <span className="badge badge-secondary">{caseData.year || '2023'}</span>
                            <span className="badge badge-success">Match: {Math.round((caseData.similarity || 0) * 100)}%</span>
                        </div>
                    </section>

                    {/* Abstract / Summary */}
                    <div className="settings-section">
                        <h3>
                            <FileText size={14} style={{ display: 'inline', marginLeft: '5px', marginRight: '5px' }} />
                            {text.modalAbstract}
                        </h3>
                        <div className="case-abstract-box" style={{
                            background: 'var(--color-bg-secondary)',
                            padding: '1rem',
                            borderRadius: 'var(--radius-md)',
                            fontSize: 'var(--font-size-sm)',
                            lineHeight: '1.6'
                        }}>
                            <p>{caseData.preview || caseData.abstract || text.modalNoAbstract}</p>
                        </div>
                    </div>

                    {/* Legal Principles */}
                    <div className="settings-section">
                        <h3>
                            <BookOpen size={14} style={{ display: 'inline', marginLeft: '5px', marginRight: '5px' }} />
                            {text.modalPrinciples}
                        </h3>
                        <ul className="legal-principles-list" style={{ paddingRight: '1.5rem' }}>
                            {(caseData.principles || ["Principle 1", "Principle 2"]).map((p, idx) => (
                                <li key={idx} style={{ marginBottom: '0.5rem', fontSize: 'var(--font-size-sm)' }}>{p}</li>
                            ))}
                        </ul>
                    </div>

                    {/* Footer Actions */}
                    <div className="modal-footer" style={{
                        display: 'flex',
                        justifyContent: 'flex-end',
                        gap: '1rem',
                        marginTop: '1rem',
                        paddingTop: '1rem',
                        borderTop: '1px solid var(--color-gray-200)'
                    }}>
                        <button className="btn-secondary" onClick={onClose} style={{
                            padding: '0.5rem 1rem',
                            borderRadius: 'var(--radius-md)',
                            border: '1px solid var(--color-gray-300)',
                            background: 'transparent',
                            cursor: 'pointer'
                        }}>
                            <div className="btn-text-stack">
                                <span>{text.modalClose}</span>
                            </div>
                        </button>

                        <button className="btn-primary" onClick={() => window.open(`#case-${caseData.id}`, '_blank')} style={{
                            display: 'flex',
                            alignItems: 'center',
                            gap: '0.5rem',
                            padding: '0.5rem 1rem',
                            borderRadius: 'var(--radius-md)',
                            background: 'var(--color-primary)',
                            color: 'white',
                            border: 'none',
                            cursor: 'pointer'
                        }}>
                            <ExternalLink size={16} />
                            <div className="btn-text-stack">
                                <span>{text.modalViewSource}</span>
                            </div>
                        </button>
                    </div>
                </div>
            </div>
        </div>
    );
}

export default RelatedCaseModal;
