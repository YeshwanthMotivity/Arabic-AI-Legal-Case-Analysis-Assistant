import React from 'react';
import { Activity, BookOpen, Scaling, ShieldAlert } from 'lucide-react';

/**
 * JudicialInsightsPanel Component
 * Displays the exposed backend intelligence: 
 * trends, win rates, extracted principles, and safety stats.
 */
export function JudicialInsightsPanel({ analysis, language = 'ar', text }) {
    if (!analysis) {
        return (
            <aside className="app-tools">
                <div className="tools-header">
                    <Activity size={18} className="text-primary" />
                    <div className="header-text-stack">
                        <span>{text.insightsHeader}</span>
                    </div>
                </div>
                <div className="tools-content" style={{ padding: '20px', textAlign: 'center', color: 'var(--color-text-tertiary)' }}>
                    {text.insightsNoData}
                </div>
            </aside>
        );
    }

    const { classification, trends, legal_principles } = analysis;

    return (
        <aside className="app-tools">
            <div className="tools-header">
                <Activity size={18} className="text-primary" />
                <div className="header-text-stack">
                    <span>{text.insightsHeader}</span>
                </div>
            </div>

            <div className="tools-content">
                {/* Classification Summary */}
                {classification && (
                    <div className="tool-section">
                        <div className="tool-section-title">{text.insightsClassification}</div>
                        <div className="tool-card">
                            <div className="tool-card-body">
                                <div style={{ fontWeight: '500', color: 'var(--color-text-primary)' }}>
                                    {language === 'ar' ? classification.name_ar : classification.name_en}
                                </div>
                                {classification.confidence && (
                                    <div className="en-small mt-2">
                                        Confidence: {(classification.confidence * 100).toFixed(0)}%
                                    </div>
                                )}
                            </div>
                        </div>
                    </div>
                )}

                {/* Trends & Statistics */}
                {trends && trends.plaintiff_win_rate !== undefined && (
                    <div className="tool-section">
                        <div className="tool-section-title">{text.insightsTrends}</div>
                        <div className="tool-card">
                            <div className="tool-card-header">
                                <Scaling size={16} className="text-primary" />
                                <h3>{text.insightsWinRate}</h3>
                            </div>
                            <div className="tool-card-body">
                                <div style={{ fontSize: '24px', fontWeight: 'bold', color: 'var(--color-success)', marginBottom: '8px' }}>
                                    {trends.plaintiff_win_rate}%
                                </div>

                                {trends.average_compensation > 0 && (
                                    <>
                                        <div style={{ fontSize: '0.85rem', color: 'var(--color-text-secondary)' }}>
                                            {text.insightsCompensation}
                                        </div>
                                        <div style={{ fontWeight: '500' }}>
                                            {trends.average_compensation.toLocaleString()} {language === 'ar' ? 'ريال' : 'SAR'}
                                        </div>
                                    </>
                                )}
                            </div>
                        </div>
                    </div>
                )}

                {/* Legal Principles with Clickable URLs */}
                {legal_principles && legal_principles.length > 0 && (
                    <div className="tool-section">
                        <div className="tool-section-title">{text.insightsPrinciples}</div>
                        <div className="related-cases-list">
                            {legal_principles.map((principle, idx) => (
                                <div key={idx} className="tool-card" style={{ marginBottom: '8px' }}>
                                    <div className="tool-card-header" style={{ alignItems: 'flex-start' }}>
                                        <BookOpen size={14} className="text-primary" style={{ marginTop: '2px', flexShrink: 0 }} />
                                        <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                                            <h3 style={{ fontSize: '0.9rem', lineHeight: '1.4' }}>
                                                {language === 'ar' ? principle.name_ar : principle.name_en}
                                            </h3>
                                            {principle.url ? (
                                                <a
                                                    href={principle.url}
                                                    target="_blank"
                                                    rel="noreferrer"
                                                    style={{ fontSize: '0.75rem', color: 'var(--color-info)', textDecoration: 'none' }}
                                                >
                                                    {language === 'ar' ? 'عرض النظام' : 'View Statute'} ↗
                                                </a>
                                            ) : null}
                                        </div>
                                    </div>
                                </div>
                            ))}
                        </div>
                    </div>
                )}
            </div>
        </aside>
    );
}

export default JudicialInsightsPanel;
