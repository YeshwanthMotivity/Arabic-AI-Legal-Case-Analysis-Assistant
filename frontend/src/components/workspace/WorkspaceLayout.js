import React from 'react';
import { useChatEngine } from '../../hooks/useChatEngine';
import ChatPanel from '../chat/ChatPanel';
import EvidencePanel from './EvidencePanel';
import 'bootstrap/dist/css/bootstrap.min.css';

const WorkspaceLayout = () => {
    const {
        messages,
        loading,
        analysis,
        caseText,
        draftText,
        setDraftText,
        healthStatus,
        sendChatMessage,
        handleFileUpload,
        handleSuggestedAction,
        checkHealth
    } = useChatEngine();

    return (
        <div className="container-fluid vh-100 p-0 d-flex flex-column overflow-hidden bg-white">
            {/* Header */}
            <header className="bg-dark text-white p-2 px-3 d-flex justify-content-between align-items-center shadow-sm" style={{ zIndex: 10 }}>
                <div className="d-flex align-items-center">
                    <h5 className="mb-0 me-3 fw-bold">️ AI Legal Workspace</h5>
                    <span className="badge bg-secondary rounded-pill" style={{ fontSize: '0.7em' }}>BETA</span>
                </div>
                <div className="d-flex align-items-center">
                    <button
                        className={`btn btn-sm ${healthStatus.includes("Connected") ? "btn-outline-success" : "btn-outline-danger"} border-0`}
                        onClick={checkHealth}
                        title="Connection Status"
                    >
                        {healthStatus}
                    </button>
                </div>
            </header>

            {/* Main Content (Split Screen) */}
            <div className="row g-0 flex-grow-1 overflow-hidden">
                {/* Left Panel: Evidence (The Auditor) */}
                <div className="col-lg-7 col-md-6 h-100 overflow-hidden border-end shadow-sm" style={{ zIndex: 5 }}>
                    <EvidencePanel
                        analysis={analysis}
                        caseText={caseText}
                        draftText={draftText}
                        setDraftText={setDraftText}
                    />
                </div>

                {/* Right Panel: Chat (The Associate) */}
                <div className="col-lg-5 col-md-6 h-100 overflow-hidden bg-light position-relative">
                    <ChatPanel
                        messages={messages}
                        loading={loading}
                        onSendMessage={sendChatMessage}
                        onFileUpload={handleFileUpload}
                        onSuggestedAction={handleSuggestedAction}
                    />
                </div>
            </div>
        </div>
    );
};

export default WorkspaceLayout;
