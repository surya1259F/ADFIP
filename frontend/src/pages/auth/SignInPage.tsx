import React, { useState, useEffect } from 'react';
import { Link, useNavigate, useLocation, Navigate } from 'react-router-dom';
import { LogIn, Mail, CheckCircle2, UserPlus } from 'lucide-react';
import { AuthCard } from '../../components/auth/AuthCard';
import { AuthInput } from '../../components/auth/AuthInput';
import { PasswordInput } from '../../components/auth/PasswordInput';
import { PrimaryButton } from '../../components/auth/PrimaryButton';
import { SocialButtons } from '../../components/auth/SocialButtons';
import { useAuthStore } from '../../stores/authStore';
import { authService } from '../../services/auth';
import { normalizeError } from '../../services/client';

export const SignInPage: React.FC = () => {
  const { status, login } = useAuthStore();
  const navigate = useNavigate();
  const location = useLocation();

  const successNotice = (location.state as { message?: string } | null)?.message;

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [errors, setErrors] = useState<{ email?: string; password?: string; general?: string }>({});
  const [notice, setNotice] = useState<string | null>(successNotice || null);
  const [socialNotice, setSocialNotice] = useState<string | null>(null);
  const [accountNotFound, setAccountNotFound] = useState(false);

  // If already authenticated, redirect to dashboard
  if (status === 'AUTHENTICATED') {
    return <Navigate to="/dashboard" replace />;
  }

  const validate = (): boolean => {
    const errs: { email?: string; password?: string } = {};

    const cleanEmail = email.trim();
    if (!cleanEmail) {
      errs.email = 'Email is required';
    } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(cleanEmail)) {
      errs.email = 'Please enter a valid email address';
    }

    if (!password) {
      errs.password = 'Password is required';
    }

    setErrors(errs);
    return Object.keys(errs).length === 0;
  };

  const handleSignIn = async (e: React.FormEvent) => {
    e.preventDefault();
    setNotice(null);
    setAccountNotFound(false);
    setErrors({});

    if (!validate()) return;

    setLoading(true);
    try {
      const res = await authService.login({
        email: email.trim(),
        password,
      });

      // Clear sensitive password from memory immediately
      setPassword('');

      const token = res.access_token;
      const user = res.user || (await authService.me(token));
      login(token, user);
      navigate('/dashboard', { replace: true });
    } catch (err: unknown) {
      // Clear password field on failed attempt
      setPassword('');
      const msg = normalizeError(err);
      setErrors((prev) => ({
        ...prev,
        general: msg || 'Invalid email or password. Please try again.',
      }));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    const params = new URLSearchParams(location.search);
    const errCode = params.get('error_code');
    const err = params.get('error');
    if (errCode === 'ACCOUNT_NOT_FOUND' || (err && decodeURIComponent(err).toLowerCase().includes('not registered'))) {
      setAccountNotFound(true);
    } else if (err) {
      setErrors((prev) => ({ ...prev, general: decodeURIComponent(err) }));
    }
  }, [location.search]);

  const handleGoogleSignIn = async () => {
    setSocialNotice(null);
    setAccountNotFound(false);
    setErrors({});
    setLoading(true);

    try {
      const res = await authService.getGoogleLoginUrl(undefined, 'SIGN_IN');
      if (!res.authorization_url) {
        setSocialNotice('Google OAuth is not configured for this deployment. Please set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in server settings.');
        setLoading(false);
        return;
      }

      // Calculate centered popup coordinates
      const width = 520;
      const height = 660;
      const left = window.screenX + (window.outerWidth - width) / 2;
      const top = window.screenY + (window.outerHeight - height) / 2;

      const popup = window.open(
        res.authorization_url,
        'adfip_google_oauth',
        `width=${width},height=${height},left=${left},top=${top},status=no,menubar=no,toolbar=no,location=yes`
      );

      if (!popup || popup.closed || typeof popup.closed === 'undefined') {
        // Browser blocked popup - fallback to full-page redirect
        window.location.href = res.authorization_url;
        return;
      }

      const allowedOrigins = [
        window.location.origin,
        'http://localhost:5173',
        'http://127.0.0.1:5173',
        'http://localhost:8000',
        'http://127.0.0.1:8000',
        'http://localhost:8001',
        'http://127.0.0.1:8001',
        'tauri://localhost',
        'http://tauri.localhost',
        'https://tauri.localhost',
      ];

      const handleMessage = async (event: MessageEvent) => {
        // 1. Strict Origin Validation
        if (!event.origin || !allowedOrigins.includes(event.origin)) {
          return;
        }

        // 2. Strict Source Validation
        if (popup && event.source !== popup) {
          return;
        }

        // 3. Payload Type Validation
        if (!event.data || typeof event.data !== 'object') {
          return;
        }

        if (event.data.type === 'ADFIP_OAUTH_SUCCESS') {
          // 4. Strict Code Payload Validation
          if (typeof event.data.code !== 'string' || event.data.code.length < 16 || event.data.code.length > 256) {
            return;
          }

          window.removeEventListener('message', handleMessage);
          const exchangeCode = event.data.code;
          try {
            const tokenRes = await authService.exchangeGoogleCode(exchangeCode);
            const token = tokenRes.access_token;
            const user = tokenRes.user || (await authService.me(token));
            login(token, user);
            navigate('/dashboard', { replace: true });
          } catch (err: unknown) {
            const msg = normalizeError(err);
            setErrors((prev) => ({ ...prev, general: msg || 'Failed to complete Google authentication.' }));
          } finally {
            setLoading(false);
          }
        } else if (event.data.type === 'ADFIP_OAUTH_ERROR') {
          // 5. Strict Error Payload Validation
          if (typeof event.data.error !== 'string' || event.data.error.length > 500) {
            return;
          }

          window.removeEventListener('message', handleMessage);
          const errCode = typeof event.data.error_code === 'string' ? event.data.error_code : undefined;
          if (errCode === 'ACCOUNT_NOT_FOUND' || (typeof event.data.error === 'string' && event.data.error.toLowerCase().includes('not registered'))) {
            setAccountNotFound(true);
            setErrors({});
          } else {
            setErrors((prev) => ({ ...prev, general: event.data.error || 'Google authentication was cancelled or failed.' }));
          }
          setLoading(false);
        }
      };

      window.addEventListener('message', handleMessage);


      // Heartbeat monitor if user closes popup window
      const checkClosedInterval = setInterval(() => {
        if (popup.closed) {
          clearInterval(checkClosedInterval);
          window.removeEventListener('message', handleMessage);
          setLoading(false);
        }
      }, 1000);

    } catch (err: unknown) {
      setLoading(false);
      const msg = normalizeError(err);
      if (msg.includes('not configured')) {
        setSocialNotice('Google OAuth is not configured for this deployment. Please set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in server configuration.');
      } else {
        setErrors((prev) => ({
          ...prev,
          general: msg || 'Unable to reach Google OAuth service. Please check server connectivity.',
        }));
      }
    }
  };


  const handleForgotPassword = (e: React.MouseEvent) => {
    e.preventDefault();
    if (!email.trim()) {
      setErrors((prev) => ({ ...prev, email: 'Enter your email above first to receive reset instructions' }));
      return;
    }
    setNotice(`If an investigator account exists for ${email.trim()}, password recovery instructions have been sent.`);
  };

  return (
    <div className="min-h-screen bg-white flex items-center justify-center p-4 sm:p-6 overflow-y-auto">
      <AuthCard>
        {/* 1. ADFIP Branding */}
        <div className="text-center">
          <p className="text-[12px] font-bold tracking-[0.25em] text-slate-800 uppercase">
            ADFIP
          </p>
          <p className="text-[12px] text-gray-500 mt-0.5">
            Autonomous Digital Forensics Investigation Platform
          </p>
        </div>

        {/* 2. Icon Tile */}
        <div className="w-16 h-16 rounded-[18px] bg-white border border-[#e5e7eb] shadow-[0_4px_12px_rgba(0,0,0,0.05)] flex items-center justify-center mx-auto my-5">
          <LogIn className="w-6 h-6 text-gray-900 ml-0.5" />
        </div>

        {/* 3. Heading */}
        <h1 className="text-[26px] font-bold text-gray-900 leading-tight">
          Sign in to ADFIP
        </h1>

        {/* 4. Subtitle */}
        <p className="text-[15px] text-gray-500 mt-2 max-w-[340px] mx-auto leading-snug">
          Autonomous multi-agent AI for faster, evidence-grade digital forensics investigations.
        </p>

        {/* Account Not Found Banner */}
        {accountNotFound && (
          <div className="mt-4 p-4 bg-amber-50/90 border border-amber-300 rounded-[14px] text-left">
            <div className="flex items-start gap-2.5">
              <UserPlus className="w-5 h-5 text-amber-600 shrink-0 mt-0.5" />
              <div>
                <h3 className="text-sm font-semibold text-amber-900">No ADFIP account found</h3>
                <p className="text-xs text-amber-800 mt-1 leading-relaxed">
                  This Google account isn't registered with ADFIP. Please use Sign Up to create your account.
                </p>
                <div className="mt-3">
                  <Link
                    to="/signup"
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-amber-600 hover:bg-amber-700 text-white rounded-lg text-xs font-semibold transition-colors cursor-pointer"
                  >
                    Go to Sign Up
                  </Link>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* General Error Banner */}
        {errors.general && (
          <div className="mt-4 p-3 bg-red-50/80 border border-red-200 rounded-[14px] text-xs text-red-700 text-left">
            {errors.general}
          </div>
        )}

        {/* Notice Banner */}
        {notice && (
          <div
            className={`mt-4 p-3 rounded-[14px] text-xs text-left flex items-start gap-2 ${
              notice === successNotice
                ? 'bg-emerald-50 border border-emerald-200 text-emerald-800'
                : 'bg-blue-50/80 border border-blue-200 text-blue-700'
            }`}
          >
            {notice === successNotice && (
              <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
            )}
            <span>{notice}</span>
          </div>
        )}

        {/* Sign In Form */}
        <form onSubmit={handleSignIn} className="mt-6 space-y-3" noValidate autoComplete="on">
          {/* 5. Email Input */}
          <AuthInput
            type="email"
            placeholder="Email"
            value={email}
            onChange={(e) => {
              setEmail(e.target.value);
              if (errors.email) setErrors((prev) => ({ ...prev, email: undefined }));
            }}
            icon={<Mail className="w-4 h-4" />}
            error={errors.email}
            autoComplete="username"
            disabled={loading}
          />

          {/* 6. Password Input */}
          <PasswordInput
            placeholder="Password"
            value={password}
            onChange={(e) => {
              setPassword(e.target.value);
              if (errors.password) setErrors((prev) => ({ ...prev, password: undefined }));
            }}
            error={errors.password}
            autoComplete="current-password"
            disabled={loading}
          />

          {/* 7. Forgot password link */}
          <div className="flex justify-end pt-0.5">
            <button
              type="button"
              onClick={handleForgotPassword}
              className="text-[13px] text-gray-900 font-medium hover:underline focus:outline-none cursor-pointer"
            >
              Forgot password?
            </button>
          </div>

          {/* 8. Primary Button: MUST be 'Sign In' */}
          <div className="pt-2">
            <PrimaryButton type="submit" loading={loading} disabled={loading}>
              Sign In
            </PrimaryButton>
          </div>
        </form>

        {/* 9. Divider */}
        <div className="relative flex items-center justify-center my-6">
          <div className="absolute inset-0 flex items-center">
            <div className="w-full border-t border-dashed border-gray-300" />
          </div>
          <span className="relative px-3 bg-[#fdfefe] text-xs text-gray-400 font-medium">
            Or continue with
          </span>
        </div>

        {/* 10. Social Button: Google */}
        <SocialButtons
          onGoogle={handleGoogleSignIn}
          disabled={loading}
        />
        {socialNotice && (
          <p className="mt-2.5 text-xs text-amber-800 bg-amber-50/90 border border-amber-200 rounded-[12px] p-2.5 text-center leading-relaxed">
            {socialNotice}
          </p>
        )}

        {/* 11. Footer Link to Sign up */}
        <p className="text-[14px] text-gray-600 mt-6">
          Don't have an account?{' '}
          <Link
            to="/signup"
            className="font-bold text-gray-900 hover:underline cursor-pointer"
          >
            Sign up
          </Link>
        </p>

        {/* 12. Legal Links */}
        <div className="mt-4 pt-4 border-t border-stone-100 flex items-center justify-center gap-4 text-xs text-gray-400">
          <Link to="/terms" className="hover:text-gray-600 underline">
            Terms of Service
          </Link>
          <span>•</span>
          <Link to="/privacy" className="hover:text-gray-600 underline">
            Privacy Policy
          </Link>
        </div>
      </AuthCard>
    </div>
  );
};
