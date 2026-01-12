import React from 'react';
import { AlertTriangle, Activity, Lock } from 'lucide-react';

export default function AnalysisPlaceholder() {
    return (
        <div className="h-full p-4 space-y-4 overflow-y-auto">
            <div className="px-2 text-xs font-bold text-slate-500 uppercase tracking-wider mb-2">Analysis Tools</div>

            <div className="bg-slate-900 border border-slate-800 rounded-lg p-4 opacity-70">
                <div className="flex items-center justify-between mb-2">
                    <h4 className="font-semibold text-slate-300 flex items-center gap-2">
                        <Activity size={16} /> Impact Analysis
                    </h4>
                    <span className="text-[10px] bg-slate-800 text-slate-500 px-2 py-0.5 rounded-full border border-slate-700">PHASE 2</span>
                </div>
                <p className="text-xs text-slate-500">
                    Dependency graph visualization and impact scoring will appear here.
                </p>
            </div>

            <div className="bg-slate-900 border border-slate-800 rounded-lg p-4 opacity-70">
                <div className="flex items-center justify-between mb-2">
                    <h4 className="font-semibold text-slate-300 flex items-center gap-2">
                        <AlertTriangle size={16} /> Risk Indicators
                    </h4>
                    <span className="text-[10px] bg-slate-800 text-slate-500 px-2 py-0.5 rounded-full border border-slate-700">PHASE 2</span>
                </div>
                <p className="text-xs text-slate-500">
                    High-risk lines and coupling metrics will be calculated after indexing.
                </p>
            </div>
        </div>
    );
}
