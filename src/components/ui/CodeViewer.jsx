import React, { useState, useEffect } from 'react';
import Editor from '@monaco-editor/react';
import { FileCode, Loader } from 'lucide-react';
import { api } from '../../lib/api';

export default function CodeViewer({ file, projectId }) {
    const [content, setContent] = useState('');
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);

    useEffect(() => {
        if (!file || !projectId || !file.path) {
            setContent(''); // Clear content when no file is selected or projectId is missing
            return;
        }

        const fetchContent = async () => {
            setLoading(true);
            setError(null);
            try {
                const data = await api.getFileContent(projectId, file.path);
                setContent(data.content);
            } catch (err) {
                console.error(err);
                setError("Failed to load file content");
                setContent("// Error loading content");
            } finally {
                setLoading(false);
            }
        };

        fetchContent();
    }, [file, projectId]);

    if (!file) {
        return (
            <div className="h-full flex flex-col items-center justify-center text-slate-500 bg-slate-900">
                <FileCode size={48} className="mb-4 opacity-50" />
                <p>Select a file to view content</p>
            </div>
        );
    }

    return (
        <div className="h-full flex flex-col">
            <div className="h-10 bg-slate-900 border-b border-slate-800 flex items-center justify-between px-4 text-sm text-slate-400 font-mono">
                <span>{file.name}</span>
                {loading && <span className="flex items-center gap-2 text-xs"><Loader className="animate-spin w-3 h-3" /> Loading...</span>}
            </div>
            <div className="flex-1 overflow-hidden relative">
                {error && (
                    <div className="absolute inset-0 z-10 flex items-center justify-center bg-slate-900/80 text-red-400">
                        {error}
                    </div>
                )}
                <Editor
                    height="100%"
                    path={file.path} // Unique path to reset editor state
                    defaultLanguage={file.language || 'javascript'}
                    value={content}
                    theme="vs-dark"
                    options={{
                        readOnly: true,
                        minimap: { enabled: false },
                        fontSize: 14,
                        fontFamily: 'JetBrains Mono, Menlo, monospace',
                        scrollBeyondLastLine: false,
                        padding: { top: 16 }
                    }}
                />
            </div>
        </div>
    );
}
