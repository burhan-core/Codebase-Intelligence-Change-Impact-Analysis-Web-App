import React from 'react';
import { motion as Motion } from 'framer-motion';
import { GitBranch, FileCode2, Network } from 'lucide-react';
import RepoInputForm from '../components/ui/RepoInputForm';

const pipeline = [
    { icon: GitBranch, title: 'Clone', text: 'Shallow-cloned into isolated storage. Read-only from here on.' },
    { icon: FileCode2, title: 'Parse', text: 'Each Python file becomes an AST: symbols, imports, and calls.' },
    { icon: Network, title: 'Graph', text: 'Files and functions are linked into a queryable dependency graph.' },
];

export default function InputPage() {
    return (
        <div className="flex-1 grid lg:grid-cols-2 overflow-y-auto">
            {/* Left: form */}
            <Motion.div
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.4 }}
                className="flex items-center justify-center p-8 lg:border-r border-zinc-900"
            >
                <RepoInputForm />
            </Motion.div>

            {/* Right: what happens next */}
            <Motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ duration: 0.4, delay: 0.15 }}
                className="hidden lg:flex items-center justify-center p-8 bg-zinc-900/20"
            >
                <div className="max-w-sm w-full">
                    <p className="font-editor text-[11px] tracking-wide text-zinc-600 mb-6">WHAT HAPPENS NEXT</p>
                    <ol className="space-y-8 relative">
                        <div className="absolute left-[15px] top-2 bottom-2 w-px bg-zinc-800" />
                        {pipeline.map(({ icon: Icon, title, text }) => (
                            <li key={title} className="flex gap-4 relative">
                                <span className="w-8 h-8 rounded-md bg-zinc-900 border border-zinc-800 flex items-center justify-center shrink-0 z-10">
                                    <Icon size={14} className="text-blue-500" />
                                </span>
                                <div>
                                    <p className="text-sm font-semibold text-zinc-200">{title}</p>
                                    <p className="text-sm text-zinc-500 leading-relaxed mt-1">{text}</p>
                                </div>
                            </li>
                        ))}
                    </ol>
                </div>
            </Motion.div>
        </div>
    );
}
