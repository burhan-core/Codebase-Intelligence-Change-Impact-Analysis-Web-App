import React from 'react';
import { Box, Play, BoxSelect } from 'lucide-react';

export default function StructurePanel({ metadata, onJumpToLine }) {
    if (!metadata) {
        return (
            <div className="h-full flex flex-col items-center justify-center text-slate-500 p-6 text-center">
                <BoxSelect size={32} className="mb-3 opacity-40" />
                <p className="text-sm">Select a python file to view its structure.</p>
            </div>
        );
    }

    const { classes, functions, imports } = metadata;

    // Render nothing if empty (non-python file or empty)
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
            <div className="p-4 border-b border-slate-800/50 bg-[#0c0e12]/90 sticky top-0 backdrop-blur-sm z-10">
                <h3 className="font-bold text-slate-300 text-xs uppercase tracking-wider flex items-center gap-2">
                    <Box size={14} className="text-blue-400" /> Symbol Map
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
                                    <button
                                        onClick={() => onJumpToLine(cls.lineno)}
                                        className="w-full text-left flex items-center gap-2 text-sm text-slate-300 hover:text-blue-400 hover:bg-slate-900/50 p-1.5 rounded transition-all"
                                    >
                                        <Box size={14} className="text-orange-400" />
                                        <span className="font-mono">{cls.name}</span>
                                    </button>
                                    {/* Methods */}
                                    {cls.methods?.map((method, mIdx) => (
                                        <button
                                            key={mIdx}
                                            onClick={() => onJumpToLine(method.lineno)}
                                            className="w-full text-left flex items-center gap-2 text-xs text-slate-400 hover:text-blue-300 hover:bg-slate-900/30 py-1 px-2 rounded ml-4 transition-all"
                                        >
                                            <Play size={10} className="text-blue-400" />
                                            <span className="font-mono">{method.name}</span>
                                            <span className="text-slate-600 text-[10px] ml-auto">L{method.lineno}</span>
                                        </button>
                                    ))}
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
                            {functions.map((func, idx) => (
                                <button
                                    key={idx}
                                    onClick={() => onJumpToLine(func.lineno)}
                                    className="w-full text-left flex items-center gap-2 text-sm text-slate-300 hover:text-blue-400 hover:bg-slate-900/50 p-1.5 rounded transition-all group"
                                >
                                    <Play size={14} className="text-green-400" />
                                    <span className="font-mono truncate">{func.name}</span>
                                    <span className="text-slate-600 text-xs ml-auto group-hover:text-slate-500">L{func.lineno}</span>
                                </button>
                            ))}
                        </div>
                    </div>
                )}

                {/* Imports Details (Can be expandable) */}
                {imports.length > 0 && (
                    <div>
                        <h4 className="text-xs font-semibold text-slate-500 mb-2 uppercase">Dependencies</h4>
                        <div className="text-xs text-slate-400 font-mono bg-slate-900/40 p-2 rounded max-h-32 overflow-y-auto">
                            {imports.map((imp, idx) => (
                                <div key={idx} className="truncate" title={imp.module}>
                                    {imp.from_module ? `from ${imp.from_module} import ${imp.alias || imp.module}` : `import ${imp.module}`}
                                </div>
                            ))}
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
}
