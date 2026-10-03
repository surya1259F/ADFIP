import React from 'react';
import { Link } from 'react-router-dom';
import { AlertCircle } from 'lucide-react';
import { Button } from '../components/ui/Button';

export const NotFoundPage: React.FC = () => (
  <div className="flex flex-col items-center justify-center min-h-[60vh] text-center">
    <AlertCircle className="w-10 h-10 text-stone-300 mb-4" />
    <h1 className="text-base font-semibold text-slate-800 mb-1">Workspace not found</h1>
    <p className="text-sm text-slate-500 mb-6">
      The requested resource does not exist or is no longer available.
    </p>
    <Link to="/cases">
      <Button variant="secondary">Return to Cases</Button>
    </Link>
  </div>
);
