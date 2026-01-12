import React from 'react';
import { Link } from 'react-router-dom';
import { Terminal } from 'lucide-react';

export default function Navbar() {
    return (
        <nav className="h-14 border-b border-slate-800 bg-slate-950 flex items-center px-6 justify-between select-none">
            <Link to="/" className="flex items-center gap-2 text-slate-100 hover:text-blue-400 transition-colors">
                <Terminal size={20} className="text-blue-500" />
                <span className="font-semibold tracking-tight">Codebase Intelligence</span>
            </Link>
            <div className="flex items-center gap-4">
                <span className="text-xs font-mono text-slate-500 px-2 py-1 bg-slate-900 rounded border border-slate-800">
                    PHASE 1: INGESTION
                </span>
            </div>
        </nav>
    );
}
