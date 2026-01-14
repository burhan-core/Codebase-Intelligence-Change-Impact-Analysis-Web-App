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


    // Navigation handler for dependencies
    const handleNavigate = (path, line) => {
        // Normalize path separators to match file tree data if needed, or just use as is
        // The CodeViewer just needs path
        const fileName = path.split(/[\\/]/).pop();

        setSelectedFile({
            name: fileName,
            path: path,
            language: 'python' // Assumption based on context
        });

        if (line) {
            setEditorLine(line);
        }
    };

    return (
        <div className="flex-1 flex overflow-hidden">
            {/* Sidebar: File Tree */}
            <aside className="w-64 flex flex-col border-r border-indigo-500/10 bg-[#030014]/40 backdrop-blur-sm">
                {isParsing && (
                    <div className="bg-indigo-500/10 text-indigo-400 text-xs px-4 py-3 flex items-center gap-2 border-b border-indigo-500/10 font-bold tracking-wide">
                        <Loader2 className="animate-spin w-3 h-3" /> Indexing...
                    </div>
                )}
                <FileTree files={fileTree} onSelectFile={setSelectedFile} />
            </aside>

            {/* Main Content: Code Viewer (Floating Panel Effect) */}
            <div className="flex-1 flex flex-col min-w-0 p-3">
                <div className="flex-1 bg-[#0c0e12]/80 backdrop-blur-md rounded-xl border border-indigo-500/20 overflow-hidden shadow-2xl relative">
                    <CodeViewer
                        file={selectedFile}
                        projectId={projectId}
                        scrollToLine={editorLine}
                    />
                </div>
            </div>

            {/* Right Sidebar: Structure */}
            <aside className="w-72 flex flex-col border-l border-indigo-500/10 bg-[#030014]/40 backdrop-blur-sm">
                <StructurePanel
                    metadata={metadata}
                    projectId={projectId}
                    onJumpToLine={(line) => setEditorLine(line)}
                    onNavigate={handleNavigate}
                />
            </aside>
        </div>
    );
}
