import React from 'react';
import { Outlet } from 'react-router-dom';
import { Sidebar } from './Sidebar';
import { TopBar } from './TopBar';

export const AppLayout: React.FC = () => (
  <div className="flex h-screen w-screen bg-stone-50 overflow-hidden">
    <Sidebar />
    <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
      <TopBar />
      <main className="flex-1 overflow-y-auto p-6 bg-stone-50">
        <Outlet />
      </main>
    </div>
  </div>
);
