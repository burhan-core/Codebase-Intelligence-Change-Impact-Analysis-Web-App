import React, { useState, useEffect } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import FileTree from '../components/ui/FileTree';
import CodeViewer from '../components/ui/CodeViewer';
import AnalysisPlaceholder from '../components/ui/AnalysisPlaceholder';
import { PanelLeft, PanelRight } from 'lucide-react';

export default function OverviewPage() {
    const { state } = useLocation();
    const navigate = useNavigate();
    const [selectedFile, setSelectedFile] = useState(null);

    // Redirect if no state (direct access protection)
    useEffect(() => {
        if (!state?.projectId || !state?.fileTree) {
            navigate('/input');
        }
    }, [state, navigate]);

    if (!state) return null;

    const { projectId, fileTree } = state;

    // Default select first file is not needed as tree is dynamic

    return (
        <div className="flex-1 flex overflow-hidden">
            {/* Sidebar: File Tree */}
            <aside className="w-64 bg-slate-950 border-r border-slate-800 flex flex-col">
                <FileTree files={fileTree} onSelectFile={setSelectedFile} />
            </aside>

            {/* Main Content: Code Viewer */}
            <div className="flex-1 bg-slate-900 relative">
                <CodeViewer file={selectedFile} projectId={projectId} />
            </div>

            {/* Right Sidebar: Analysis */}
            <aside className="w-72 bg-slate-950 border-l border-slate-800 flex flex-col">
                <AnalysisPlaceholder />
            </aside>
        </div>
    );
}
