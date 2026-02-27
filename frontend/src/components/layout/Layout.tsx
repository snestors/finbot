import { useState } from 'react';
import { Outlet } from 'react-router-dom';
import Sidebar from './Sidebar';
import { useWebSocket } from '../../hooks/useWebSocket';

export default function Layout() {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  useWebSocket();

  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar open={sidebarOpen} onClose={() => setSidebarOpen(false)} />
      <div className="flex-1 flex flex-col overflow-hidden">
        <header className="h-12 flex items-center px-4 border-b border-surface-light bg-surface lg:hidden">
          <button onClick={() => setSidebarOpen(true)} className="text-xl mr-3">☰</button>
          <span className="text-primary font-bold">FinBot</span>
        </header>
        <main className="flex-1 overflow-y-auto p-4 md:p-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
