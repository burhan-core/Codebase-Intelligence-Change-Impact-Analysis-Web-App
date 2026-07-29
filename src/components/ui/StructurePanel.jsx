import React, { useState } from 'react';
import { Box, Braces, Crosshair, ArrowUpRight, ArrowDownLeft, Loader2, Info, ChevronRight, ChevronDown } from 'lucide-react';
import { api } from '../../lib/api';

const DependencyList = ({ projectId, nodeId, onNavigate }) => {
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

    const renderGroup = (label, Icon, iconCls, items) => (
        <div>
            <div className="flex items-center gap-1.5 text-[11px] text-zinc-500 mb-1">
                <Icon size={11} className={iconCls} /> {label} ({items.length})
            </div>
            {items.length === 0 ? (
                <div className="text-[11px] text-zinc-700 pl-4">none</div>
            ) : (
                <div className="space-y-px">
                    {items.map((item, i) => (
                        <button
                            key={i}
                            title={item.id}
                            className="w-full flex items-center gap-1.5 font-editor text-[11px] text-zinc-400 pl-4 pr-1 py-1 hover:text-zinc-100 hover:bg-zinc-800/60 rounded-sm transition-colors text-left"
                            onClick={(e) => {
                                e.stopPropagation();
                                if (item.file_path && onNavigate) {
                                    onNavigate(item.file_path, item.lineno);
                                }
                            }}
                        >
                            <Box size={9} className="shrink-0 text-zinc-600" />
                            <span className="truncate">{item.label || item.id}</span>
                        </button>
                    ))}
                </div>
            )}
        </div>
    );

    return (
        <div className="ml-5 border-l border-zinc-800/70 pl-2 mb-1">
            <button
                onClick={handleToggle}
                className="flex items-center gap-1 text-[11px] text-zinc-600 hover:text-zinc-300 py-0.5 transition-colors"
            >
                {loading
                    ? <Loader2 size={10} className="animate-spin" />
                    : (expanded ? <ChevronDown size={10} /> : <ChevronRight size={10} />)}
                dependencies
            </button>

            {expanded && data && (
                <div className="space-y-2 py-1">
                    {renderGroup('called by', ArrowDownLeft, 'text-amber-500', data.callers)}
                    {renderGroup('calls', ArrowUpRight, 'text-blue-500', data.callees)}
                </div>
            )}
        </div>
    );
};

function SymbolRow({ icon, name, lineno, onJump, onTarget }) {
    return (
        <div className="group flex items-center gap-2 rounded-sm hover:bg-zinc-800/60 transition-colors pr-1">
            <button
                onClick={onJump}
                className="flex-1 min-w-0 flex items-center gap-2 text-left px-2 py-1.5"
                title={`Jump to line ${lineno}`}
            >
                {icon}
                <span className="font-editor text-xs text-zinc-300 truncate">{name}</span>
                <span className="font-editor text-[10px] text-zinc-600 ml-auto shrink-0">:{lineno}</span>
            </button>
            {onTarget && (
                <button
                    onClick={onTarget}
                    title="Trace impact of changing this"
                    className="opacity-0 group-hover:opacity-100 p-1 rounded text-zinc-500 hover:text-amber-500 hover:bg-zinc-800 transition-all shrink-0"
                >
                    <Crosshair size={12} />
                </button>
            )}
        </div>
    );
}

export default function StructurePanel({ metadata, selectedFile, projectId, onJumpToLine, onNavigate, onTargetImpact }) {
    if (!selectedFile) {
        return (
            <div className="h-full flex flex-col items-center justify-center text-zinc-600 p-6 text-center gap-3">
                <Braces size={26} strokeWidth={1.5} />
                <p className="text-sm">Open a file to inspect its symbols.</p>
            </div>
        );
    }

    if (!selectedFile.name?.endsWith('.py')) {
        return (
            <div className="h-full flex flex-col items-center justify-center text-zinc-600 p-6 text-center gap-3">
                <Info size={22} strokeWidth={1.5} />
                <p className="text-sm text-zinc-500 leading-relaxed max-w-[220px]">
                    Only <span className="font-editor text-zinc-300">.py</span> files are analyzed.
                    This file is browsable but has no symbol data.
                </p>
            </div>
        );
    }

    if (!metadata) {
        return (
            <div className="h-full flex items-center justify-center gap-2 text-zinc-600 text-sm">
                <Loader2 size={13} className="animate-spin" /> Loading symbols…
            </div>
        );
    }

    const { classes = [], functions = [], relative_path: rawPath } = metadata;
    const relative_path = rawPath?.replace(/\\/g, '/');
    const globalFunctions = functions.filter((f) => !f.parent);

    if (!classes.length && !globalFunctions.length) {
        return (
            <div className="h-full flex flex-col items-center justify-center text-zinc-600 p-6 text-center gap-3">
                <Braces size={22} strokeWidth={1.5} />
                <p className="text-sm">No classes or functions in this file.</p>
            </div>
        );
    }

    const target = (nodeId, label) => onTargetImpact && (() => onTargetImpact({
        nodeId,
        label,
        filePath: relative_path,
    }));

    return (
        <div className="h-full overflow-y-auto">
            <div className="p-4 space-y-5">
                {classes.length > 0 && (
                    <div>
                        <h4 className="text-[11px] font-semibold text-zinc-600 mb-1.5 uppercase tracking-wider">Classes</h4>
                        {classes.map((cls) => (
                            <div key={cls.name} className="mb-1">
                                <SymbolRow
                                    icon={<Box size={13} className="text-amber-500 shrink-0" />}
                                    name={cls.name}
                                    lineno={cls.lineno}
                                    onJump={() => onJumpToLine(cls.lineno)}
                                />
                                {cls.methods?.map((method) => {
                                    const nodeId = `${relative_path}::${cls.name}.${method.name}`;
                                    return (
                                        <div key={method.name + method.lineno} className="ml-4">
                                            <SymbolRow
                                                icon={<Braces size={12} className="text-blue-500 shrink-0" />}
                                                name={method.name}
                                                lineno={method.lineno}
                                                onJump={() => onJumpToLine(method.lineno)}
                                                onTarget={target(nodeId, `${cls.name}.${method.name}`)}
                                            />
                                            <DependencyList projectId={projectId} nodeId={nodeId} onNavigate={onNavigate} />
                                        </div>
                                    );
                                })}
                            </div>
                        ))}
                    </div>
                )}

                {globalFunctions.length > 0 && (
                    <div>
                        <h4 className="text-[11px] font-semibold text-zinc-600 mb-1.5 uppercase tracking-wider">Functions</h4>
                        {globalFunctions.map((func) => {
                            const nodeId = `${relative_path}::${func.name}`;
                            return (
                                <div key={func.name + func.lineno}>
                                    <SymbolRow
                                        icon={<Braces size={12} className="text-blue-500 shrink-0" />}
                                        name={func.name}
                                        lineno={func.lineno}
                                        onJump={() => onJumpToLine(func.lineno)}
                                        onTarget={target(nodeId, func.name)}
                                    />
                                    <DependencyList projectId={projectId} nodeId={nodeId} onNavigate={onNavigate} />
                                </div>
                            );
                        })}
                    </div>
                )}
            </div>
        </div>
    );
}
