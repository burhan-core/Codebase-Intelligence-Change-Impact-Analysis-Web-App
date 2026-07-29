import React, { useState, useEffect, useRef } from 'react';
import Editor from '@monaco-editor/react';
import { FileCode2, Loader2 } from 'lucide-react';
import { api } from '../../lib/api';

const EXT_LANGUAGES = {
    py: 'python', js: 'javascript', jsx: 'javascript', ts: 'typescript', tsx: 'typescript',
    json: 'json', md: 'markdown', html: 'html', css: 'css', yml: 'yaml', yaml: 'yaml',
    toml: 'ini', sh: 'shell', bat: 'bat', sql: 'sql', rb: 'ruby', go: 'go', rs: 'rust',
    java: 'java', c: 'c', h: 'c', cpp: 'cpp', cs: 'csharp', xml: 'xml',
};

function detectLanguage(name = '') {
    const ext = name.split('.').pop().toLowerCase();
    return EXT_LANGUAGES[ext] || 'plaintext';
}

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

        monaco.editor.defineTheme('impact-lens', {
            base: 'vs-dark',
            inherit: true,
            rules: [],
            colors: {
                'editor.background': '#09090b',
                'editor.lineHighlightBackground': '#18181b',
                'editorLineNumber.foreground': '#3f3f46',
                'editorLineNumber.activeForeground': '#a1a1aa',
                'editorGutter.background': '#09090b',
                'scrollbarSlider.background': '#27272a80',
                'scrollbarSlider.hoverBackground': '#3f3f4680',
            },
        });
        monaco.editor.setTheme('impact-lens');
    }

    // Jump-to-line with a brief highlight pulse
    useEffect(() => {
        if (scrollToLine && editorRef.current && monacoRef.current) {
            const editor = editorRef.current;
            const monaco = monacoRef.current;

            editor.revealLineInCenter(scrollToLine);
            editor.setPosition({ column: 1, lineNumber: scrollToLine });
            editor.focus();

            decorationsRef.current = editor.deltaDecorations(decorationsRef.current, [
                {
                    range: new monaco.Range(scrollToLine, 1, scrollToLine, 1),
                    options: { isWholeLine: true, className: 'line-highlight-blink' },
                },
            ]);

            setTimeout(() => {
                decorationsRef.current = editor.deltaDecorations(decorationsRef.current, []);
            }, 2000);
        }
    }, [scrollToLine]);

    useEffect(() => {
        if (!file || !projectId || !file.path) {
            setContent('');
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
                setError('Failed to load file content');
                setContent('');
            } finally {
                setLoading(false);
            }
        };

        fetchContent();
    }, [file, projectId]);

    if (!file) {
        return (
            <div className="h-full flex flex-col items-center justify-center text-zinc-600 gap-3">
                <FileCode2 size={36} strokeWidth={1.5} />
                <p className="text-sm">Select a file to view its source</p>
            </div>
        );
    }

    const language = detectLanguage(file.name);

    return (
        <div className="h-full flex flex-col">
            <div className="h-9 border-b border-zinc-800 flex items-center justify-between px-4 shrink-0">
                <span className="font-editor text-xs text-zinc-400 truncate">{file.name}</span>
                <div className="flex items-center gap-3">
                    {loading && <Loader2 size={12} className="animate-spin text-zinc-500" />}
                    <span className="font-editor text-[11px] text-zinc-600">{language}</span>
                </div>
            </div>
            <div className="flex-1 overflow-hidden relative">
                {error && (
                    <div className="absolute inset-0 z-10 flex items-center justify-center bg-zinc-950/80 text-red-400 text-sm">
                        {error}
                    </div>
                )}
                <Editor
                    height="100%"
                    path={file.path}
                    language={language}
                    value={content}
                    theme="vs-dark"
                    onMount={handleEditorDidMount}
                    options={{
                        readOnly: true,
                        minimap: { enabled: false },
                        fontSize: 13,
                        fontFamily: 'JetBrains Mono, Consolas, monospace',
                        scrollBeyondLastLine: false,
                        padding: { top: 16 },
                        renderLineHighlight: 'none',
                        overviewRulerBorder: false,
                        hideCursorInOverviewRuler: true,
                        domReadOnly: true,
                    }}
                />
            </div>
        </div>
    );
}
