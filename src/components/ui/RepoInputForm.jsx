import React, { useState } from 'react';
import { Github, ArrowRight, Loader2, AlertCircle } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { api } from '../../lib/api';

const REPO_URL_PATTERN = /^https?:\/\/(www\.)?(github|gitlab)\.com\/[\w.-]+\/[\w.-]+\/?$/;

const EXAMPLES = [
    'https://github.com/pallets/click',
    'https://github.com/psf/requests',
];

export default function RepoInputForm() {
    const [url, setUrl] = useState('');
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState(null);
    const navigate = useNavigate();

    const trimmed = url.trim();
    const isValidUrl = REPO_URL_PATTERN.test(trimmed.replace(/\.git$/, ''));
    const showInvalid = trimmed.length > 10 && !isValidUrl;

    const handleSubmit = async (e) => {
        e.preventDefault();
        if (!isValidUrl || isLoading) return;

        setIsLoading(true);
        setError(null);

        try {
            const data = await api.ingest(trimmed);
            navigate('/overview', { state: { projectId: data.project_id, fileTree: data.file_tree } });
        } catch (err) {
            console.error(err);
            setError(err.message);
            setIsLoading(false);
        }
    };

    return (
        <div className="flex flex-col w-full max-w-lg mx-auto">
            <h2 className="text-2xl font-bold tracking-tight text-zinc-50 mb-2">Analyze a repository</h2>
            <p className="text-sm text-zinc-500 mb-8">
                Public GitHub or GitLab URL. The repository is shallow-cloned and parsed —
                never executed.
            </p>

            <form onSubmit={handleSubmit} className="space-y-4">
                <div>
                    <label htmlFor="repo-url" className="block text-[13px] font-medium text-zinc-400 mb-2">
                        Repository URL
                    </label>
                    <div className="relative">
                        <Github size={16} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-zinc-600" />
                        <input
                            id="repo-url"
                            type="text"
                            autoFocus
                            spellCheck={false}
                            placeholder="https://github.com/owner/repository"
                            className="w-full bg-zinc-900 border border-zinc-800 rounded-md py-2.5 pl-10 pr-4 font-editor text-[13px] text-zinc-200 placeholder:text-zinc-600 focus:outline-none focus:border-blue-600 focus:ring-1 focus:ring-blue-600/50 transition-colors"
                            value={url}
                            onChange={(e) => setUrl(e.target.value)}
                        />
                    </div>
                    {showInvalid && (
                        <p className="mt-2 text-xs text-amber-500/90 flex items-center gap-1.5">
                            <AlertCircle size={12} />
                            Expected format: https://github.com/owner/repository
                        </p>
                    )}
                </div>

                {error && (
                    <div className="p-3 bg-red-500/5 border border-red-500/20 text-red-400 rounded-md text-sm flex items-start gap-2">
                        <AlertCircle size={15} className="mt-0.5 shrink-0" />
                        {error}
                    </div>
                )}

                <button
                    type="submit"
                    disabled={!isValidUrl || isLoading}
                    className={`w-full py-2.5 rounded-md text-sm font-semibold flex items-center justify-center gap-2 transition-colors
                        ${isValidUrl && !isLoading
                            ? 'bg-blue-600 hover:bg-blue-500 text-white'
                            : 'bg-zinc-900 text-zinc-600 cursor-not-allowed border border-zinc-800'
                        }`}
                >
                    {isLoading ? (
                        <>
                            <Loader2 size={16} className="animate-spin" />
                            Cloning &amp; scanning…
                        </>
                    ) : (
                        <>
                            Analyze
                            <ArrowRight size={16} />
                        </>
                    )}
                </button>
            </form>

            <div className="mt-8">
                <p className="text-xs text-zinc-600 mb-2">Try an example</p>
                <div className="flex flex-wrap gap-2">
                    {EXAMPLES.map((ex) => (
                        <button
                            key={ex}
                            type="button"
                            onClick={() => setUrl(ex)}
                            className="font-editor text-xs text-zinc-400 hover:text-zinc-100 border border-zinc-800 hover:border-zinc-700 rounded-md px-2.5 py-1.5 transition-colors"
                        >
                            {ex.replace('https://github.com/', '')}
                        </button>
                    ))}
                </div>
            </div>
        </div>
    );
}
