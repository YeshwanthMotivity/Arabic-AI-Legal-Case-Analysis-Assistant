import React from 'react';

class ErrorBoundary extends React.Component {
    constructor(props) {
        super(props);
        this.state = {
            hasError: false,
            error: null,
            errorInfo: null
        };
    }

    static getDerivedStateFromError(error) {
        return { hasError: true };
    }

    componentDidCatch(error, errorInfo) {
        // Log to console for debugging
        console.error('ErrorBoundary caught:', error, errorInfo);

        // Update state to show error UI
        this.setState({
            error,
            errorInfo
        });

        // Optional: Send to error tracking service (e.g., Sentry)
        // logErrorToService(error, errorInfo);
    }

    render() {
        if (this.state.hasError) {
            return (
                <div style={{
                    padding: '20px',
                    textAlign: 'center',
                    backgroundColor: '#ffe6e6',
                    color: '#cc0000',
                    minHeight: '100vh',
                    display: 'flex',
                    flexDirection: 'column',
                    justifyContent: 'center',
                    alignItems: 'center',
                    fontFamily: 'Arial, sans-serif'
                }}>
                    <h1>⚠️ Something Went Wrong</h1>
                    <p>The application encountered an error. Please refresh the page to continue.</p>

                    {process.env.NODE_ENV === 'development' && this.state.error && (
                        <details style={{
                            textAlign: 'left',
                            backgroundColor: '#f5f5f5',
                            padding: '10px',
                            borderRadius: '5px',
                            marginTop: '20px',
                            maxWidth: '600px'
                        }}>
                            <summary>Error Details (Development Only)</summary>
                            <pre style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
                                {this.state.error.toString()}
                                {this.state.errorInfo?.componentStack}
                            </pre>
                        </details>
                    )}

                    <button
                        onClick={() => window.location.reload()}
                        style={{
                            marginTop: '20px',
                            padding: '10px 20px',
                            backgroundColor: '#0066cc',
                            color: 'white',
                            border: 'none',
                            borderRadius: '5px',
                            cursor: 'pointer'
                        }}
                    >
                        Refresh Page
                    </button>
                </div>
            );
        }

        return this.props.children;
    }
}

export default ErrorBoundary;
