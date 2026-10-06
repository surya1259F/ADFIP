import React, { useState } from 'react';
import { Link, useNavigate, Navigate } from 'react-router-dom';
import { UserPlus, User, Mail, Building2, Shield } from 'lucide-react';
import { AuthCard } from '../../components/auth/AuthCard';
import { AuthInput } from '../../components/auth/AuthInput';
import { PasswordInput } from '../../components/auth/PasswordInput';
import { PrimaryButton } from '../../components/auth/PrimaryButton';
import { SocialButtons } from '../../components/auth/SocialButtons';
import { useAuthStore } from '../../stores/authStore';
import { authService } from '../../services/auth';
import { normalizeError } from '../../services/client';
import { cn } from '../../lib/utils';

const ROLES = [
  'Forensic Investigator',
  'Incident Responder',
  'SOC Analyst',
  'Legal / Compliance',
  'Security Researcher',
  'Administrator',
];

interface StrengthResult {
  score: number;
  label: 'Weak' | 'Medium' | 'Strong';
  color: string;
}

const getPasswordStrength = (pass: string): StrengthResult => {
  if (!pass) return { score: 0, label: 'Weak', color: 'bg-gray-200' };
  let points = 0;
  if (pass.length >= 8) points += 1;
  if (/[0-9]/.test(pass)) points += 1;
  if (/[^A-Za-z0-9]/.test(pass)) points += 1;
  if (/[A-Z]/.test(pass) && /[a-z]/.test(pass)) points += 1;

  if (points <= 1) return { score: 1, label: 'Weak', color: 'bg-red-500' };
  if (points <= 2) return { score: 2, label: 'Medium', color: 'bg-amber-500' };
  return { score: 3, label: 'Strong', color: 'bg-emerald-500' };
};

