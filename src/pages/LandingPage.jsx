import React from 'react';
import { motion as Motion } from 'framer-motion';
import { ArrowRight, GitBranch, Check, Minus } from 'lucide-react';
import { Link } from 'react-router-dom';

const fadeUp = {
    hidden: { opacity: 0, y: 16 },
    visible: { opacity: 1, y: 0, transition: { duration: 0.5, ease: 'easeOut' } },
};

const stagger = {
    hidden: {},
    visible: { transition: { staggerChildren: 0.08 } },
};

const steps = [
    { n: '01', title: 'Parse', text: 'Every Python file is read into an AST — imports, classes, functions, and each call they make.' },
    { n: '02', title: 'Model', text: 'A directed graph connects files and functions through contains, imports, and calls edges.' },
    { n: '03', title: 'Traverse', text: 'Selecting a function walks the graph upstream, collecting every transitive caller.' },
    { n: '04', title: 'Report', text: 'The blast radius is listed by file, with depth and confidence for every affected symbol.' },
];

const does = [
    'Maps dependencies across an entire repository',
    'Traces the transitive blast radius of any function',
    'Explains every result deterministically — no guesswork',
];

const doesNot = [
    'Execute or modify your code',
    'Generate code or push changes',
    'Require any AI to be correct',
];

/* Static mock of an impact report — gives visitors the product in one glance. */
function ImpactPreview() {
    const rows = [
        { name: 'create_order()', file: 'api/orders.py', depth: 1, tone: 'text-amber-400' },
        { name: 'checkout_view()', file: 'views/checkout.py', depth: 2, tone: 'text-amber-400' },
        { name: 'retry_payment()', file: 'jobs/billing.py', depth: 2, tone: 'text-amber-400' },
        { name: 'test_checkout()', file: 'tests/test_checkout.py', depth: 3, tone: 'text-zinc-500' },
    ];
    return (
        <div className="w-full max-w-md rounded-lg border border-zinc-800 bg-zinc-900/60 font-editor text-[13px] shadow-2xl shadow-black/40">
            <div className="flex items-center gap-2 px-4 py-2.5 border-b border-zinc-800">
                <span className="w-2.5 h-2.5 rounded-full bg-zinc-700" />
                <span className="w-2.5 h-2.5 rounded-full bg-zinc-700" />
                <span className="w-2.5 h-2.5 rounded-full bg-zinc-700" />
                <span className="ml-2 text-zinc-500 text-xs">impact report</span>
            </div>
            <div className="p-4 space-y-1.5">
                <div className="text-zinc-400">
                    <span className="text-blue-400">❯</span> impact <span className="text-zinc-100">charge_card()</span>
                    <span className="text-zinc-600"> · payments/core.py</span>
                </div>
                <div className="text-zinc-600 pb-1">4 symbols affected across 4 files</div>
                {rows.map((r) => (
                    <div key={r.name} className="flex items-center gap-2">
                        <span className="text-zinc-700">{'│ '.repeat(r.depth - 1)}└─</span>
                        <span className={r.tone}>{r.name}</span>
                        <span className="text-zinc-600 truncate">{r.file}</span>
                        <span className="ml-auto text-zinc-700 text-xs shrink-0">d{r.depth}</span>
                    </div>
                ))}
            </div>
        </div>
    );
}

