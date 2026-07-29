import React, { useEffect, useMemo, useState } from 'react';
import { ReactFlow, Background, Controls, MiniMap } from '@xyflow/react';
import dagre from '@dagrejs/dagre';
import '@xyflow/react/dist/style.css';
import { Loader2, AlertCircle } from 'lucide-react';
import { api } from '../../lib/api';

const NODE_HEIGHT = 34;

// Semantic palette: amber = depends on the focus (breaks if it changes),
// emerald = the focus depends on it, blue = the focus itself.
const C = {
    focusBorder: '#3b82f6',
    dependent: '#f59e0b',
    dependency: '#10b981',
    base: '#3f3f46',
    baseText: '#a1a1aa',
    edge: '#71717a',
};

function nodeWidth(label) {
    return Math.max(90, label.length * 7.5 + 28);
}

function layoutNodes(nodes, edges) {
    // Dagre lays out the connected dependency structure; files with no
    // import edges go into a compact grid below it instead of one huge column.
    const connectedIds = new Set(edges.flatMap((e) => [e.source, e.target]));
    const connected = nodes.filter((n) => connectedIds.has(n.id));
    const isolated = nodes.filter((n) => !connectedIds.has(n.id));

    const g = new dagre.graphlib.Graph();
    g.setGraph({ rankdir: 'LR', nodesep: 22, ranksep: 110 });
    g.setDefaultEdgeLabel(() => ({}));
    connected.forEach((n) => g.setNode(n.id, { width: n.width, height: NODE_HEIGHT }));
    edges.forEach((e) => g.setEdge(e.source, e.target));
    dagre.layout(g);

    let maxY = 0;
    const placed = connected.map((n) => {
        const pos = g.node(n.id);
        maxY = Math.max(maxY, pos.y);
        return { ...n, position: { x: pos.x - n.width / 2, y: pos.y - NODE_HEIGHT / 2 } };
    });

    const COL_W = 190, ROW_H = 52, COLS = 6;
    isolated.forEach((n, i) => {
        placed.push({
            ...n,
            position: { x: (i % COLS) * COL_W, y: maxY + 110 + Math.floor(i / COLS) * ROW_H },
        });
    });

    return placed;
}

function LegendDot({ color, children }) {
    return (
        <span className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full shrink-0" style={{ background: color }} />
            {children}
        </span>
    );
}

