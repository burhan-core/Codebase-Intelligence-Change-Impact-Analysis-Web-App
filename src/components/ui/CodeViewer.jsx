import React, { useState, useEffect, useRef } from 'react';
import Editor from '@monaco-editor/react';
import { FileCode, Loader } from 'lucide-react';
import { api } from '../../lib/api';

export default function CodeViewer({ file, projectId, scrollToLine }) {
    const [content, setContent] = useState('');
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);
    const editorRef = useRef(null);
    const monacoRef = useRef(null);
    const decorationsRef = useRef([]);

    function handleEditorDidMount(editor, monaco) {
        editorRef.current = editor;
        monacoRef.current = monaco;
    }

    // Handle scrolling when scrollToLine prop changes
    useEffect(() => {
        if (scrollToLine && editorRef.current && monacoRef.current) {
            const editor = editorRef.current;
            const monaco = monacoRef.current;

            editor.revealLineInCenter(scrollToLine);
            editor.setPosition({ column: 1, lineNumber: scrollToLine });
            editor.focus();

            // Blinking Animation
            decorationsRef.current = editor.deltaDecorations(decorationsRef.current, [
                {
                    range: new monaco.Range(scrollToLine, 1, scrollToLine, 1),
                    options: {
                        isWholeLine: true,
                        className: 'line-highlight-blink'
                    }
                }
            ]);

            // Optional: Remove highlight after animation (or keep it until next navigation)
            setTimeout(() => {
                decorationsRef.current = editor.deltaDecorations(decorationsRef.current, []);
            }, 2000);
        }
    }, [scrollToLine]);

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
        <div className="h-full flex flex-col bg-transparent">
            <div className="h-10 bg-transparent border-b border-indigo-500/10 flex items-center justify-between px-4 text-sm text-indigo-200/60 font-mono">
                <span>{file.name}</span>
                {loading && <span className="flex items-center gap-2 text-xs"><Loader className="animate-spin w-3 h-3" /> Loading...</span>}
            </div>
            <div className="flex-1 overflow-hidden relative">
                {error && (
                    <div className="absolute inset-0 z-10 flex items-center justify-center bg-[#09090b]/80 text-red-400">
                        {error}
                    </div>
                )}
                <Editor
                    height="100%"
                    path={file.path} // Unique path to reset editor state
                    defaultLanguage={file.language || 'javascript'}
                    value={content}
                    theme="vs-dark"
                    onMount={handleEditorDidMount}
                    options={{
                        readOnly: true,
                        minimap: { enabled: false },
                        fontSize: 13, // Smaller font
                        fontFamily: 'JetBrains Mono, Menlo, monospace',
                        fontWeight: '300', // Lighter font
                        scrollBeyondLastLine: false,
                        padding: { top: 24 },
                        renderLineHighlight: 'none',
                        overviewRulerBorder: false,
                        hideCursorInOverviewRuler: true,
                    }}
                />
            </div>
        </div>
    );
}
