import React from 'react';
import { FileText, X } from 'lucide-react';

/**
 * FileAttachment Component
 * Displays a file card with icon, name, size and optional remove action
 */
export function FileAttachment({ file, onRemove }) {
    if (!file) return null;

    const formatSize = (bytes) => {
        if (!bytes) return '';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
    };

    return (
        <div className="file-attachment">
            <div className="file-icon">
                <FileText size={24} strokeWidth={1.5} />
            </div>
            <div className="file-info">
                <div className="file-name" title={file.name}>
                    {file.name}
                </div>
                {file.size && (
                    <div className="file-size">
                        {formatSize(file.size)}
                    </div>
                )}
            </div>
            {onRemove && (
                <button
                    className="file-remove-btn"
                    onClick={(e) => {
                        e.stopPropagation();
                        onRemove();
                    }}
                    title="Remove file"
                >
                    <X size={16} />
                </button>
            )}
        </div>
    );
}

export default FileAttachment;
