import React from 'react';
import { X, Sun, Moon, Trash2 } from 'lucide-react';

/**
 * SettingsModal Component
 * Allows users to configure application preferences.
 */
export function SettingsModal({
  isOpen,
  onClose,
  theme,
  onToggleTheme,
  fontSize,
  onFontSizeChange,
  onClearData,
  text
}) {
  if (!isOpen) return null;

  const fontSizes = [
    { value: 'small', label: text.fontSmall },
    { value: 'medium', label: text.fontMedium },
    { value: 'large', label: text.fontLarge },
    { value: 'xl', label: text.fontXL }
  ];

  return (
    <div className="settings-modal-overlay" onClick={onClose}>
      <div className="settings-modal" onClick={e => e.stopPropagation()}>
        <div className="settings-header">
          <h2>{text.settingsTitle}</h2>
          <button className="btn-icon" onClick={onClose}>
            <X size={20} />
          </button>
        </div>

        <div className="settings-content">
          <section className="settings-section">
            <h3>{text.settingsAppearance}</h3>
            <div className="settings-row">
              <div className="label-stack">
                <span>{text.settingsThemeLabel}</span>
              </div>
              <button
                className="btn-secondary theme-toggle-btn"
                onClick={onToggleTheme}
              >
                {theme === 'light' ? (
                  <>
                    <Moon size={18} />
                    <div className="btn-text-stack">
                      <span>{text.settingsDarkMode}</span>
                    </div>
                  </>
                ) : (
                  <>
                    <Sun size={18} />
                    <div className="btn-text-stack">
                      <span>{text.settingsLightMode}</span>
                    </div>
                  </>
                )}
              </button>
            </div>
          </section>

          <section className="settings-section">
            <h3>{text.settingsFontSize}</h3>
            <div className="font-size-options">
              {fontSizes.map((size) => (
                <button
                  key={size.value}
                  className={`btn-option ${fontSize === size.value ? 'active' : ''}`}
                  onClick={() => onFontSizeChange(size.value)}
                >
                  <span style={{ fontSize: size.value === 'small' ? '0.875rem' : size.value === 'medium' ? '1rem' : size.value === 'large' ? '1.125rem' : '1.25rem' }}>
                    A
                  </span>
                  <div className="btn-text-stack">
                    <span>{size.label}</span>
                  </div>
                </button>
              ))}
            </div>
          </section>

          <section className="settings-section destructive">
            <h3>{text.settingsData}</h3>
            <div className="settings-row">
              <div className="label-stack">
                <span>{text.settingsClearDataLabel}</span>
              </div>
              <button
                className="btn-danger"
                onClick={() => {
                  if (window.confirm(text.confirmClearData)) {
                    onClearData();
                  }
                }}
              >
                <Trash2 size={18} />
                <div className="btn-text-stack">
                  <span>{text.settingsClearDataButton}</span>
                </div>
              </button>
            </div>
          </section>
        </div>
      </div>
    </div>
  );
}

export default SettingsModal;
