import React from 'react';
import { motion } from 'framer-motion';
import { ArrowRight, ShieldCheck, Zap, AlertTriangle, Code2, Server, Terminal, Lock } from 'lucide-react';
import { Link } from 'react-router-dom';

const fadeIn = {
    hidden: { opacity: 0, y: 20 },
    visible: { opacity: 1, y: 0, transition: { duration: 0.6, ease: "easeOut" } }
};

const staggerContainer = {
    hidden: { opacity: 0 },
    visible: {
        opacity: 1,
        transition: {
            staggerChildren: 0.1
        }
    }
};

export default function LandingPage() {
    return (
        <div className="flex flex-col items-center justify-center min-h-[calc(100vh-3.5rem)] px-4 py-12">

            {/* 1. Project Title & Value Prop */}
            <motion.div
                initial="hidden"
                animate="visible"
                variants={staggerContainer}
                className="text-center max-w-4xl mx-auto mb-16"
            >
                <motion.div variants={fadeIn} className="flex justify-center mb-6">
                    <div className="p-3 bg-blue-500/10 rounded-full border border-blue-500/20">
                        <Terminal className="w-8 h-8 text-blue-400" />
                    </div>
                </motion.div>

                <motion.h1
                    variants={fadeIn}
                    className="text-5xl md:text-6xl font-extrabold tracking-tight text-white mb-6"
                >
                    Codebase Impact Analysis Tool
                </motion.h1>

                <motion.p
                    variants={fadeIn}
                    className="text-xl text-slate-400 max-w-2xl mx-auto"
                >
                    Understand what breaks before you change code.
                </motion.p>
            </motion.div>

            {/* 2. & 3. Features "What it does" vs "What it does NOT do" */}
            <motion.div
                initial="hidden"
                whileInView="visible"
                viewport={{ once: true }}
                variants={staggerContainer}
                className="grid md:grid-cols-2 gap-8 max-w-5xl w-full mb-16"
            >
                {/* DO CARD */}
                <motion.div variants={fadeIn} className="bg-slate-900/50 border border-slate-800 rounded-xl p-8 relative overflow-hidden group hover:border-blue-500/30 transition-colors">
                    <div className="absolute top-0 left-0 w-1 h-full bg-blue-500/50" />
                    <div className="flex items-center gap-3 mb-6">
                        <Zap className="text-blue-400" />
                        <h2 className="text-2xl font-bold text-white">What This Tool Does</h2>
                    </div>
                    <ul className="space-y-4">
                        <li className="flex items-start gap-3">
                            <ShieldCheck className="w-5 h-5 text-blue-500 mt-1 shrink-0" />
                            <span className="text-slate-300">Analyzes entire repositories using static analysis</span>
                        </li>
                        <li className="flex items-start gap-3">
                            <ShieldCheck className="w-5 h-5 text-blue-500 mt-1 shrink-0" />
                            <span className="text-slate-300">Builds dependency relationships between files and functions</span>
                        </li>
                        <li className="flex items-start gap-3">
                            <ShieldCheck className="w-5 h-5 text-blue-500 mt-1 shrink-0" />
                            <span className="text-slate-300">Highlights potential impact and risk before changes are made</span>
                        </li>
                        <li className="flex items-start gap-3">
                            <ShieldCheck className="w-5 h-5 text-blue-500 mt-1 shrink-0" />
                            <span className="text-slate-300">Never executes or modifies code</span>
                        </li>
                    </ul>
                </motion.div>

                {/* DON'T CARD */}
                <motion.div variants={fadeIn} className="bg-slate-900/20 border border-slate-800 rounded-xl p-8 relative overflow-hidden group hover:border-orange-500/30 transition-colors">
                    <div className="absolute top-0 left-0 w-1 h-full bg-orange-500/50" />
                    <div className="flex items-center gap-3 mb-6">
                        <AlertTriangle className="text-orange-400" />
                        <h2 className="text-2xl font-bold text-white">What This Tool Does NOT Do</h2>
                    </div>
                    <ul className="space-y-4">
                        <li className="flex items-start gap-3">
                            <Lock className="w-5 h-5 text-orange-500 mt-1 shrink-0" />
                            <span className="text-slate-400">Does not generate code</span>
                        </li>
                        <li className="flex items-start gap-3">
                            <Lock className="w-5 h-5 text-orange-500 mt-1 shrink-0" />
                            <span className="text-slate-400">Does not run repositories</span>
                        </li>
                        <li className="flex items-start gap-3">
                            <Lock className="w-5 h-5 text-orange-500 mt-1 shrink-0" />
                            <span className="text-slate-400">Does not push changes</span>
                        </li>
                    </ul>
                </motion.div>
            </motion.div>

            {/* 4. CTA */}
            <motion.div
                initial={{ opacity: 0, scale: 0.9 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ delay: 0.8, duration: 0.5 }}
            >
                <Link
                    to="/input"
                    className="group relative inline-flex items-center gap-3 px-8 py-4 bg-blue-600 hover:bg-blue-500 text-white font-bold rounded-lg transition-all hover:scale-105 active:scale-95 shadow-lg shadow-blue-900/20"
                >
                    <span>Analyze a Repository</span>
                    <ArrowRight className="w-5 h-5 group-hover:translate-x-1 transition-transform" />
                </Link>
            </motion.div>

        </div>
    );
}
