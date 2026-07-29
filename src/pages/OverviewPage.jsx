import React, { useState, useEffect, useRef } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import FileTree from '../components/ui/FileTree';
import CodeViewer from '../components/ui/CodeViewer';
import StructurePanel from '../components/ui/StructurePanel';
import ImpactPanel from '../components/ui/ImpactPanel';
import GraphView from '../components/ui/GraphView';
import { Loader2, Braces, Crosshair, CheckCircle2, Code2, Network } from 'lucide-react';
import { api } from '../lib/api';

export default function OverviewPage() {
    const { state } = useLocation();
    const navigate = useNavigate();
    const [selectedFile, setSelectedFile] = useState(null);
    const [metadata, setMetadata] = useState(null);
    const [isParsing, setIsParsing] = useState(false);
    const [parseStats, setParseStats] = useState(null);
    const [editorLine, setEditorLine] = useState(null);
    const [rightTab, setRightTab] = useState('symbols');
    const [impactTarget, setImpactTarget] = useState(null);
    const [viewMode, setViewMode] = useState('ide');

    const projectId = state?.projectId;
    const fileTree = state?.fileTree;

    // Redirect if no state (direct access protection)
    useEffect(() => {
        if (!projectId || !fileTree) {
            navigate('/input');
        }
    }, [projectId, fileTree, navigate]);

    // Auto-trigger parsing on mount (ref guard: StrictMode double-mounts
    // would otherwise fire two concurrent parses that clobber each other)
    const parsedRef = useRef(null);
    useEffect(() => {
        if (!projectId || parsedRef.current === projectId) return;
        parsedRef.current = projectId;
        const parse = async () => {
            setIsParsing(true);
            try {
                const result = await api.parseProject(projectId);
                setParseStats(result);
            } catch (e) {
                console.error('Parsing failed', e);
            } finally {
                setIsParsing(false);
            }
        };
        parse();
    }, [projectId]);

    // Fetch metadata when a Python file is selected
    useEffect(() => {
        if (!selectedFile?.path || !selectedFile.name.endsWith('.py')) {
            setMetadata(null);
            return;
        }

        const fetchMeta = async () => {
            try {
                const data = await api.getMetadata(projectId, selectedFile.path);
                setMetadata(data);
            } catch (e) {
                console.error(e);
            }
        };
        fetchMeta();
    }, [selectedFile, projectId]);

    if (!projectId || !fileTree) return null;

    // Navigate to a file (and optionally a line) from dependency/impact results
    const handleNavigate = (path, line) => {
        const fileName = path.split(/[\\/]/).pop();
        setSelectedFile({ name: fileName, path });
        if (line) setEditorLine(line);
    };

    const handleTargetImpact = (target) => {
        setImpactTarget(target);
        setRightTab('impact');
    };

    const tabs = [
        { id: 'symbols', label: 'Symbols', Icon: Braces },
        { id: 'impact', label: 'Impact', Icon: Crosshair },
    ];

    return (
        <div className="flex-1 flex flex-col overflow-hidden">
            <div className="flex-1 flex overflow-hidden">
                {/* Left: file explorer */}
                <aside className="w-64 flex flex-col border-r border-zinc-800 bg-zinc-950 shrink-0">
                    <FileTree files={fileTree} onSelectFile={setSelectedFile} selectedPath={selectedFile?.path} />
                </aside>

                {/* Center: code viewer or dependency graph */}
                <div className="flex-1 flex flex-col min-w-0 bg-zinc-950 relative">
                    {viewMode === 'ide' ? (
                        <CodeViewer file={selectedFile} projectId={projectId} scrollToLine={editorLine} />
                    ) : (
                        <GraphView
                            projectId={projectId}
                            selectedPath={selectedFile?.path}
                            impactTarget={impactTarget}
                            onSelectFile={(path) => handleNavigate(path)}
                            onOpenFile={(path) => { handleNavigate(path); setViewMode('ide'); }}
                        />
                    )}

                    {/* View toggle */}
                    <div className="absolute bottom-3 left-1/2 -translate-x-1/2 z-20 flex rounded-md border border-zinc-800 bg-zinc-950/90 backdrop-blur-sm p-0.5 shadow-lg shadow-black/40">
                        {[
                            { id: 'ide', label: 'IDE', Icon: Code2 },
                            { id: 'graph', label: 'Graph', Icon: Network },
                        ].map(({ id, label, Icon }) => (
                            <button
                                key={id}
                                onClick={() => setViewMode(id)}
                                className={`flex items-center gap-1.5 px-3 py-1.5 rounded text-xs font-medium transition-colors
                                    ${viewMode === id
                                        ? 'bg-zinc-800 text-zinc-100'
                                        : 'text-zinc-500 hover:text-zinc-300'}`}
                            >
                                <Icon size={13} />
                                {label}
                            </button>
                        ))}
                    </div>
                </div>

                {/* Right: symbols / impact */}
                <aside className="w-80 flex flex-col border-l border-zinc-800 bg-zinc-950 shrink-0">
                    <div className="h-9 flex border-b border-zinc-800 shrink-0">
                        {tabs.map(({ id, label, Icon }) => (
                            <button
                                key={id}
                                onClick={() => setRightTab(id)}
                                className={`flex-1 flex items-center justify-center gap-1.5 text-xs font-medium transition-colors border-b-2 -mb-px
                                    ${rightTab === id
                                        ? 'text-zinc-100 border-blue-600'
                                        : 'text-zinc-500 border-transparent hover:text-zinc-300'}`}
                            >
                                <Icon size={12} />
                                {label}
                            </button>
                        ))}
                    </div>
                    <div className="flex-1 overflow-hidden">
                        {rightTab === 'symbols' ? (
                            <StructurePanel
                                metadata={metadata}
                                selectedFile={selectedFile}
                                projectId={projectId}
                                onJumpToLine={setEditorLine}
                                onNavigate={handleNavigate}
                                onTargetImpact={handleTargetImpact}
                            />
                        ) : (
                            <ImpactPanel
                                projectId={projectId}
                                target={impactTarget}
                                onNavigate={handleNavigate}
                            />
                        )}
                    </div>
                </aside>
            </div>

            {/* Status bar */}
            <footer className="h-6 border-t border-zinc-800 bg-zinc-950 flex items-center px-4 gap-4 font-editor text-[11px] text-zinc-600 shrink-0 select-none">
                {isParsing ? (
                    <span className="flex items-center gap-1.5 text-blue-500">
                        <Loader2 size={10} className="animate-spin" /> indexing python files…
                    </span>
                ) : parseStats ? (
                    <span className="flex items-center gap-1.5">
                        <CheckCircle2 size={10} className="text-emerald-500" />
                        {parseStats.parsed_files} files indexed
                        {parseStats.errors > 0 && <span className="text-amber-500">· {parseStats.errors} parse errors</span>}
                    </span>
                ) : (
                    <span>ready</span>
                )}
                {selectedFile && <span className="truncate ml-auto">{selectedFile.name}</span>}
            </footer>
        </div>
    );
}
