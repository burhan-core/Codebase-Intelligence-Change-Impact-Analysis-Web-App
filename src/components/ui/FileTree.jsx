import React, { useState } from 'react';
import { ChevronRight, ChevronDown, FileCode, Folder, FolderOpen } from 'lucide-react';

const mockFileSystem = [
    {
        name: 'src',
        type: 'folder',
        children: [
            {
                name: 'components',
                type: 'folder',
                children: [
                    { name: 'Button.jsx', type: 'file', language: 'javascript' },
                    { name: 'Header.jsx', type: 'file', language: 'javascript' },
                    { name: 'Modal.jsx', type: 'file', language: 'javascript' },
                ]
            },
            {
                name: 'utils',
                type: 'folder',
                children: [
                    { name: 'api.js', type: 'file', language: 'javascript' },
                    { name: 'helpers.js', type: 'file', language: 'javascript' },
                ]
            },
            { name: 'App.jsx', type: 'file', language: 'javascript' },
            { name: 'index.css', type: 'file', language: 'css' },
        ]
    },
    { name: 'package.json', type: 'file', language: 'json' },
    { name: 'README.md', type: 'file', language: 'markdown' },
    { name: 'vite.config.js', type: 'file', language: 'javascript' },
];

const FileItem = ({ item, level, onSelect }) => {
    const [isOpen, setIsOpen] = useState(true);

    const handleToggle = (e) => {
        e.stopPropagation();
        setIsOpen(!isOpen);
    };

    const handleClick = () => {
        if (item.type === 'folder') {
            setIsOpen(!isOpen);
        } else {
            onSelect(item);
        }
    };

    return (
        <div>
            <div
                className={`flex items-center py-1 px-2 hover:bg-slate-800 cursor-pointer text-sm select-none
          ${item.type === 'file' ? 'text-slate-300' : 'text-slate-100 font-medium'}
        `}
                style={{ paddingLeft: `${level * 12 + 8}px` }}
                onClick={handleClick}
            >
                <span className="mr-1.5 opacity-70">
                    {item.type === 'folder' ? (
                        isOpen ? <FolderOpen size={16} className="text-blue-400" /> : <Folder size={16} className="text-blue-400" />
                    ) : (
                        <FileCode size={16} className="text-slate-500" />
                    )}
                </span>
                <span className="truncate">{item.name}</span>
            </div>

            {item.type === 'folder' && isOpen && item.children && (
                <div>
                    {item.children.map((child, idx) => (
                        <FileItem key={idx} item={child} level={level + 1} onSelect={onSelect} />
                    ))}
                </div>
            )}
        </div>
    );
};

export default function FileTree({ files, onSelectFile }) {
    if (!files) return null;

    return (
        <div className="h-full overflow-y-auto py-2">
            <div className="px-4 py-2 text-xs font-bold text-slate-500 uppercase tracking-wider mb-2">Explorer</div>
            {files.map((item, idx) => (
                <FileItem key={idx} item={item} level={0} onSelect={onSelectFile} />
            ))}
        </div>
    );
}
