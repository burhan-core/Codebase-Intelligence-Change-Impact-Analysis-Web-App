import React, { useEffect, useState } from 'react';
import { Crosshair, Loader2, AlertCircle, FileCode2, CornerDownRight } from 'lucide-react';
import AiInsight from './AiInsight';
import { api } from '../../lib/api';

function groupByFile(impacted) {
    const groups = new Map();
    for (const node of impacted) {
        const file = node.file_path || node.id;
        if (!groups.has(file)) groups.set(file, []);
        groups.get(file).push(node);
    }
    for (const nodes of groups.values()) {
        nodes.sort((a, b) => a.depth - b.depth);
    }
    return [...groups.entries()].sort((a, b) => a[1][0].depth - b[1][0].depth);
}

function Stat({ value, label }) {
    return (
        <div className="flex-1 rounded-md border border-zinc-800 bg-zinc-900/40 px-3 py-2">
            <div className="text-lg font-semibold text-zinc-100 leading-none">{value}</div>
            <div className="text-[11px] text-zinc-500 mt-1">{label}</div>
        </div>
    );
}

export default function ImpactPanel({ projectId, target, onNavigate }) {
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);

    useEffect(() => {
        if (!target?.nodeId) {
            setData(null);
            return;
        }
        const fetchImpact = async () => {
            setLoading(true);
            setError(null);
            try {
                const res = await api.getImpact(projectId, target.nodeId);
                setData(res);
            } catch (err) {
                console.error(err);
                setError('Could not compute impact for this symbol.');
                setData(null);
            } finally {
                setLoading(false);
            }
        };
        fetchImpact();
    }, [projectId, target]);

    if (!target) {
        return (
            <div className="h-full flex flex-col items-center justify-center text-center p-6 gap-3">
                <Crosshair size={28} strokeWidth={1.5} className="text-zinc-700" />
                <p className="text-sm text-zinc-500 max-w-[220px] leading-relaxed">
                    Target any function in the <span className="text-zinc-300">Symbols</span> tab
                    to trace its blast radius.
                </p>
            </div>
        );
    }

    if (loading) {
        return (
            <div className="h-full flex items-center justify-center gap-2 text-zinc-500 text-sm">
                <Loader2 size={14} className="animate-spin" /> Tracing callers…
            </div>
        );
    }

    if (error) {
        return (
            <div className="h-full flex flex-col items-center justify-center gap-2 text-sm text-red-400 p-6 text-center">
                <AlertCircle size={18} />
                {error}
            </div>
        );
    }

    if (!data) return null;

    const { impacted, summary } = data;
    const groups = groupByFile(impacted);

    return (
        <div className="h-full overflow-y-auto">
            <div className="p-4 border-b border-zinc-800 sticky top-0 bg-zinc-950/95 backdrop-blur-sm z-10">
                <div className="flex items-center gap-2 mb-1">
                    <Crosshair size={13} className="text-amber-500" />
                    <span className="font-editor text-[13px] text-zinc-100 truncate">{target.label}</span>
                </div>
                <p className="font-editor text-[11px] text-zinc-600 truncate">{target.filePath}</p>
            </div>

            <div className="p-4 space-y-4">
                <div className="flex gap-2">
                    <Stat value={summary.total_impacted} label="affected" />
                    <Stat value={summary.impacted_files.length} label="files" />
                    <Stat value={summary.max_depth_reached} label="max depth" />
                </div>

                {impacted.length === 0 ? (
                    <p className="text-sm text-zinc-500 leading-relaxed pt-2">
                        Nothing depends on this symbol — changing it is contained to its own file.
                    </p>
                ) : (
                    <div className="space-y-4 pb-1">
                        {groups.map(([file, nodes]) => (
                            <div key={file}>
                                <div className="flex items-center gap-1.5 mb-1.5">
                                    <FileCode2 size={12} className="text-zinc-600 shrink-0" />
                                    <span className="font-editor text-[11px] text-zinc-500 truncate" title={file}>{file}</span>
                                </div>
                                <div className="space-y-px">
                                    {nodes.map((node) => (
                                        <button
                                            key={node.id}
                                            onClick={() => node.file_path && onNavigate(node.file_path, node.lineno)}
                                            title={node.id}
                                            className="w-full flex items-center gap-2 text-left pl-4 pr-2 py-1.5 rounded-sm hover:bg-zinc-800/60 transition-colors group"
                                        >
                                            <CornerDownRight size={11} className="text-zinc-700 shrink-0" />
                                            <span className="font-editor text-xs text-zinc-300 group-hover:text-zinc-100 truncate">
                                                {node.label || node.id}
                                            </span>
                                            <span className="ml-auto flex items-center gap-1.5 shrink-0">
                                                {node.confidence === 'possible' && (
                                                    <span className="font-editor text-[10px] text-zinc-600 border border-zinc-800 rounded px-1">?</span>
                                                )}
                                                <span className={`font-editor text-[10px] rounded px-1.5 py-0.5
                                                    ${node.depth === 1
                                                        ? 'bg-amber-500/10 text-amber-500'
                                                        : 'bg-zinc-800 text-zinc-500'}`}>
                                                    d{node.depth}
                                                </span>
                                            </span>
                                        </button>
                                    ))}
                                </div>
                            </div>
                        ))}
                    </div>
                )}

                <AiInsight projectId={projectId} target={target} />
            </div>
        </div>
    );
}
