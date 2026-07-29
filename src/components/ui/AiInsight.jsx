import React, { useEffect, useRef, useState } from 'react';
import { Sparkles, SendHorizonal, Loader2, AlertCircle, RotateCcw } from 'lucide-react';
import { api } from '../../lib/api';

export default function AiInsight({ projectId, target }) {
    const [messages, setMessages] = useState([]);
    const [input, setInput] = useState('');
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);
    const bottomRef = useRef(null);

    // New target = new conversation
    useEffect(() => {
        setMessages([]);
        setInput('');
        setError(null);
    }, [target?.nodeId]);

    useEffect(() => {
        bottomRef.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }, [messages, loading]);

    if (!target) return null;

    const send = async (question) => {
        setLoading(true);
        setError(null);
        const history = messages;
        if (question) setMessages((m) => [...m, { role: 'user', content: question }]);
        try {
            const res = await api.askAi(projectId, target.nodeId, question, history);
            setMessages((m) => [...m, { role: 'assistant', content: res.answer }]);
        } catch (err) {
            setError(err.message);
            if (question) setMessages(history); // roll back the optimistic user message
        } finally {
            setLoading(false);
        }
    };

    const handleSubmit = (e) => {
        e.preventDefault();
        const q = input.trim();
        if (!q || loading) return;
        setInput('');
        send(q);
    };

    return (
        <div className="border-t border-zinc-800 pt-4">
            <div className="flex items-center justify-between mb-3">
                <h4 className="flex items-center gap-1.5 text-[11px] font-semibold text-zinc-500 uppercase tracking-wider">
                    <Sparkles size={12} className="text-blue-500" /> AI review
                </h4>
                {messages.length > 0 && (
                    <button
                        onClick={() => { setMessages([]); setError(null); }}
                        title="Start over"
                        className="text-zinc-600 hover:text-zinc-300 transition-colors"
                    >
                        <RotateCcw size={12} />
                    </button>
                )}
            </div>

            {messages.length === 0 && !loading && (
                <button
                    onClick={() => send(null)}
                    className="w-full flex items-center justify-center gap-2 py-2.5 rounded-md border border-zinc-800 bg-zinc-900/60 hover:bg-zinc-900 hover:border-zinc-700 text-sm text-zinc-300 transition-colors"
                >
                    <Sparkles size={14} className="text-blue-500" />
                    Assess the risk of changing <span className="font-editor text-zinc-100">{target.label}</span>
                </button>
            )}

            <div className="space-y-3">
                {messages.map((m, i) => (
                    m.role === 'user' ? (
                        <div key={i} className="ml-6 rounded-md bg-blue-600/10 border border-blue-600/20 px-3 py-2 text-[13px] text-zinc-200 whitespace-pre-wrap">
                            {m.content}
                        </div>
                    ) : (
                        <div key={i} className="rounded-md bg-zinc-900/60 border border-zinc-800 px-3 py-2.5 text-[13px] leading-relaxed text-zinc-300 whitespace-pre-wrap">
                            {m.content}
                        </div>
                    )
                ))}

                {loading && (
                    <div className="flex items-center gap-2 text-zinc-500 text-xs px-1 py-2">
                        <Loader2 size={12} className="animate-spin" /> Reviewing blast radius…
                    </div>
                )}

                {error && (
                    <div className="flex items-start gap-2 rounded-md bg-red-500/5 border border-red-500/20 px-3 py-2 text-xs text-red-400">
                        <AlertCircle size={13} className="mt-0.5 shrink-0" />
                        <div>
                            {error}
                            {error.includes('Insufficient Balance') && (
                                <p className="text-zinc-500 mt-1">
                                    Your DeepSeek account has no credits — top up at platform.deepseek.com, then retry.
                                </p>
                            )}
                        </div>
                    </div>
                )}
            </div>

            {(messages.length > 0 || loading) && (
                <form onSubmit={handleSubmit} className="mt-3 relative">
                    <input
                        type="text"
                        value={input}
                        onChange={(e) => setInput(e.target.value)}
                        placeholder="Ask a follow-up — “what breaks if I rename it?”"
                        disabled={loading}
                        className="w-full bg-zinc-900 border border-zinc-800 rounded-md py-2 pl-3 pr-9 text-[13px] text-zinc-200 placeholder:text-zinc-600 focus:outline-none focus:border-blue-600 transition-colors disabled:opacity-50"
                    />
                    <button
                        type="submit"
                        disabled={!input.trim() || loading}
                        className="absolute right-2 top-1/2 -translate-y-1/2 text-zinc-500 hover:text-blue-500 disabled:opacity-40 transition-colors"
                    >
                        <SendHorizonal size={15} />
                    </button>
                </form>
            )}

            <div ref={bottomRef} />
        </div>
    );
}
