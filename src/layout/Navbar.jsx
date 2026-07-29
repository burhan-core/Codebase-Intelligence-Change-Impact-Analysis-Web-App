import React from 'react';
import { Link } from 'react-router-dom';
import { Aperture } from 'lucide-react';

export default function Navbar() {
    return (
        <nav className="h-12 border-b border-zinc-800 bg-zinc-950 flex items-center px-5 justify-between select-none sticky top-0 z-50 shrink-0">
            <Link to="/" className="flex items-center gap-2.5 group">
                <Aperture size={18} className="text-blue-500" strokeWidth={2.25} />
                <span className="font-semibold text-[15px] tracking-tight text-zinc-100 group-hover:text-white transition-colors">
                    Impact Lens
                </span>
            </Link>
            <span className="font-editor text-[11px] text-zinc-600">
                static analysis · read-only
            </span>
        </nav>
    );
}
