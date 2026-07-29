import React from 'react';
import Navbar from './Navbar';
import { Outlet } from 'react-router-dom';

export default function Layout() {
    return (
        <div className="h-screen bg-zinc-950 text-zinc-300 flex flex-col overflow-hidden">
            <Navbar />
            <main className="flex-1 flex flex-col relative overflow-hidden">
                <Outlet />
            </main>
        </div>
    );
}
