import React, { useState } from 'react';

const EvidencePanel = ({ analysis, caseText, draftText, setDraftText }) => {
    const [activeTab, setActiveTab] = useState('overview');

    if (!analysis) {
        return (
            <div className="evidence-panel h-100 d-flex align-items-center justify-content-center bg-light text-muted">
                <div className="text-center">
                    <div className="display-1 mb-3"></div>
                    <h5>No Case Selected</h5>
                    <p>Upload a document or paste text to begin analysis.</p>
                </div>
            </div>
        );
    }

    const { classification, entities, trends, recommendation, legal_principles } = analysis;

    return (
        <div className="evidence-panel h-100 d-flex flex-column bg-white border-end">
            {/* Tabs */}
            <ul className="nav nav-tabs nav-fill bg-light border-bottom">
                <li className="nav-item">
                    <button
                        className={`nav-link ${activeTab === 'overview' ? 'active fw-bold' : ''}`}
                        onClick={() => setActiveTab('overview')}
                    >
                        Overview
                    </button>
                </li>
                <li className="nav-item">
                    <button
                        className={`nav-link ${activeTab === 'facts' ? 'active fw-bold' : ''}`}
                        onClick={() => setActiveTab('facts')}
                    >
                        Facts
                    </button>
                </li>
                <li className="nav-item">
                    <button
                        className={`nav-link ${activeTab === 'stats' ? 'active fw-bold' : ''}`}
                        onClick={() => setActiveTab('stats')}
                    >
                        Statistics
                    </button>
                </li>
                <li className="nav-item">
                    <button
                        className={`nav-link ${activeTab === 'drafts' ? 'active fw-bold' : ''}`}
                        onClick={() => setActiveTab('drafts')}
                    >
                        Draft Editor
                    </button>
                </li>
            </ul>

            {/* Content Area */}
            <div className="tab-content flex-grow-1 p-4 overflow-auto">

                {/* OVERVIEW TAB */}
                {activeTab === 'overview' && (
                    <div className="tab-pane fade show active">
                        <div className="mb-4">
                            <h6 className="text-uppercase text-muted small fw-bold">Case Classification</h6>
                            <div className="d-flex align-items-center">
                                <h3 className="mb-0 text-primary">{classification.name_ar}</h3>
                                <span className="badge bg-success ms-2">
                                    {(classification.confidence * 100).toFixed(0)}% Confidence
                                </span>
                            </div>
                            <p className="text-muted">{classification.name_en}</p>
                        </div>

                        {recommendation && (
                            <div className="card bg-info bg-opacity-10 border-info mb-4">
                                <div className="card-body">
                                    <h6 className="card-title text-info fw-bold"> Recommendation</h6>
                                    <p className="card-text">{recommendation.recommendation_ar}</p>
                                </div>
                            </div>
                        )}

                        {legal_principles && legal_principles.length > 0 && (
                            <div>
                                <h6 className="text-uppercase text-muted small fw-bold mb-3">Legal Principles</h6>
                                {legal_principles.map((principle, idx) => (
                                    <div key={idx} className="mb-3 border-bottom pb-2">
                                        <div className="fw-bold">{principle.name_ar}</div>
                                        <small className="text-muted">{principle.description_ar}</small>
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>
                )}

                {/* FACTS TAB */}
                {activeTab === 'facts' && (
                    <div className="tab-pane fade show active">
                        <h6 className="text-uppercase text-muted small fw-bold mb-3">Extracted Entities (The Auditor)</h6>
                        {entities && Object.keys(entities).length > 0 ? (
                            <table className="table table-hover table-bordered table-sm">
                                <thead className="table-light">
                                    <tr>
                                        <th>Entity</th>
                                        <th>Value</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {Object.entries(entities).map(([key, val], i) => (
                                        <tr key={i}>
                                            <td className="fw-bold text-nowrap">{key}</td>
                                            <td>{typeof val === 'object' ? JSON.stringify(val) : String(val)}</td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        ) : (
                            <p className="text-muted">No specific entities extracted.</p>
                        )}

                        {caseText && (
                            <div className="mt-4">
                                <h6 className="text-uppercase text-muted small fw-bold">Original Text Snippet</h6>
                                <div className="p-3 bg-light rounded border font-monospace small" style={{ maxHeight: '200px', overflowY: 'auto' }}>
                                    {caseText.substring(0, 1000)}...
                                </div>
                            </div>
                        )}
                    </div>
                )}

                {/* STATS TAB */}
                {activeTab === 'stats' && trends && (
                    <div className="tab-pane fade show active">
                        <h6 className="text-uppercase text-muted small fw-bold mb-4">Predictive Analytics</h6>

                        <div className="row g-3">
                            <div className="col-12">
                                <div className="card shadow-sm border-0">
                                    <div className="card-body text-center">
                                        <h2 className="display-4 text-success fw-bold">{trends.plaintiff_win_rate}%</h2>
                                        <p className="text-muted mb-0">Plaintiff Win Probability</p>
                                    </div>
                                </div>
                            </div>

                            <div className="col-6">
                                <div className="card shadow-sm border-0 h-100">
                                    <div className="card-body">
                                        <h6 className="text-muted small">Avg Compensation</h6>
                                        <h4 className="fw-bold">{trends.average_compensation.toLocaleString()} SAR</h4>
                                    </div>
                                </div>
                            </div>

                            <div className="col-6">
                                <div className="card shadow-sm border-0 h-100">
                                    <div className="card-body">
                                        <h6 className="text-muted small">Similar Cases</h6>
                                        <h4 className="fw-bold">{trends.compensation_count || 'N/A'}</h4>
                                    </div>
                                </div>
                            </div>
                        </div>

                        <div className="mt-4 p-3 bg-warning bg-opacity-10 rounded">
                            <small>️ These statistics are based on historical data of similar cases and do not guarantee future outcomes.</small>
                        </div>
                    </div>
                )}

                {/* DRAFTS TAB */}
                {activeTab === 'drafts' && (
                    <div className="tab-pane fade show active h-100 d-flex flex-column">
                        <div className="d-flex justify-content-between align-items-center mb-2">
                            <h6 className="fw-bold m-0">Legal Draft Editor</h6>
                            <div>
                                <button
                                    className="btn btn-sm btn-outline-primary me-2"
                                    onClick={() => {
                                        const editor = document.getElementById('draft-editor');
                                        if (editor) navigator.clipboard.writeText(editor.value);
                                    }}
                                >
                                    Copy
                                </button>
                                <button
                                    className="btn btn-sm btn-outline-success"
                                    onClick={() => alert('Download feature coming soon in Phase 3!')}
                                >
                                    Download
                                </button>
                            </div>
                        </div>
                        <textarea
                            id="draft-editor"
                            className="form-control flex-grow-1"
                            style={{ resize: 'none', fontFamily: 'monospace', fontSize: '0.9rem', direction: 'rtl' }}
                            placeholder="AI generated drafts will appear here... (Copy/Paste from chat for now)"
                            value={draftText || ''}
                            onChange={(e) => setDraftText && setDraftText(e.target.value)}
                        />
                    </div>
                )}
            </div>
        </div>
    );
};

export default EvidencePanel;
