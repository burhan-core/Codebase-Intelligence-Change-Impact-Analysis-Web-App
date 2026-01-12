import React from 'react';
import { motion } from 'framer-motion';
import { Info, Lock, Eye, FileSearch, CheckCircle2 } from 'lucide-react';

export default function InfoPanel() {
    return (
        <div className="h-full flex flex-col justify-center max-w-lg mx-auto p-4">
            <div className="bg-slate-900/50 border border-slate-800 rounded-2xl p-8 backdrop-blur-sm">
                <h3 className="text-xl font-bold text-white mb-6 flex items-center gap-2">
                    <Info className="w-5 h-5 text-blue-400" />
                    What Happens Next?
                </h3>

                <div className="space-y-6 relative">
                    {/* Timeline Line */}
                    <div className="absolute left-[11px] top-2 bottom-2 w-0.5 bg-slate-800" />

                    {/* Steps */}
                    <div className="relative pl-8">
                        <div className="absolute left-0 top-1 w-6 h-6 bg-slate-900 border border-slate-700 rounded-full flex items-center justify-center z-10">
                            <div className="w-2 h-2 bg-blue-500 rounded-full" />
                        </div>
                        <h4 className="font-semibold text-slate-200">Repository Extraction</h4>
                        <p className="text-sm text-slate-400 mt-1">We clone or unzip your code into a temporary secure sandbox.</p>
                    </div>

                    <div className="relative pl-8">
                        <div className="absolute left-0 top-1 w-6 h-6 bg-slate-900 border border-slate-700 rounded-full flex items-center justify-center z-10">
                            <FileSearch className="w-3 h-3 text-slate-500" />
                        </div>
                        <h4 className="font-semibold text-slate-200">Structural Indexing</h4>
                        <p className="text-sm text-slate-400 mt-1">Files are scanned to build a map of your project geometry.</p>
                    </div>

                    <div className="relative pl-8">
                        <div className="absolute left-0 top-1 w-6 h-6 bg-slate-900 border border-slate-700 rounded-full flex items-center justify-center z-10">
                            <CheckCircle2 className="w-3 h-3 text-green-500" />
                        </div>
                        <h4 className="font-semibold text-slate-200">Ready for Analysis</h4>
                        <p className="text-sm text-slate-400 mt-1">Once indexed, you can run specific impact queries safely.</p>
                    </div>
                </div>

                <div className="mt-8 pt-6 border-t border-slate-800">
                    <h4 className="text-sm font-bold text-slate-300 uppercase tracking-wider mb-4">Security & Privacy</h4>
                    <ul className="space-y-3">
                        <li className="flex items-center gap-3 text-sm text-slate-400">
                            <Lock className="w-4 h-4 text-green-500" />
                            <span>Read-only analysis (no write access)</span>
                        </li>
                        <li className="flex items-center gap-3 text-sm text-slate-400">
                            <Eye className="w-4 h-4 text-green-500" />
                            <span>No external sharing or training</span>
                        </li>
                        <li className="flex items-center gap-3 text-sm text-slate-400">
                            <CheckCircle2 className="w-4 h-4 text-green-500" />
                            <span>Temporary ephemeral workspace</span>
                        </li>
                    </ul>
                </div>
            </div>
        </div>
    );
}
