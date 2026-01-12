import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { Github, UploadCloud, FolderUp, CheckCircle2, ArrowRight } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { api } from '../../lib/api';

export default function RepoInputForm() {
    const [url, setUrl] = useState('');
    const [isDragging, setIsDragging] = useState(false);
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState(null);
    const navigate = useNavigate();

    const isValidUrl = url.includes('github.com') || url.includes('gitlab.com');
    const canProceed = isValidUrl;

    const handleSubmit = async (e) => {
        e.preventDefault();
        if (!canProceed) return;

        setIsLoading(true);
        setError(null);

        try {
            const data = await api.ingest(url);
            navigate('/overview', { state: { projectId: data.project_id, fileTree: data.file_tree } });
        } catch (err) {
            console.error(err);
            setError(err.message);
            setIsLoading(false);
        }
    };

    return (
        <div className="flex flex-col gap-8 w-full max-w-lg mx-auto">
            <div className="mb-4">
                <h2 className="text-3xl font-bold text-white mb-2">Import Repository</h2>
                <p className="text-slate-400">Provide a URL or upload a minimal ZIP archive.</p>
                {error && (
                    <div className="mt-4 p-3 bg-red-500/10 border border-red-500/20 text-red-400 rounded-lg text-sm">
                        Error: {error}
                    </div>
                )}
            </div>

            {/* GitHub Input */}
            <form onSubmit={handleSubmit} className="space-y-4">
                <div className="space-y-2">
                    <label className="text-sm font-medium text-slate-300 ml-1">GitHub Repository URL</label>
                    <div className="relative group">
                        <Github className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-500 group-focus-within:text-blue-400 transition-colors" />
                        <input
                            type="text"
                            placeholder="https://github.com/username/project"
                            className="w-full bg-slate-900 border border-slate-700 rounded-lg py-3 pl-12 pr-4 text-slate-200 focus:outline-none focus:ring-2 focus:ring-blue-500/50 focus:border-blue-500 transition-all"
                            value={url}
                            onChange={(e) => setUrl(e.target.value)}
                        />
                    </div>
                </div>

                <div className="relative flex items-center py-4">
                    <div className="flex-grow border-t border-slate-800"></div>
                    <span className="flex-shrink-0 mx-4 text-slate-600 font-mono text-sm">OR</span>
                    <div className="flex-grow border-t border-slate-800"></div>
                </div>

                {/* Mock Drop Zone */}
                <div
                    className={`border-2 border-dashed rounded-xl p-8 flex flex-col items-center justify-center text-center transition-colors cursor-pointer ${isDragging ? 'border-blue-500 bg-blue-500/5' : 'border-slate-800 hover:border-slate-600 bg-slate-900/50'}`}
                    onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
                    onDragLeave={() => setIsDragging(false)}
                    onDrop={(e) => { e.preventDefault(); setIsDragging(false); }}
                >
                    <FolderUp className="w-10 h-10 text-slate-600 mb-4" />
                    <p className="text-slate-300 font-medium">Drag & Drop ZIP here</p>
                    <p className="text-sm text-slate-500 mt-1">or click to browse</p>
                </div>

                <button
                    type="submit"
                    disabled={!canProceed || isLoading}
                    className={`w-full py-4 rounded-lg font-bold flex items-center justify-center gap-2 transition-all mt-8
            ${canProceed && !isLoading
                            ? 'bg-blue-600 hover:bg-blue-500 text-white shadow-lg shadow-blue-900/20 hover:scale-[1.02]'
                            : 'bg-slate-800 text-slate-500 cursor-not-allowed'
                        }`}
                >
                    {isLoading ? (
                        <>
                            <motion.div
                                animate={{ rotate: 360 }}
                                transition={{ duration: 1, repeat: Infinity, ease: "linear" }}
                                className="w-5 h-5 border-2 border-white/20 border-t-white rounded-full"
                            />
                            Loading Repository...
                        </>
                    ) : (
                        <>
                            Load Repository <ArrowRight className="w-5 h-5" />
                        </>
                    )}
                </button>
            </form>
        </div>
    );
}
