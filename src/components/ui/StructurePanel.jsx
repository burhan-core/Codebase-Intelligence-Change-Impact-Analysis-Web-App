import React, { useState } from 'react';
import { Box, Play, BoxSelect, ArrowUpRight, ArrowDownLeft, Loader2 } from 'lucide-react';
import { api } from '../../lib/api';

const DependencyList = ({ projectId, nodeId, type, onJumpToLine, onNavigate }) => {
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(false);
    const [expanded, setExpanded] = useState(false);

    const handleToggle = async (e) => {
        e.stopPropagation();
        if (!expanded && !data) {
            setLoading(true);
            try {
                const res = await api.getDependencies(projectId, nodeId);
                setData(res);
            } catch (err) {
                console.error(err);
            } finally {
                setLoading(false);
            }
        }
        setExpanded(!expanded);
    };

    if (!nodeId) return null;

    return (
        <div className="mt-1 ml-4 border-l border-slate-800/50 pl-2">
            <button
                onClick={handleToggle}
                className="flex items-center gap-1.5 text-[10px] uppercase font-bold text-slate-500 hover:text-indigo-400 mb-1"
            >
                {loading ? <Loader2 size={10} className="animate-spin" /> : (expanded ? 'Hide Dependencies' : 'Show Dependencies')}
            </button>

            {expanded && data && (
                <div className="space-y-2 animate-in fade-in slide-in-from-top-1 duration-200">
                    {/* Callers */}
                    <div>
                        <div className="flex items-center gap-1 text-[10px] text-indigo-300/60 mb-1">
                            <ArrowDownLeft size={10} /> Called By ({data.callers.length})
                        </div>
                        {data.callers.length === 0 ? <div className="text-[10px] text-slate-700 italic pl-3">None</div> : (
                            <div className="space-y-0.5">
                                {data.callers.map((caller, i) => (
                                    <div
                                        key={i}
                                        className="flex items-center gap-1 text-[10px] text-indigo-200/80 pl-2 hover:text-white cursor-pointer hover:bg-white/5 rounded py-0.5 transition-colors"
                                        title={caller.id}
                                        onClick={(e) => {
                                            e.stopPropagation();
                                            if (caller.file_path && onNavigate) {
                                                onNavigate(caller.file_path, caller.lineno);
                                            }
                                        }}
                                    >
                                        <Box size={8} /> {caller.label || caller.id}
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>

                    {/* Callees */}
                    <div>
                        <div className="flex items-center gap-1 text-[10px] text-emerald-300/60 mb-1">
                            <ArrowUpRight size={10} /> Calls ({data.callees.length})
                        </div>
                        {data.callees.length === 0 ? <div className="text-[10px] text-slate-700 italic pl-3">None</div> : (
                            <div className="space-y-0.5">
                                {data.callees.map((callee, i) => (
                                    <div
                                        key={i}
                                        className="flex items-center gap-1 text-[10px] text-emerald-200/80 pl-2 hover:text-white cursor-pointer hover:bg-white/5 rounded py-0.5 transition-colors"
                                        title={callee.id}
                                        onClick={(e) => {
                                            e.stopPropagation();
                                            if (callee.file_path && onNavigate) {
                                                onNavigate(callee.file_path, callee.lineno);
                                            }
                                        }}
                                    >
                                        <Box size={8} /> {callee.label || callee.id}
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>
                </div>
            )}
        </div>
    );
};

export default function StructurePanel({ metadata, projectId, onJumpToLine, onNavigate }) {
    if (!metadata) {
        return (
            <div className="h-full flex flex-col items-center justify-center text-slate-500 p-6 text-center">
                <BoxSelect size={32} className="mb-3 opacity-40" />
                <p className="text-sm">Select a python file to view its structure.</p>
            </div>
        );
    }

    const { classes, functions, imports, relative_path: rawPath } = metadata;
    const relative_path = rawPath?.replace(/\\/g, '/');

    if (!classes?.length && !functions?.length) {
        return (
            <div className="h-full p-4 text-slate-500 text-sm">
                <h3 className="font-bold text-slate-400 mb-4 uppercase text-xs tracking-wider">Structure</h3>
                <p>No symbols found.</p>
            </div>
        );
    }

    return (
        <div className="h-full overflow-y-auto custom-scrollbar flex flex-col bg-transparent">
            <div className="p-4 border-b border-indigo-500/10 bg-[#0c0e12]/90 sticky top-0 backdrop-blur-sm z-10">
                <h3 className="font-bold text-indigo-200/80 text-xs uppercase tracking-wider flex items-center gap-2">
                    <Box size={14} className="text-indigo-400" /> Symbol Map
                </h3>
            </div>

            <div className="p-4 space-y-6">
                {/* Classes */}
                {classes.length > 0 && (
                    <div>
                        <h4 className="text-xs font-semibold text-slate-500 mb-2 uppercase">Classes</h4>
                        <div className="space-y-1">
                            {classes.map((cls, idx) => (
                                <div key={idx} className="group">
                                    <div className="flex flex-col">
                                        <button
                                            onClick={() => onJumpToLine(cls.lineno)}
                                            className="w-full text-left flex items-center gap-2 text-sm text-slate-300 hover:text-indigo-400 hover:bg-white/5 p-1.5 rounded transition-all"
                                        >
                                            <Box size={14} className="text-orange-400" />
                                            <span className="font-mono">{cls.name}</span>
                                        </button>
                                    </div>

                                    {/* Methods */}
                                    {cls.methods?.map((method, mIdx) => {
                                        const nodeId = `${relative_path}::${cls.name}.${method.name}`;
                                        return (
                                            <div key={mIdx} className="ml-4">
                                                <button
                                                    onClick={() => onJumpToLine(method.lineno)}
                                                    className="w-full text-left flex items-center gap-2 text-xs text-slate-400 hover:text-indigo-300 hover:bg-white/5 py-1 px-2 rounded transition-all"
                                                >
                                                    <Play size={10} className="text-indigo-400" />
                                                    <span className="font-mono">{method.name}</span>
                                                    <span className="text-slate-600 text-[10px] ml-auto">L{method.lineno}</span>
                                                </button>
                                                {/* Dependencies */}
                                                <DependencyList
                                                    projectId={projectId}
                                                    nodeId={nodeId}
                                                    onJumpToLine={onJumpToLine}
                                                    onNavigate={onNavigate}
                                                />
                                            </div>
                                        );
                                    })}
                                </div>
                            ))}
                        </div>
                    </div>
                )}

                {/* Global Functions */}
                {functions.length > 0 && (
                    <div>
                        <h4 className="text-xs font-semibold text-slate-500 mb-2 uppercase">Global Functions</h4>
                        <div className="space-y-1">
                            {functions.map((func, idx) => {
                                const nodeId = `${relative_path}::${func.name}`;
                                return (
                                    <div key={idx} className="flex flex-col">
                                        <button
                                            onClick={() => onJumpToLine(func.lineno)}
                                            className="w-full text-left flex items-center gap-2 text-sm text-slate-300 hover:text-indigo-400 hover:bg-white/5 p-1.5 rounded transition-all group"
                                        >
                                            <Play size={14} className="text-emerald-400" />
                                            <span className="font-mono truncate">{func.name}</span>
                                            <span className="text-slate-600 text-xs ml-auto group-hover:text-slate-500">L{func.lineno}</span>
                                        </button>
                                        <DependencyList
                                            projectId={projectId}
                                            nodeId={nodeId}
                                            onJumpToLine={onJumpToLine}
                                            onNavigate={onNavigate}
                                        />
                                    </div>
                                );
                            })}
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
}
