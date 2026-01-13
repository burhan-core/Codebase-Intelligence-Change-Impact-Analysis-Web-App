import React from 'react';
import { Link } from 'react-router-dom';
import { Binoculars } from 'lucide-react';

export default function Navbar() {
    return (
        <nav className="h-14 border-b border-indigo-500/10 bg-[#030014]/80 backdrop-blur-md flex items-center px-6 justify-between select-none sticky top-0 z-50">
            <Link to="/" className="flex items-center gap-3 group">
                <div className="p-1.5 bg-indigo-500/10 rounded-lg group-hover:bg-indigo-500/20 transition-colors">
                    <Binoculars size={20} className="text-indigo-400" />
                </div>
                <span className="font-bold tracking-tight text-indigo-100 group-hover:text-white transition-colors">
                    RepoSpy
                </span>
            </Link>
            <div className="flex items-center gap-4">
                <span className="text-[10px] font-bold tracking-widest text-indigo-400/60">
                    INTELLIGENCE
                </span>
            </div>
        </nav>
    );
}
