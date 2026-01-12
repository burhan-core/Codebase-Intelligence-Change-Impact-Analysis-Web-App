import React from 'react';
import Navbar from './Navbar';
import { Outlet } from 'react-router-dom';

export default function Layout() {
    return (
        <div className="min-h-screen bg-slate-950 text-slate-200 flex flex-col font-sans">
            <Navbar />
            <main className="flex-1 flex flex-col relative overflow-hidden">
                <Outlet />
            </main>
        </div>
    );
}
