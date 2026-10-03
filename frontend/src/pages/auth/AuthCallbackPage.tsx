import React, { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { Shield, AlertCircle, Loader2 } from 'lucide-react';
import { authService } from '../../services/auth';
import { useAuthStore } from '../../stores/authStore';
import { normalizeError } from '../../services/client';
import { Button } from '../../components/ui/Button';

export const AuthCallbackPage: React.FC = () => {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const login = useAuthStore((s) => s.login);

  const [status, setStatus] = useState<'exchanging' | 'success' | 'error'>('exchanging');
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const executedRef = React.useRef(false);

  useEffect(() => {
    if (executedRef.current) return;

    const code = searchParams.get('code');
    const error = searchParams.get('error') || searchParams.get('error_description');

    if (error) {
      executedRef.current = true;
      setStatus('error');
      setErrorMessage(error);
      return;
    }

    if (!code || typeof code !== 'string' || code.length < 16 || code.length > 256) {
      executedRef.current = true;
      setStatus('error');
      setErrorMessage('Invalid or missing authorization exchange code.');
      return;
    }

    executedRef.current = true;
    let isMounted = true;

    const exchangeCode = async () => {
      try {
        const res = await authService.exchangeGoogleCode(code);
        if (!isMounted) return;

        setStatus('success');
        const token = res.access_token;
        const user = res.user || (await authService.me(token));

        login(token, user);

        // Notify parent if inside a popup
        if (window.opener && !window.opener.closed) {
          try {
            window.opener.postMessage({ type: 'ADFIP_OAUTH_SUCCESS', code }, window.location.origin);
            setTimeout(() => window.close(), 300);
            return;
          } catch {
            // popup origin check fallback
          }
        }

        // Navigate to dashboard with replace to clear sensitive parameters from browser history
        navigate('/dashboard', { replace: true });
      } catch (err: unknown) {
        if (!isMounted) return;
        setStatus('error');
        const msg = normalizeError(err);
        setErrorMessage(msg || 'Failed to complete Google authentication.');
      }
    };

    exchangeCode();

    return () => {
      isMounted = false;
    };
  }, [searchParams, navigate, login]);


  return (
    <div className="min-h-screen bg-stone-50 flex items-center justify-center p-4">
      <div className="w-full max-w-sm bg-white border border-stone-200 rounded-xl shadow-sm p-6 text-center">
        <div className="inline-flex p-3 bg-slate-900 rounded-xl mb-4">
          <Shield className="w-6 h-6 text-white" />
        </div>

        {status === 'exchanging' && (
          <div className="space-y-3">
            <Loader2 className="w-8 h-8 text-slate-600 animate-spin mx-auto" />
            <h2 className="text-sm font-semibold text-slate-800">Verifying Investigator Credentials</h2>
            <p className="text-xs text-slate-500">
              Securing session tokens and establishing authenticated forensic workspace...
            </p>
          </div>
        )}

        {status === 'success' && (
          <div className="space-y-2">
            <h2 className="text-sm font-semibold text-emerald-700">Authenticated Successfully</h2>
            <p className="text-xs text-slate-500">Redirecting to your investigation dashboard...</p>
          </div>
        )}

        {status === 'error' && (
          <div className="space-y-4">
            <div className="flex items-center justify-center w-10 h-10 rounded-full bg-red-50 text-red-600 mx-auto">
              <AlertCircle className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-sm font-semibold text-slate-800">Authentication Failed</h2>
              <p className="text-xs text-red-600 mt-1 max-w-xs mx-auto leading-relaxed">
                {errorMessage}
              </p>
            </div>
            <Button
              variant="primary"
              size="md"
              className="w-full mt-2"
              onClick={() => navigate('/signin', { replace: true })}
            >
              Return to Sign In
            </Button>
          </div>
        )}
      </div>
    </div>
  );
};