export default function LandingPage() {
    return (
        <div className="flex-1 overflow-y-auto relative">
            {/* Ambient hero backdrop */}
            <div aria-hidden className="absolute inset-x-0 top-0 h-[560px] pointer-events-none overflow-hidden">
                <div className="absolute -top-40 left-1/2 translate-x-16 w-[560px] h-[560px] bg-blue-600/10 rounded-full blur-[130px]" />
                <div className="absolute inset-0 [background-image:radial-gradient(#27272a_1px,transparent_1px)] [background-size:26px_26px] [mask-image:linear-gradient(to_bottom,rgba(0,0,0,0.5),transparent_75%)]" />
            </div>

            {/* Hero */}
            <Motion.section
                initial="hidden"
                animate="visible"
                variants={stagger}
                className="relative max-w-6xl mx-auto px-6 pt-24 pb-20 grid lg:grid-cols-2 gap-16 items-center"
            >
                <div>
                    <Motion.div variants={fadeUp} className="inline-flex items-center gap-2 rounded-full border border-zinc-800 bg-zinc-900/50 px-3 py-1 mb-8">
                        <GitBranch size={12} className="text-blue-500" />
                        <span className="font-editor text-[11px] tracking-wide text-zinc-400">STATIC ANALYSIS · NOTHING IS EXECUTED</span>
                    </Motion.div>

                    <Motion.h1
                        variants={fadeUp}
                        className="text-4xl md:text-[3.4rem] leading-[1.05] font-bold tracking-tight text-zinc-50 mb-6"
                    >
                        See what breaks<br />
                        <span className="text-zinc-500">before you change code.</span>
                    </Motion.h1>

                    <Motion.p variants={fadeUp} className="text-lg text-zinc-400 max-w-lg mb-10 leading-relaxed">
                        Impact Lens parses your repository, builds its dependency graph, and shows the
                        exact blast radius of changing any function — every caller, at every depth.
                    </Motion.p>

                    <Motion.div variants={fadeUp} className="flex items-center gap-4">
                        <Link
                            to="/input"
                            className="group inline-flex items-center gap-2 px-5 py-2.5 bg-blue-600 hover:bg-blue-500 text-white text-sm font-semibold rounded-md transition-colors"
                        >
                            Analyze a repository
                            <ArrowRight size={16} className="group-hover:translate-x-0.5 transition-transform" />
                        </Link>
                        <a
                            href="#how-it-works"
                            className="px-5 py-2.5 text-sm font-medium text-zinc-400 hover:text-zinc-100 border border-zinc-800 hover:border-zinc-700 rounded-md transition-colors"
                        >
                            How it works
                        </a>
                    </Motion.div>
                </div>

                <Motion.div variants={fadeUp} className="hidden lg:flex justify-end">
                    <ImpactPreview />
                </Motion.div>
            </Motion.section>

            {/* How it works */}
            <section id="how-it-works" className="border-t border-zinc-900">
                <div className="max-w-6xl mx-auto px-6 py-20">
                    <h2 className="text-sm font-editor text-blue-500 mb-2">HOW IT WORKS</h2>
                    <p className="text-2xl font-semibold text-zinc-100 mb-12 tracking-tight">
                        Deterministic, four steps, no magic.
                    </p>
                    <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-px bg-zinc-900 border border-zinc-900 rounded-lg overflow-hidden">
                        {steps.map((s) => (
                            <div key={s.n} className="bg-zinc-950 p-6 hover:bg-zinc-900/50 transition-colors">
                                <div className="font-editor text-xs text-zinc-600 mb-4">{s.n}</div>
                                <div className="font-semibold text-zinc-100 mb-2">{s.title}</div>
                                <p className="text-sm text-zinc-500 leading-relaxed">{s.text}</p>
                            </div>
                        ))}
                    </div>
                </div>
            </section>

            {/* Boundaries */}
            <section className="border-t border-zinc-900">
                <div className="max-w-6xl mx-auto px-6 py-20 grid md:grid-cols-2 gap-12">
                    <div>
                        <h3 className="text-sm font-semibold text-zinc-100 mb-5">What it does</h3>
                        <ul className="space-y-3">
                            {does.map((d) => (
                                <li key={d} className="flex items-start gap-3 text-sm text-zinc-400">
                                    <Check size={16} className="text-blue-500 mt-0.5 shrink-0" />
                                    {d}
                                </li>
                            ))}
                        </ul>
                    </div>
                    <div>
                        <h3 className="text-sm font-semibold text-zinc-100 mb-5">What it will never do</h3>
                        <ul className="space-y-3">
                            {doesNot.map((d) => (
                                <li key={d} className="flex items-start gap-3 text-sm text-zinc-500">
                                    <Minus size={16} className="text-zinc-700 mt-0.5 shrink-0" />
                                    {d}
                                </li>
                            ))}
                        </ul>
                    </div>
                </div>
            </section>

            {/* Bottom CTA */}
            <section className="border-t border-zinc-900">
                <div className="max-w-6xl mx-auto px-6 py-16 flex flex-col items-center text-center">
                    <p className="text-xl font-semibold text-zinc-100 mb-6 tracking-tight">
                        Point it at a repository and see the graph.
                    </p>
                    <Link
                        to="/input"
                        className="group inline-flex items-center gap-2 px-5 py-2.5 bg-zinc-100 hover:bg-white text-zinc-950 text-sm font-semibold rounded-md transition-colors"
                    >
                        Get started
                        <ArrowRight size={16} className="group-hover:translate-x-0.5 transition-transform" />
                    </Link>
                </div>
            </section>
        </div>
    );
}
