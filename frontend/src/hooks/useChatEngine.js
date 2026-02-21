import { useState, useRef, useEffect, useCallback } from 'react';
import axios from 'axios';

const API_BASE = "/api";

export const useChatEngine = () => {
    // Chat State
    const [messages, setMessages] = useState([]);
    const [loading, setLoading] = useState(false);
    const [healthStatus, setHealthStatus] = useState("Checking...");
    const [analysis, setAnalysis] = useState(null);
    const [caseText, setCaseText] = useState(null);
    const [draftText, setDraftText] = useState(''); // New state for Draft Editor
    const [showDetailedView, setShowDetailedView] = useState(false); // Can be managed by UI, but kept here for now logic

    const greetingSent = useRef(false);

    // Helper: Detect if text looks like legal case content
    const isLikelyCaseText = useCallback((text) => {
        if (!text || text.length < 100) return false;
        const legalKeywords = [
            'المدعي', 'المدعى عليه', 'المحكمة', 'الحكم', 'الدعوى',
            'القضية', 'الوقائع', 'الأسباب', 'منطوق', 'لائحة',
            'plaintiff', 'defendant', 'court', 'judgment', 'case',
            'حكمت', 'إلزام', 'تعويض', 'فصل', 'عقد العمل',
            'نظام العمل', 'المادة', 'البند', 'الفقرة'
        ];
        const matchCount = legalKeywords.filter(kw => text.includes(kw)).length;
        return matchCount >= 2;
    }, []);

    // Helper: Add User Message
    const addUserMessage = useCallback((text) => {
        const id = Date.now() + Math.random();
        const newMessage = {
            id: id,
            role: 'user',
            content: text,
            timestamp: new Date().toISOString()
        };
        setMessages(prev => [...prev, newMessage]);
        return id;
    }, []);

    // Helper: Add Assistant Message
    const addAssistantMessage = useCallback((text, intent = '', suggestedActions = []) => {
        const newMessage = {
            id: Date.now() + Math.random(),
            role: 'assistant',
            content: text,
            intent: intent,
            suggested_actions: suggestedActions,
            timestamp: new Date().toISOString()
        };
        setMessages(prev => [...prev, newMessage]);
    }, []);

    // Check Health
    const checkHealth = useCallback(async () => {
        try {
            await axios.get(`${API_BASE}/health`);
            setHealthStatus("Connected ");
        } catch (err) {
            setHealthStatus("Disconnected ");
        }
    }, []);

    // Analyze Pasted Text
    const analyzeCaseText = useCallback(async (text) => {
        // Add truncated user message for display
        addUserMessage(text.length > 200 ? text.substring(0, 200) + '...' : text);
        setLoading(true);

        try {
            const response = await axios.post(`${API_BASE}/analyze`, {
                text: text,
                top_k: 5
            });

            setAnalysis(response.data);
            setCaseText(text);

            addAssistantMessage(
                `تم تحليل النص بنجاح! \n\nنوع القضية: ${response.data.classification.name_ar}\nدرجة الثقة: ${(response.data.classification.confidence * 100).toFixed(0)}%\n\n---\n\nText analyzed successfully! \n\nCase Type: ${response.data.classification.name_en}\nConfidence: ${(response.data.classification.confidence * 100).toFixed(0)}%\n\nيمكنك الآن طرح أسئلة حول القضية.\nYou can now ask questions about the case.`,
                "case_analyzed",
                [
                    { label: " Full Details | عرض التفاصيل الكاملة", action: "show_details" },
                    { label: " Case Summary | ملخص القضية", action: "case_summary" },
                    { label: " Similar Cases | قضايا مشابهة", action: "similar_cases" },
                    { label: " Recommendations | توصيات", action: "recommendations" },
                    { label: "️ Legal Principles | المبادئ القانونية", action: "legal_principles" }
                ]
            );
        } catch (error) {
            console.error("Analysis error:", error);
            addAssistantMessage(
                `خطأ في تحليل النص: ${error.response?.data?.detail || error.message}\n\nText analysis error: ${error.response?.data?.detail || error.message}`,
                "error",
                [
                    { label: "Try Again | حاول مرة أخرى", action: "retry" },
                    { label: "Upload File | رفع ملف", action: "upload" }
                ]
            );
        } finally {
            setLoading(false);
        }
    }, [addUserMessage, addAssistantMessage]);

    // Send Chat Message
    const sendChatMessage = useCallback(async (userMessage, fileToUpload = null) => {
        // Handle File Upload if provided
        if (fileToUpload) {
            handleFileUpload(fileToUpload);
            return;
        }

        if (!userMessage || !userMessage.trim()) return;

        // Check if pasted text looks like case content → auto-analyze
        if (!analysis && isLikelyCaseText(userMessage)) {
            await analyzeCaseText(userMessage);
            return;
        }

        const msgId = addUserMessage(userMessage);
        setLoading(true);

        try {
            const response = await axios.post(`${API_BASE}/chat`, {
                message: userMessage,
                analysis_data: analysis, // Send current context
                case_text: caseText || null
            });

            const { text, intent, suggested_actions, user_translation, metadata } = response.data;

            // Check for Draft Metadata
            if (metadata && metadata.is_draft) {
                setDraftText(text);
                // Optional: You could also trigger a tab switch here if you exposed a way to do so
            }

            // Update message with translation if available
            if (user_translation) {
                setMessages(prev => prev.map(msg =>
                    msg.id === msgId ? { ...msg, translation: user_translation } : msg
                ));
            }

            addAssistantMessage(text, intent, suggested_actions);

        } catch (error) {
            console.error("Chat error:", error);
            addAssistantMessage(
                "عذراً، حدث خطأ في معالجة طلبك.\nSorry, an error occurred.",
                "error",
                [
                    { label: "Try Again | حاول مرة أخرى", action: "retry" },
                    { label: "Upload Case | رفع قضية", action: "upload" }
                ]
            );
        } finally {
            setLoading(false);
        }
    }, [analysis, caseText, isLikelyCaseText, analyzeCaseText, addUserMessage, addAssistantMessage, handleFileUpload]);

    // Handle File Upload
    const handleFileUpload = useCallback(async (file) => {
        if (!file) return;

        addUserMessage(` رفع ملف: ${file.name}\nUploading file: ${file.name}`);
        setLoading(true);

        const formData = new FormData();
        formData.append("file", file);

        try {
            const response = await axios.post(`${API_BASE}/upload-analyze`, formData, {
                headers: { 'Content-Type': 'multipart/form-data' }
            });

            setAnalysis(response.data);
            // We don't have raw text from PDF easily here unless backend returns it. 
            // Backend returns 'text' in AnalyzeResponse? Let's check models.py: Yes, AnalyzeResponse has 'text: str'.
            // Wait, models.py Step 299: AnalyzeResponse definition?
            // I should assume backend returns text. 
            // Let's assume response.data.text exists.
            if (response.data.text) {
                setCaseText(response.data.text);
            }

            addAssistantMessage(
                `تم تحليل الملف بنجاح! \n\nنوع القضية: ${response.data.classification.name_ar}\nدرجة الثقة: ${(response.data.classification.confidence * 100).toFixed(0)}%\n\n---\n\nFile analyzed successfully! \n\nCase Type: ${response.data.classification.name_en}\nConfidence: ${(response.data.classification.confidence * 100).toFixed(0)}%\n\nيمكنك الآن طرح أسئلة حول القضية.\nYou can now ask questions about the case.`,
                "file_analyzed",
                [
                    { label: " Full Details | عرض التفاصيل الكاملة", action: "show_details" },
                    { label: " Case Summary | ملخص القضية", action: "case_summary" }
                ]
            );

        } catch (error) {
            console.error("Upload error:", error);
            addAssistantMessage(
                `خطأ في رفع الملف: ${error.response?.data?.detail || error.message}`,
                "error",
                [
                    { label: "Try Again | حاول مرة أخرى", action: "retry" },
                    { label: "Upload Different File | رفع ملف آخر", action: "upload" }
                ]
            );
        } finally {
            setLoading(false);
        }
    }, [addUserMessage, addAssistantMessage]);

    // Initial Greeting (Once)
    useEffect(() => {
        if (greetingSent.current) return;
        greetingSent.current = true;

        // Simulate initial loading/greeting from backend
        const init = async () => {
            try {
                const response = await axios.post(`${API_BASE}/chat`, { message: "مرحبا" });
                const { text, intent, suggested_actions } = response.data;
                addAssistantMessage(text, intent, suggested_actions);
            } catch (e) {
                console.error(e);
                addAssistantMessage("مرحباً بك في المساعد القانوني الذكي.\nWelcome to the AI Legal Assistant.");
            }
        };
        init();
    }, [addAssistantMessage]);

    // Periodic Health Check
    useEffect(() => {
        checkHealth();
        const interval = setInterval(checkHealth, 5000);
        return () => clearInterval(interval);
    }, [checkHealth]);

    return {
        messages,
        loading,
        analysis,
        caseText,
        draftText, // Export state
        setDraftText, // Export setter
        healthStatus,
        showDetailedView,
        setShowDetailedView,
        sendChatMessage,
        handleFileUpload,
        checkHealth
    };
};
