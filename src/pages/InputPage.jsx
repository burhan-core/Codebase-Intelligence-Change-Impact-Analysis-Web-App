import React from 'react';
import { motion } from 'framer-motion';
import RepoInputForm from '../components/ui/RepoInputForm';
import InfoPanel from '../components/ui/InfoPanel';

export default function InputPage() {
    return (
        <div className="flex-1 grid md:grid-cols-2 h-full">
            {/* Left Panel - Input */}
            <motion.div
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ duration: 0.5 }}
                className="flex items-center justify-center p-8 border-r border-slate-800 bg-slate-950"
            >
                <RepoInputForm />
            </motion.div>

            {/* Right Panel - Info */}
            <motion.div
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ duration: 0.5, delay: 0.2 }}
                className="hidden md:flex flex-col bg-slate-900/20"
            >
                <div className="flex-1 flex items-center justify-center p-8">
                    <InfoPanel />
                </div>

                {/* Decorative background element */}
                <div className="h-2 bg-gradient-to-r from-blue-600 via-purple-600 to-blue-600 opacity-20" />
            </motion.div>
        </div>
    );
}
