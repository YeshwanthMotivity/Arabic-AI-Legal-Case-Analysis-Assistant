import React from 'react';
import { RotateCcw, Copy, Download, FileText } from 'lucide-react';

/**
 * ToolsPanel Component
 * Right sidebar with document info, related cases, and quick actions.
 */
export function ToolsPanel({
  uploadedCase,
  relatedCases = [],
  onExport,
  onRegenerate,
  onCopyAll,
  onViewCase,
  language = 'ar',
  text
}) {
  const translateValue = (val) => {
    if (language === 'ar' || !val) return val;
    // Basic dictionary for standard backend entities
    const db = {
      'نزاع تجاري': text.toolsTypeTranslated || 'Commercial Dispute',
      'قضية قانونية': 'Legal Case',
      'تجاري': 'Commercial',
      'عمالي': 'Labor',
      'جنائي': 'Criminal'
    };
    if (db[val]) return db[val];

    // For dynamic excerpts, if language is EN, replace common Arabic legal openings
    let stringVal = String(val);
    if (stringVal.includes('تتلخص وقائع هذه القضية')) {
      return stringVal.replace('تتلخص وقائع هذه القضية', 'The facts of this case are summarized').substring(0, 100) + '...';
    }
    if (stringVal.includes('تتحصل وقائع هذه الدعوى')) {
      return stringVal.replace('تتحصل وقائع هذه الدعوى', 'The facts of this lawsuit are obtained').substring(0, 100) + '...';
    }
    if (stringVal.includes('تتلخص وقائع هذه الدعوى')) {
      return stringVal.replace('تتلخص وقائع هذه الدعوى', 'The facts of this lawsuit are summarized').substring(0, 100) + '...';
    }
    return stringVal;
  };

  return (
    <aside className="app-tools">
      <div className="tools-header">
        <span className="tools-header-icon"></span>
        <div className="header-text-stack">
          <span>{text.toolsHeader}</span>
        </div>
      </div>

      <div className="tools-content">
        {uploadedCase ? (
          <div className="tool-section">
            <div className="tool-section-title">{text.toolsUploadedDocument}</div>
            <div className="tool-card">
              <div className="tool-card-header">
                <FileText size={18} className="tool-icon" />
                <h3>{uploadedCase.name || text.sidebarUntitled}</h3>
              </div>
              <div className="tool-card-body">
                <div className="tool-info-grid">
                  <div>{text.toolsType}: <span className="text-secondary">{translateValue(uploadedCase.type) || 'PDF'}</span></div>
                  <div>{text.toolsPages}: <span className="text-secondary">{uploadedCase.pages || 'N/A'}</span></div>
                  <div>{text.toolsUploadedAt}: <span className="text-secondary">{uploadedCase.timestamp ? new Date(uploadedCase.timestamp).toLocaleDateString(language === 'ar' ? 'ar-SA' : 'en-US') : 'N/A'}</span></div>
                </div>

                {uploadedCase.keywords && uploadedCase.keywords.length > 0 && (
                  <div className="tool-keywords">
                    <div className="tool-keywords-title">{text.toolsKeywords}:</div>
                    <div className="tool-badges">
                      {uploadedCase.keywords.map((keyword, idx) => (
                        <span key={idx} className="badge badge-primary">
                          {translateValue(keyword)}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>
        ) : (
          <div className="tool-section empty">
            <div className="tool-section-title">{text.toolsUploadedDocument}</div>
            <div className="tool-empty-text">{text.toolsNoDocument}</div>
          </div>
        )}

        {relatedCases.length > 0 && (
          <div className="tool-section">
            <div className="tool-section-title">{text.toolsRelatedCases}</div>
            <div className="related-cases-list">
              {relatedCases
                .filter(caseItem => caseItem && caseItem.case)
                .map((caseItem, idx) => (
                  <div
                    key={idx}
                    className="related-case-item"
                    onClick={() => onViewCase?.(caseItem?.case?.case_id)}
                  >
                    <div className="related-case-header">
                      <span className="related-case-title">{caseItem?.case?.case_id || text.toolsUnknownCase}</span>
                      <span className="badge badge-success">
                        {Math.round(caseItem?.similarity_score || 0)}%
                      </span>
                    </div>
                    <div className="related-case-preview" style={{ direction: language === 'ar' ? 'rtl' : 'ltr' }}>
                      {translateValue(caseItem?.preview) || text.toolsNoPreview}
                    </div>
                  </div>
                ))}
            </div>
          </div>
        )}

        <div className="tool-section">
          <div className="tool-section-title">{text.toolsQuickActions}</div>
          <div className="quick-actions-grid">
            <button className="tool-button" onClick={onRegenerate}>
              <RotateCcw size={16} />
              <div className="btn-text-stack">
                <span>{text.toolsRegenerate}</span>
              </div>
            </button>
            <button className="tool-button" onClick={onCopyAll}>
              <Copy size={16} />
              <div className="btn-text-stack">
                <span>{text.toolsCopyAll}</span>
              </div>
            </button>
            <button className="tool-button" onClick={onExport}>
              <Download size={16} />
              <div className="btn-text-stack">
                <span>{text.toolsDownloadPdf}</span>
              </div>
            </button>
          </div>
        </div>

        <div className="tool-help-section">
          <div className="tool-help-box">
            Powered By <strong>Motivity Labs</strong>
            <div className="en-tiny">{text.toolsNotice}
            </div>
          </div>
        </div>
      </div>
    </aside>
  );
}

export default ToolsPanel;