export const SignUpPage: React.FC = () => {
  const { status, login } = useAuthStore();
  const navigate = useNavigate();

  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [organization, setOrganization] = useState('');
  const [role, setRole] = useState(ROLES[0]);
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [agreeTerms, setAgreeTerms] = useState(false);
  const [authorizedUse, setAuthorizedUse] = useState(false);

  const [loading, setLoading] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [generalError, setGeneralError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [socialNotice, setSocialNotice] = useState<string | null>(null);

  if (status === 'AUTHENTICATED') {
    return <Navigate to="/dashboard" replace />;
  }

  const strength = getPasswordStrength(password);

  const validate = (): boolean => {
    const errs: Record<string, string> = {};

    if (!fullName.trim()) {
      errs.fullName = 'Full name is required';
    }

    const cleanEmail = email.trim();
    if (!cleanEmail) {
      errs.email = 'Work email is required';
    } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(cleanEmail)) {
      errs.email = 'Please enter a valid work email address';
    }


    if (!password) {
      errs.password = 'Password is required';
    } else if (password.length < 8) {
      errs.password = 'Password must be at least 8 characters long';
    } else if (!/[0-9]/.test(password) || !/[^A-Za-z0-9]/.test(password)) {
      errs.password = 'Include at least one number and one symbol';
    }

    if (!confirmPassword) {
      errs.confirmPassword = 'Confirm your password';
    } else if (password !== confirmPassword) {
      errs.confirmPassword = 'Passwords do not match';
    }

    if (!agreeTerms) {
      errs.terms = 'You must agree to the Terms of Service and Privacy Policy';
    }

    setErrors(errs);
    return Object.keys(errs).length === 0;
  };

  const handleSignUp = async (e: React.FormEvent) => {
    e.preventDefault();
    setGeneralError(null);
    setNotice(null);

    if (!validate()) return;

    setLoading(true);
    try {
      await authService.signup({
        email: email.trim(),
        name: fullName.trim(),
        password,
        organization: organization.trim(),
        role,
      });

      // Clear passwords from memory immediately
      setPassword('');
      setConfirmPassword('');

      navigate('/signin', {
        state: {
          signupSuccess: true,
          message: 'Account created successfully. Please sign in with your credentials.',
        },
      });
    } catch (err: unknown) {
      setPassword('');
      setConfirmPassword('');
      const msg = normalizeError(err);
      setGeneralError(msg || 'Failed to create account. Please check your information or try again.');
    } finally {
      setLoading(false);
    }
  };

  const handleGoogleSignUp = async () => {
    setSocialNotice(null);
    setGeneralError(null);
    setLoading(true);

    try {
      const res = await authService.getGoogleLoginUrl();
      if (!res.authorization_url) {
        setSocialNotice('Google OAuth is not configured for this deployment. Please set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in server settings.');
        setLoading(false);
        return;
      }

      const width = 520;
      const height = 660;
      const left = window.screenX + (window.outerWidth - width) / 2;
      const top = window.screenY + (window.outerHeight - height) / 2;

      const popup = window.open(
        res.authorization_url,
        'adfip_google_oauth_signup',
        `width=${width},height=${height},left=${left},top=${top},status=no,menubar=no,toolbar=no,location=yes`
      );

      if (!popup || popup.closed || typeof popup.closed === 'undefined') {
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
            setGeneralError(msg || 'Failed to complete Google registration.');
          } finally {
            setLoading(false);
          }
        } else if (event.data?.type === 'ADFIP_OAUTH_ERROR') {
          // 5. Strict Error Payload Validation
          if (typeof event.data.error !== 'string' || event.data.error.length > 500) {
            return;
          }

          window.removeEventListener('message', handleMessage);
          setGeneralError(event.data.error || 'Google registration was cancelled or failed.');
          setLoading(false);
        }
      };

      window.addEventListener('message', handleMessage);


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
        setSocialNotice('Google OAuth is not configured for this deployment. Please configure GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in environment settings.');
      } else {
        setGeneralError(msg || 'Unable to reach Google OAuth service. Please verify server connection.');
      }
    }
  };


  return (
    <div className="min-h-screen bg-white flex items-center justify-center p-4 sm:p-6 py-10 overflow-y-auto">
      <AuthCard className="max-w-[460px]">
        {/* 1. ADFIP Branding */}
        <div className="text-center">
          <p className="text-[12px] font-bold tracking-[0.25em] text-slate-800 uppercase">
            ADFIP
          </p>
          <p className="text-[12px] text-gray-500 mt-0.5">
            Autonomous Digital Forensics Investigation Platform
          </p>
        </div>

        {/* Icon Tile: UserPlus */}
        <div className="w-16 h-16 rounded-[18px] bg-white border border-[#e5e7eb] shadow-[0_4px_12px_rgba(0,0,0,0.05)] flex items-center justify-center mx-auto my-5">
          <UserPlus className="w-6 h-6 text-gray-900" />
        </div>

        {/* 2. Heading & Subtitle */}
        <h1 className="text-[26px] font-bold text-gray-900 leading-tight">
          Create your account
        </h1>
        <p className="text-[15px] text-gray-500 mt-2 max-w-[360px] mx-auto leading-snug">
          Join ADFIP and let autonomous AI agents accelerate your forensic investigations.
        </p>

        {/* Error Alert */}
        {generalError && (
          <div className="mt-4 p-3 bg-red-50/80 border border-red-200 rounded-[14px] text-xs text-red-700 text-left">
            {generalError}
          </div>
        )}

        {/* Notice Alert */}
        {notice && (
          <div className="mt-4 p-3 bg-blue-50/80 border border-blue-200 rounded-[14px] text-xs text-blue-700 text-left">
            {notice}
          </div>
        )}

        {/* 3. Form Fields */}
        <form onSubmit={handleSignUp} className="mt-6 space-y-3" noValidate autoComplete="on">
          {/* Full Name */}
          <AuthInput
            placeholder="Full Name"
            value={fullName}
            onChange={(e) => {
              setFullName(e.target.value);
              if (errors.fullName) setErrors((prev) => ({ ...prev, fullName: '' }));
            }}
            icon={<User className="w-4 h-4" />}
            error={errors.fullName}
            autoComplete="name"
            disabled={loading}
          />

          {/* Work Email */}
          <AuthInput
            type="email"
            placeholder="Work Email"
            value={email}
            onChange={(e) => {
              setEmail(e.target.value);
              if (errors.email) setErrors((prev) => ({ ...prev, email: '' }));
            }}
            icon={<Mail className="w-4 h-4" />}
            error={errors.email}
            autoComplete="email"
            disabled={loading}
          />

          {/* Organization / Agency */}
          <AuthInput
            placeholder="Organization / Agency (Optional)"
            value={organization}
            onChange={(e) => {
              setOrganization(e.target.value);
              if (errors.organization) setErrors((prev) => ({ ...prev, organization: '' }));
            }}
            icon={<Building2 className="w-4 h-4" />}
            error={errors.organization}
            autoComplete="organization"
            disabled={loading}
          />

          {/* Role Dropdown */}
          <div className="w-full text-left">
            <div className="relative flex items-center">
              <span className="absolute left-3.5 flex items-center justify-center text-gray-400 pointer-events-none">
                <Shield className="w-4 h-4" />
              </span>
              <select
                value={role}
                onChange={(e) => setRole(e.target.value)}
                disabled={loading}
                className="w-full h-[42px] rounded-[14px] bg-[#f8f9fb] border border-[#e5e7eb] pl-10 pr-8 text-sm text-gray-900 transition-colors focus:outline-none focus:border-slate-500 focus:bg-white focus:ring-2 focus:ring-slate-200/60 cursor-pointer appearance-none"
              >
                {ROLES.map((r) => (
                  <option key={r} value={r}>
                    {r}
                  </option>
                ))}
              </select>
              <div className="absolute right-3.5 pointer-events-none text-gray-400 text-xs">
                ▼
              </div>
            </div>
          </div>

          {/* Password with live strength meter */}
          <div className="space-y-1.5 text-left">
            <PasswordInput
              placeholder="Password"
              value={password}
              onChange={(e) => {
                setPassword(e.target.value);
                if (errors.password) setErrors((prev) => ({ ...prev, password: '' }));
              }}
              error={errors.password}
              autoComplete="new-password"
              disabled={loading}
            />

            {/* Live Strength Meter */}
            {password && (
              <div className="pt-1 px-1 space-y-1">
                <div className="flex items-center justify-between text-[11px]">
                  <span className="text-gray-500">Password strength:</span>
                  <span
                    className={cn(
                      'font-semibold',
                      strength.label === 'Weak' && 'text-red-600',
                      strength.label === 'Medium' && 'text-amber-600',
                      strength.label === 'Strong' && 'text-emerald-600'
                    )}
                  >
                    {strength.label}
                  </span>
                </div>
                <div className="grid grid-cols-3 gap-1.5 h-1.5">
                  <div
                    className={cn(
                      'rounded-full h-full transition-colors duration-300',
                      strength.score >= 1 ? strength.color : 'bg-gray-200'
                    )}
                  />
                  <div
                    className={cn(
                      'rounded-full h-full transition-colors duration-300',
                      strength.score >= 2 ? strength.color : 'bg-gray-200'
                    )}
                  />
                  <div
                    className={cn(
                      'rounded-full h-full transition-colors duration-300',
                      strength.score >= 3 ? strength.color : 'bg-gray-200'
                    )}
                  />
                </div>
              </div>
            )}
            <p className="text-[11px] text-gray-400 pl-1">
              At least 8 characters with a number and a symbol
            </p>
          </div>

          {/* Confirm Password */}
          <PasswordInput
            placeholder="Confirm password"
            value={confirmPassword}
            onChange={(e) => {
              setConfirmPassword(e.target.value);
              if (errors.confirmPassword) setErrors((prev) => ({ ...prev, confirmPassword: '' }));
            }}
            error={errors.confirmPassword}
            autoComplete="new-password"
            disabled={loading}
          />

          {/* Checkboxes */}
          <div className="pt-2 text-left space-y-2">
            {/* Terms of Service & Privacy Policy Links */}
            <div>
              <label className="flex items-start gap-2.5 text-[13px] text-gray-600 cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={agreeTerms}
                  onChange={(e) => {
                    setAgreeTerms(e.target.checked);
                    if (errors.terms) setErrors((prev) => ({ ...prev, terms: '' }));
                  }}
                  className="mt-0.5 rounded text-slate-800 focus:ring-slate-400 accent-slate-800 h-4 w-4"
                />
                <span>
                  I agree to the{' '}
                  <Link
                    to="/terms"
                    target="_blank"
                    className="font-medium text-gray-900 underline hover:text-black"
                  >
                    Terms of Service
                  </Link>{' '}
                  and{' '}
                  <Link
                    to="/privacy"
                    target="_blank"
                    className="font-medium text-gray-900 underline hover:text-black"
                  >
                    Privacy Policy
                  </Link>
                </span>
              </label>
              {errors.terms && (
                <p className="text-[12px] text-red-600 mt-1 pl-6 font-medium">
                  {errors.terms}
                </p>
              )}
            </div>

            {/* Legal authorization confirmation */}
            <label className="flex items-start gap-2.5 text-[13px] text-gray-600 cursor-pointer select-none">
              <input
                type="checkbox"
                checked={authorizedUse}
                onChange={(e) => setAuthorizedUse(e.target.checked)}
                className="mt-0.5 rounded text-slate-800 focus:ring-slate-400 accent-slate-800 h-4 w-4"
              />
              <span>
                I will only use ADFIP on evidence I am legally authorized to examine.
              </span>
            </label>
          </div>

          {/* Primary Button: 'Create Account' */}
          <div className="pt-2">
            <PrimaryButton type="submit" loading={loading} disabled={loading}>
              Create Account
            </PrimaryButton>
          </div>
        </form>

        {/* Divider */}
        <div className="relative flex items-center justify-center my-6">
          <div className="absolute inset-0 flex items-center">
            <div className="w-full border-t border-dashed border-gray-300" />
          </div>
          <span className="relative px-3 bg-[#fdfefe] text-xs text-gray-400 font-medium">
            Or continue with
          </span>
        </div>

        {/* Social Button: Google */}
        <SocialButtons
          onGoogle={handleGoogleSignUp}
          disabled={loading}
        />
        {socialNotice && (
          <p className="mt-2.5 text-xs text-amber-800 bg-amber-50/90 border border-amber-200 rounded-[12px] p-2.5 text-center leading-relaxed">
            {socialNotice}
          </p>
        )}

        {/* Footer Link to Sign in */}
        <p className="text-[14px] text-gray-600 mt-6">
          Already have an account?{' '}
          <Link
            to="/signin"
            className="font-bold text-gray-900 hover:underline cursor-pointer"
          >
            Sign in
          </Link>
        </p>

        {/* Legal Links */}
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
