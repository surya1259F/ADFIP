import React, { useState } from 'react';
import { useNavigate, Navigate } from 'react-router-dom';
import { Shield, AlertCircle } from 'lucide-react';
import { useAuthStore } from '../../stores/authStore';
import { authService } from '../../services/auth';
import { normalizeError } from '../../services/client';
import { Button } from '../../components/ui/Button';
import { Input } from '../../components/ui/Input';

export const LoginPage: React.FC = () => {
  const { status, login } = useAuthStore();
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (status === 'AUTHENTICATED') return <Navigate to="/dashboard" replace />;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email || !password) return;
    setLoading(true);
    setError(null);
    try {
      const res = await authService.login({ email, password });
      const token = res.access_token;
      const user = res.user || (await authService.me(token));
      login(token, user);
      navigate('/dashboard', { replace: true });
    } catch (err) {
      setError(normalizeError(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-stone-50 flex items-center justify-center p-4">
      <div className="w-full max-w-sm">
        {/* Brand */}
        <div className="text-center mb-8">
          <div className="inline-flex p-3 bg-slate-800 rounded-xl mb-4">
            <Shield className="w-6 h-6 text-white" />
          </div>
          <h1 className="text-xl font-bold text-slate-900">ADFIP</h1>
          <p className="text-sm text-slate-500 mt-1">Autonomous Digital Forensic Investigation Platform</p>
        </div>

        {/* Form */}
        <div className="bg-white border border-stone-200 rounded-lg shadow-sm p-6">
          <h2 className="text-sm font-semibold text-slate-800 mb-4">Investigator Sign In</h2>

          {error && (
            <div className="flex items-start gap-2 p-3 bg-red-50 border border-red-200 rounded-md mb-4">
              <AlertCircle className="w-4 h-4 text-red-500 shrink-0 mt-0.5" />
              <p className="text-xs text-red-700">{error}</p>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-3">
            <Input
              label="Email address"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="investigator@org.gov"
              autoComplete="email"
              required
            />
            <Input
              label="Password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              autoComplete="current-password"
              required
            />
            <Button
              type="submit"
              variant="primary"
              size="lg"
              loading={loading}
              className="w-full mt-2"
            >
              Sign In
            </Button>
          </form>
        </div>

        <p className="text-center text-[11px] text-slate-400 mt-4">
          Authorized investigators only. All sessions are audited.
        </p>
      </div>
    </div>
  );
};