export default function GraphView({ projectId, selectedPath, impactTarget, onSelectFile, onOpenFile }) {
    const [graph, setGraph] = useState(null);
    const [impactFiles, setImpactFiles] = useState(null);
    const [hoverId, setHoverId] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    useEffect(() => {
        const fetchGraph = async () => {
            setLoading(true);
            try {
                const data = await api.getDependencies(projectId);
                if (!data) throw new Error('empty');
                setGraph(data);
            } catch (err) {
                console.error(err);
                setError('Could not load the dependency graph.');
            } finally {
                setLoading(false);
            }
        };
        fetchGraph();
    }, [projectId]);

    // When an impact target is active, tint its blast radius on the graph
    useEffect(() => {
        if (!impactTarget?.nodeId) {
            setImpactFiles(null);
            return;
        }
        api.getImpact(projectId, impactTarget.nodeId)
            .then((res) => setImpactFiles(new Set([impactTarget.filePath, ...res.summary.impacted_files])))
            .catch(() => setImpactFiles(null));
    }, [projectId, impactTarget]);

    // Static graph structure: file nodes, import edges, neighbor lookup
    const structure = useMemo(() => {
        if (!graph) return null;
        const fileNodes = graph.nodes.filter((n) => n.type === 'file');
        const fileIds = new Set(fileNodes.map((n) => n.id));
        // networkx node_link_data emits "links" in older versions, "edges" in newer
        const rawEdges = (graph.links || graph.edges || [])
            .filter((l) => l.type === 'imports' && fileIds.has(l.source) && fileIds.has(l.target));

        // id -> { dependents: who imports it, dependencies: what it imports }
        const neighbors = new Map();
        const entry = (id) => {
            if (!neighbors.has(id)) neighbors.set(id, { dependents: new Set(), dependencies: new Set() });
            return neighbors.get(id);
        };
        rawEdges.forEach((e) => {
            entry(e.source).dependencies.add(e.target);
            entry(e.target).dependents.add(e.source);
        });

        return { fileNodes, rawEdges, neighbors };
    }, [graph]);

    const selectedId = useMemo(() => {
        if (!structure || !selectedPath) return null;
        const normalized = selectedPath.replace(/\\/g, '/');
        return structure.fileNodes.find((n) => normalized.endsWith(n.id))?.id || null;
    }, [structure, selectedPath]);

    const focusId = hoverId || selectedId;
    const focus = focusId ? structure?.neighbors.get(focusId) : null;

    const { nodes, edges } = useMemo(() => {
        if (!structure) return { nodes: [], edges: [] };
        const { fileNodes, rawEdges } = structure;

        const nodes = fileNodes.map((n) => {
            const isFocus = n.id === focusId;
            const isDependent = focus?.dependents.has(n.id);
            const isDependency = focus?.dependencies.has(n.id);
            const isImpacted = impactFiles?.has(n.id);
            const dimmed = focusId && !isFocus && !isDependent && !isDependency;

            let border = C.base, color = C.baseText, background = '#18181b';
            if (isImpacted) { border = '#b45309'; color = '#fbbf24'; background = 'rgba(245,158,11,0.10)'; }
            if (isDependent) { border = C.dependent; color = '#fbbf24'; background = 'rgba(245,158,11,0.08)'; }
            if (isDependency) { border = C.dependency; color = '#34d399'; background = 'rgba(16,185,129,0.08)'; }
            if (isFocus) { border = C.focusBorder; color = '#fafafa'; background = '#1e293b'; }

            const w = nodeWidth(n.label);
            // Explicit dimensions + handles let React Flow draw edges and
            // fitView immediately, without waiting for DOM measurement.
            return {
                id: n.id,
                data: { label: n.label },
                position: { x: 0, y: 0 },
                width: w,
                height: NODE_HEIGHT,
                sourcePosition: 'right',
                targetPosition: 'left',
                handles: [
                    { type: 'source', position: 'right', x: w, y: NODE_HEIGHT / 2, width: 1, height: 1 },
                    { type: 'target', position: 'left', x: 0, y: NODE_HEIGHT / 2, width: 1, height: 1 },
                ],
                style: {
                    width: w,
                    background,
                    color,
                    border: `1.5px solid ${border}`,
                    borderRadius: 6,
                    fontSize: 12,
                    fontFamily: 'JetBrains Mono, monospace',
                    padding: '7px 4px',
                    opacity: dimmed ? 0.18 : 1,
                    transition: 'opacity 120ms ease',
                },
            };
        });

        const edges = rawEdges.map((e) => {
            // Edge e.source imports e.target
            const toFocus = e.target === focusId;   // a dependent's edge into the focus
            const fromFocus = e.source === focusId; // the focus importing a dependency
            const active = toFocus || fromFocus;
            const stroke = toFocus ? C.dependent : fromFocus ? C.dependency : C.edge;

            return {
                id: `${e.source}->${e.target}`,
                source: e.source,
                target: e.target,
                animated: active,
                style: {
                    stroke,
                    strokeWidth: active ? 2.25 : 1.25,
                    opacity: focusId && !active ? 0.06 : active ? 1 : 0.55,
                    transition: 'opacity 120ms ease',
                },
                markerEnd: { type: 'arrowclosed', color: stroke },
            };
        });

        return { nodes: layoutNodes(nodes, edges), edges };
    }, [structure, focusId, focus, impactFiles]);

    if (loading) {
        return (
            <div className="h-full flex items-center justify-center gap-2 text-zinc-500 text-sm">
                <Loader2 size={14} className="animate-spin" /> Building graph…
            </div>
        );
    }

    if (error) {
        return (
            <div className="h-full flex flex-col items-center justify-center gap-2 text-sm text-red-400">
                <AlertCircle size={18} />
                {error}
            </div>
        );
    }

    const focusLabel = focusId?.split('/').pop();

    return (
        <div className="h-full relative">
            {/* Top-left: context card */}
            <div className="absolute top-3 left-3 z-10 font-editor text-[11px] bg-zinc-950/85 border border-zinc-800 rounded-md px-3 py-2 backdrop-blur-sm max-w-[280px]">
                {focus ? (
                    <div className="space-y-1">
                        <div className="text-zinc-100 truncate">{focusLabel}</div>
                        <div className="text-amber-400">{focus.dependents.size} importer{focus.dependents.size === 1 ? '' : 's'} <span className="text-zinc-600">— break if it changes</span></div>
                        <div className="text-emerald-400">{focus.dependencies.size} import{focus.dependencies.size === 1 ? '' : 's'} <span className="text-zinc-600">— what it relies on</span></div>
                    </div>
                ) : (
                    <div className="text-zinc-500">
                        {nodes.length} files · {edges.length} imports
                        <div className="text-zinc-600 mt-0.5">hover a node to trace its connections</div>
                    </div>
                )}
            </div>

            {/* Bottom-left: legend */}
            <div className="absolute bottom-3 left-3 z-10 flex flex-col gap-1.5 font-editor text-[10px] text-zinc-500 bg-zinc-950/85 border border-zinc-800 rounded-md px-3 py-2 backdrop-blur-sm">
                <LegendDot color={C.dependent}>imports it — affected by change</LegendDot>
                <LegendDot color={C.dependency}>imported by it — its dependencies</LegendDot>
                <LegendDot color={C.focusBorder}>selected / hovered</LegendDot>
            </div>

            <ReactFlow
                nodes={nodes}
                edges={edges}
                fitView
                fitViewOptions={{ padding: 0.12, maxZoom: 1 }}
                minZoom={0.1}
                nodesConnectable={false}
                nodesDraggable
                edgesFocusable={false}
                proOptions={{ hideAttribution: true }}
                onNodeClick={(_, node) => onSelectFile(node.id)}
                onNodeDoubleClick={(_, node) => onOpenFile(node.id)}
                onNodeMouseEnter={(_, node) => setHoverId(node.id)}
                onNodeMouseLeave={() => setHoverId(null)}
                onPaneClick={() => setHoverId(null)}
                colorMode="dark"
            >
                <Background color="#27272a" gap={24} />
                <Controls showInteractive={false} position="bottom-right" />
                <MiniMap
                    pannable
                    zoomable
                    position="top-right"
                    nodeColor={(n) => n.style?.border?.includes(C.dependent) ? C.dependent : n.style?.border?.includes(C.focusBorder) ? C.focusBorder : '#3f3f46'}
                    maskColor="rgba(9, 9, 11, 0.75)"
                    style={{ background: '#18181b', border: '1px solid #27272a', borderRadius: 6 }}
                />
            </ReactFlow>
        </div>
    );
}
