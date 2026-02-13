import React from 'react';
import { RotateCcw, Copy, Download, FileText } from 'lucide-react';
/* jsPDF import removed, logic moved to App.js */

/**
 * ToolsPanel Component
 * Right sidebar with document info, related cases, and quick actions
 */
export function ToolsPanel({
  uploadedCase,
  relatedCases = [],
  onExport,
  onRegenerate,
  onCopyAll,
  onViewCase
}) {
  return (
    <aside className="app-tools">
      {/* Header */}
      <div className="tools-header">
        <span className="tools-header-icon"></span>
        <div className="header-text-stack">
          <span>الأدوات والسياق</span>
          <span className="en-tiny">Tools & Context</span>
        </div>
      </div>

      {/* Content */}
      <div className="tools-content">
        {/* Uploaded Document Section */}
        {uploadedCase ? (
          <div className="tool-section">
            <div className="tool-section-title">المستند المرفوع | Uploaded Document</div>
            <div className="tool-card">
              <div className="tool-card-header">
                <FileText size={18} className="tool-icon" />
                <h3>{uploadedCase.name || 'قضية بدون عنوان'}</h3>
              </div>
              <div className="tool-card-body">
                <div className="tool-info-grid">
                  <div>📄 النوع | Type: <span className="text-secondary">{uploadedCase.type || 'PDF'}</span></div>
                  <div>📖 الصفحات | Pages: <span className="text-secondary">{uploadedCase.pages || 'N/A'}</span></div>
                  <div>⏰ تم الرفع | Uploaded: <span className="text-secondary">{uploadedCase.timestamp ? new Date(uploadedCase.timestamp).toLocaleDateString('ar-SA') : 'N/A'}</span></div>
                </div>

                {/* Keywords/Tags */}
                {uploadedCase.keywords && uploadedCase.keywords.length > 0 && (
                  <div className="tool-keywords">
                    <div className="tool-keywords-title">الكلمات المفتاحية | Keywords:</div>
                    <div className="tool-badges">
                      {uploadedCase.keywords.map((keyword, idx) => (
                        <span key={idx} className="badge badge-primary">
                          {keyword}
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
            <div className="tool-section-title">المستند المرفوع | Uploaded Document</div>
            <div className="tool-empty-text">لم يتم رفع مستند | No document uploaded</div>
          </div>
        )}

        {/* Related Cases Section */}
        {relatedCases.length > 0 && (
          <div className="tool-section">
            <div className="tool-section-title">القضايا ذات الصلة | Related Cases</div>
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
                    <span className="related-case-title">{caseItem?.case?.case_id || 'Unknown Case'}</span>
                    <span className="badge badge-success">
                      {Math.round(caseItem?.similarity_score || 0)}%
                    </span>
                  </div>
                  <div className="related-case-preview">
                    {caseItem?.preview || 'No preview available'}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Quick Actions Section */}
        <div className="tool-section">
          <div className="tool-section-title">الإجراءات السريعة | Quick Actions</div>
          <div className="quick-actions-grid">
            <button className="tool-button" onClick={onRegenerate}>
              <RotateCcw size={16} />
              <div className="btn-text-stack">
                <span>إعادة توليد</span>
                <span className="en-tiny">Regenerate</span>
              </div>
            </button>
            <button className="tool-button" onClick={onCopyAll}>
              <Copy size={16} />
              <div className="btn-text-stack">
                <span>نسخ الكل</span>
                <span className="en-tiny">Copy All</span>
              </div>
            </button>
            <button className="tool-button" onClick={onExport}>
              <Download size={16} />
              <div className="btn-text-stack">
                <span>تحميل PDF</span>
                <span className="en-tiny">Download PDF</span>
              </div>
            </button>
          </div>
        </div>

        {/* Help Section */}
        <div className="tool-help-section">
          <div className="tool-help-box">
            <strong>💡 نصيحة | Pro Tip:</strong> استخدم أوامر التشطة (/) أثناء الكتابة للوصول إلى الأدوات بسرعة.
            <div className="en-tiny">Use slash commands (/) for quick tool access while typing.</div>
          </div>
        </div>
      </div>
    </aside>
  );
}

export default ToolsPanel;
