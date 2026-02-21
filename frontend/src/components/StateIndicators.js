import React from 'react';

/**
 * State Indicators
 * Visual feedback for different conversation states
 * - Thinking: Purple with pulse animation
 * - Streaming: Cyan with animated dots
 * - Error: Red with retry action
 * - Success: Green with checkmark
 */

export function ThinkingIndicator({ message = 'جاري التفكير...' }) {
  return (
    <div className="state-indicator state-thinking">
      <span>&nbsp;</span>
      {message}
    </div>
  );
}

export function StreamingIndicator({ message = 'جاري الاستقبال...' }) {
  return (
    <div className="state-indicator state-streaming">
      <span>&nbsp;</span>
      {message}
    </div>
  );
}

export function ErrorIndicator({ message = 'خطأ في الاتصال', onRetry }) {
  return (
    <div className="state-indicator state-error">
      <span>&nbsp;</span>
      {message}
      {onRetry && (
        <button 
          onClick={onRetry}
          style={{
            marginLeft: 'var(--space-2)',
            padding: '2px 8px',
            fontSize: 'var(--font-size-xs)',
            background: 'var(--color-error-pale)',
            border: '1px solid var(--color-error)',
            borderRadius: 'var(--radius-sm)',
            cursor: 'pointer',
            color: 'var(--color-error)'
          }}
        >
          إعادة المحاولة
        </button>
      )}
    </div>
  );
}

export function SuccessIndicator({ message = 'تم بنجاح' }) {
  return (
    <div className="state-indicator state-success">
      <span>&nbsp;</span>
      {message}
    </div>
  );
}

export const StateIndicators = {
  Thinking: ThinkingIndicator,
  Streaming: StreamingIndicator,
  Error: ErrorIndicator,
  Success: SuccessIndicator
};

export default StateIndicators;
