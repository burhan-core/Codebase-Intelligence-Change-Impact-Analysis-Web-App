import React, { useMemo, useState } from 'react';
import { ChevronRight, ChevronDown, Folder, FolderOpen, FileCode, FileText, FileJson, File } from 'lucide-react';

// Analyzable files get the accent color so users can see at a glance
// which parts of the tree the engine understands.
function fileIcon(name) {
    if (name.endsWith('.py')) return { Icon: FileCode, cls: 'text-blue-500' };
    if (/\.(js|jsx|ts|tsx|mjs|cjs)$/.test(name)) return { Icon: FileCode, cls: 'text-zinc-500' };
    if (/\.(json|ya?ml|toml)$/.test(name)) return { Icon: FileJson, cls: 'text-zinc-500' };
    if (/\.(md|txt|rst)$/.test(name)) return { Icon: FileText, cls: 'text-zinc-500' };
    return { Icon: File, cls: 'text-zinc-600' };
}

function sortEntries(items) {
    return [...items].sort((a, b) => {
        if (a.type !== b.type) return a.type === 'folder' ? -1 : 1;
        return a.name.localeCompare(b.name);
    });
}

const FileItem = React.memo(({ item, level, onSelect, selectedPath }) => {
    const [isOpen, setIsOpen] = useState(level < 1);
    const isFolder = item.type === 'folder';
    const isSelected = !isFolder && selectedPath === item.path;
    const { Icon, cls } = isFolder ? {} : fileIcon(item.name);

    const handleClick = () => {
        if (isFolder) setIsOpen(!isOpen);
        else onSelect(item);
    };

    return (
        <div>
            <div
                className={`flex items-center gap-1.5 py-[3px] px-2 cursor-pointer text-[13px] select-none rounded-sm transition-colors
                    ${isSelected ? 'bg-blue-600/15 text-zinc-100' : 'hover:bg-zinc-800/60'}
                    ${isFolder ? 'text-zinc-300' : 'text-zinc-400'}`}
                style={{ paddingLeft: `${level * 14 + 8}px` }}
                onClick={handleClick}
            >
                {isFolder ? (
                    <>
                        {isOpen
                            ? <ChevronDown size={13} className="text-zinc-600 shrink-0" />
                            : <ChevronRight size={13} className="text-zinc-600 shrink-0" />}
                        {isOpen
                            ? <FolderOpen size={14} className="text-zinc-500 shrink-0" />
                            : <Folder size={14} className="text-zinc-500 shrink-0" />}
                    </>
                ) : (
                    <Icon size={14} className={`${cls} shrink-0 ml-[17px]`} />
                )}
                <span className="truncate">{item.name}</span>
            </div>

            {isFolder && isOpen && item.children && (
                <div>
                    {sortEntries(item.children).map((child) => (
                        <FileItem
                            key={child.path || child.name}
                            item={child}
                            level={level + 1}
                            onSelect={onSelect}
                            selectedPath={selectedPath}
                        />
                    ))}
                </div>
            )}
        </div>
    );
});

export default function FileTree({ files, onSelectFile, selectedPath }) {
    const sorted = useMemo(() => (files ? sortEntries(files) : []), [files]);
    if (!files) return null;

    return (
        <div className="h-full overflow-y-auto py-2">
            <div className="px-3 py-1.5 text-[11px] font-semibold text-zinc-600 uppercase tracking-wider">
                Explorer
            </div>
            {sorted.map((item) => (
                <FileItem
                    key={item.path || item.name}
                    item={item}
                    level={0}
                    onSelect={onSelectFile}
                    selectedPath={selectedPath}
                />
            ))}
        </div>
    );
}
