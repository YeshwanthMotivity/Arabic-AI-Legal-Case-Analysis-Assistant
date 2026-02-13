import { Settings } from 'lucide-react';

/**
 * Header Component
 * Fixed header with logo, status indicator, and controls
 * - Desktop: Full header with text and status
 * - Mobile: Icon-only header with compact status
 */
export function Header({
  healthStatus = 'idle',
  onSettings
}) {
  const getStatusInfo = () => {
    switch (healthStatus) {
      case 'connected':
        return { text: 'متصل | Connected', class: 'connected', dot: '●' };
      case 'disconnected':
        return { text: 'قطع الاتصال | Disconnected', class: 'disconnected', dot: '●' };
      case 'connecting':
        return { text: 'جاري الاتصال | Connecting...', class: 'connecting', dot: '●' };
      default:
        return { text: 'يتحقق | Checking...', class: 'idle', dot: '●' };
    }
  };

  const status = getStatusInfo();

  return (
    <header className="app-header">
      {/* Logo Section */}
      <div className="header-logo">
        <div className="header-logo-icon"></div>
        <div className="header-logo-text">
          <h1>مساعد القانون | Legal AI</h1>
          <p>أداة تحليل القضايا القانونية</p>
          <p className="subtitle-en">Legal Case Analysis Assistant</p>
        </div>
      </div>

      {/* Controls */}
      <div className="header-controls">
        <div className="status-indicator" title={status.text}>
          <div className={`status-dot ${status.class}`} />
          <div className="status-text-stack">
            <span>{status.text.split('|')[0]}</span>
            <span className="en-small">{status.text.split('|')[1]}</span>
          </div>
        </div>

        {/* Settings Button */}
        <button
          className="btn-icon btn-icon-white"
          onClick={onSettings}
          title="الإعدادات | Settings"
        >
          <Settings size={20} />
        </button>
      </div>
    </header>
  );
}

export default Header;
