import React, { useState, useEffect } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import FileTree from '../components/ui/FileTree';
import CodeViewer from '../components/ui/CodeViewer';
import StructurePanel from '../components/ui/StructurePanel';
import { PanelLeft, PanelRight, Loader2 } from 'lucide-react';
import { api } from '../lib/api';

export default function OverviewPage() {
    const { state } = useLocation();
    const navigate = useNavigate();
    const [selectedFile, setSelectedFile] = useState(null);
    const [metadata, setMetadata] = useState(null);
    const [isParsing, setIsParsing] = useState(false);
    const [editorLine, setEditorLine] = useState(null); // To control scrolling

    // Redirect if no state (direct access protection)
    useEffect(() => {
        if (!state?.projectId || !state?.fileTree) {
            navigate('/input');
        }
    }, [state, navigate]);

    if (!state) return null;

    const { projectId, fileTree } = state;

    // Auto-trigger parsing on mount
    useEffect(() => {
        const parse = async () => {
            setIsParsing(true);
            try {
                await api.parseProject(projectId);
                console.log("Project parsed successfully");
            } catch (e) {
                console.error("Parsing failed", e);
            } finally {
                setIsParsing(false);
            }
        };
        parse();
    }, [projectId]);

    // Fetch metadata when file is selected
    useEffect(() => {
        if (!selectedFile?.path) {
            setMetadata(null);
            return;
        }

        // Only fetch for python files
        if (!selectedFile.name.endsWith('.py')) {
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


    return (
        <div className="flex-1 flex overflow-hidden">
            {/* Sidebar: File Tree */}
            <aside className="w-64 bg-slate-950 border-r border-slate-800 flex flex-col">
                {isParsing && (
                    <div className="bg-blue-500/10 text-blue-400 text-xs px-4 py-2 flex items-center gap-2 border-b border-blue-500/20">
                        <Loader2 className="animate-spin w-3 h-3" /> Indexing codebase...
                    </div>
                )}
                <FileTree files={fileTree} onSelectFile={setSelectedFile} />
            </aside>

            {/* Main Content: Code Viewer */}
            <div className="flex-1 bg-slate-900 relative">
                <CodeViewer
                    file={selectedFile}
                    projectId={projectId}
                    scrollToLine={editorLine}
                />
            </div>

            {/* Right Sidebar: Structure */}
            <aside className="w-72 bg-slate-950 border-l border-slate-800 flex flex-col">
                <StructurePanel
                    metadata={metadata}
                    onJumpToLine={(line) => setEditorLine(line)}
                />
            </aside>
        </div>
    );
}
