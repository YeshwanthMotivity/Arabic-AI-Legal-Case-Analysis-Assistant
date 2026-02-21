import { Languages, Settings, Activity } from 'lucide-react';

/**
 * Header Component
 * Fixed header with title, status indicator, language toggle, and settings.
 */
export function Header({
  healthStatus = 'idle',
  onSettings,
  onToggleInsights,
  insightsVisible,
  language = 'ar',
  onToggleLanguage,
  text
}) {
  const getStatusInfo = () => {
    switch (healthStatus) {
      case 'connected':
        return { text: text.statusConnected, class: 'connected' };
      case 'disconnected':
        return { text: text.statusDisconnected, class: 'disconnected' };
      case 'connecting':
        return { text: text.statusConnecting, class: 'connecting' };
      default:
        return { text: text.statusChecking, class: 'idle' };
    }
  };

  const status = getStatusInfo();

  return (
    <header className="app-header">
      <div className="header-logo">
        <div className="header-logo-text">
          <h1>{text.headerTitle}</h1>
          <p>{text.headerSubtitleAr}</p>
          <p className="subtitle-en">{text.headerSubtitleEn}</p>
        </div>
      </div>

      <div className="header-controls">
        <div className="status-indicator" title={status.text}>
          <div className={`status-dot ${status.class}`} />
          <div className="status-text-stack">
            <span>{status.text}</span>
          </div>
        </div>

        <button
          className={`btn-icon btn-icon-white ${insightsVisible ? 'active-panel-btn' : ''}`}
          onClick={onToggleInsights}
          title={text.insightsHeader}
          aria-label="Toggle Insights"
        >
          <Activity size={18} style={{ color: insightsVisible ? 'var(--color-primary)' : 'inherit' }} />
        </button>

        <button
          className="btn-icon btn-icon-white language-toggle-btn"
          onClick={onToggleLanguage}
          title={`${language === 'ar' ? 'Switch to English' : 'التبديل إلى العربية'}`}
          aria-label="Toggle language"
        >
          <Languages size={18} />
          <span className="language-toggle-label">{text.languageLabel}</span>
        </button>

        <button
          className="btn-icon btn-icon-white"
          onClick={onSettings}
          title={text.settings}
          aria-label={text.settings}
        >
          <Settings size={20} />
        </button>
      </div>
    </header>
  );
}

export default Header;
