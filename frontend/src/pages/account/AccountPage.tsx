import React, { useState, useEffect, useRef } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Save,
  Upload,
  Trash2,
  CheckCircle2,
  AlertTriangle,
  Loader2,
} from 'lucide-react';
import { authService } from '../../services/auth';
import { normalizeError } from '../../services/client';
import { useAuthStore } from '../../stores/authStore';
import { Card } from '../../components/ui/Card';
import { StatusBadge } from '../../components/ui/Badge';
import { Button } from '../../components/ui/Button';
import { Input } from '../../components/ui/Input';
import { Skeleton } from '../../components/ui/Skeleton';
import { ErrorState } from '../../components/ui/ErrorState';
import { SectionHeader } from '../../components/ui/SectionHeader';
import { formatTimestamp } from '../../lib/utils';
import type { UserProfile } from '../../types';

export const AccountPage: React.FC = () => {
  const qc = useQueryClient();
  const updateUserStore = useAuthStore((s) => s.updateUser);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [name, setName] = useState('');
  const [badgeNumber, setBadgeNumber] = useState('');
  const [saveSuccess, setSaveSuccess] = useState<string | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [avatarError, setAvatarError] = useState<string | null>(null);

  const {
    data: user,
    isLoading,
    isError,
    error,
    refetch,
  } = useQuery({
    queryKey: ['auth-me'],
    queryFn: () => authService.me(),
    staleTime: 60_000,
  });

  useEffect(() => {
    if (user) {
      setName(user.name || '');
      setBadgeNumber(user.badge_number || user.badge_id || '');
    }
  }, [user]);

  const updateProfileMutation = useMutation({
    mutationFn: (data: { name: string; badge_number: string }) =>
      authService.updateProfile({ name: data.name, badge_number: data.badge_number, badge_id: data.badge_number }),
    onSuccess: (updatedUser: UserProfile) => {
      qc.setQueryData(['auth-me'], updatedUser);
      updateUserStore(updatedUser);
      setSaveSuccess('Profile successfully updated.');
      setSaveError(null);
      setTimeout(() => setSaveSuccess(null), 3000);
    },
    onError: (err) => {
      setSaveError(normalizeError(err));
      setSaveSuccess(null);
    },
  });

  const uploadAvatarMutation = useMutation({
    mutationFn: (file: File) => authService.uploadAvatar(file),
    onSuccess: (updatedUser: UserProfile) => {
      qc.setQueryData(['auth-me'], updatedUser);
      updateUserStore(updatedUser);
      setAvatarError(null);
    },
    onError: (err) => {
      setAvatarError(normalizeError(err));
    },
  });

  const deleteAvatarMutation = useMutation({
    mutationFn: () => authService.deleteAvatar(),
    onSuccess: (updatedUser: UserProfile) => {
      qc.setQueryData(['auth-me'], updatedUser);
      updateUserStore(updatedUser);
      setAvatarError(null);
    },
    onError: (err) => {
      setAvatarError(normalizeError(err));
    },
  });

  const handleSaveProfile = (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) {
      setSaveError('Full Name is required.');
      return;
    }
    updateProfileMutation.mutate({ name: name.trim(), badge_number: badgeNumber.trim() });
  };

  const handleAvatarFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    if (!['image/png', 'image/jpeg', 'image/webp'].includes(file.type)) {
      setAvatarError('Invalid file format. Please upload a PNG, JPEG, or WebP image.');
      return;
    }

    if (file.size > 2 * 1024 * 1024) {
      setAvatarError('Image exceeds the maximum allowed size of 2MB.');
      return;
    }

    setAvatarError(null);
    uploadAvatarMutation.mutate(file);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const initials = user
    ? (user.name || user.email)
        .split(' ')
        .filter(Boolean)
        .map((p) => p[0])
        .slice(0, 2)
        .join('')
        .toUpperCase()
    : 'DF';

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <SectionHeader
        title="Investigator Account & Profile"
        description="Manage your investigator credentials, badge registration, and secure profile avatar."
      />

      {isLoading && (
        <div className="space-y-4">
          <Skeleton className="h-32 w-full rounded-lg" />
          <Skeleton className="h-64 w-full rounded-lg" />
        </div>
      )}

      {isError && (
        <ErrorState message={normalizeError(error)} onRetry={refetch} />
      )}

      {user && (
        <>
          {/* Avatar & Identity Card */}
          <Card className="p-5">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-5">
              <div className="flex items-center gap-4">
                <div className="relative group shrink-0">
                  {user.avatar_url ? (
                    <img
                      src={user.avatar_url}
                      alt={user.name || 'Investigator Avatar'}
                      className="w-16 h-16 rounded-full object-cover border-2 border-stone-300 shadow-sm"
                      onError={(e) => {
                        (e.target as HTMLElement).style.display = 'none';
                      }}
                    />
                  ) : (
                    <div className="w-16 h-16 rounded-full bg-slate-800 text-white flex items-center justify-center font-bold text-lg tracking-wider border-2 border-stone-300 shadow-sm">
                      {initials}
                    </div>
                  )}
                  {uploadAvatarMutation.isPending && (
                    <div className="absolute inset-0 rounded-full bg-black/40 flex items-center justify-center text-white">
                      <Loader2 className="w-5 h-5 animate-spin" />
                    </div>
                  )}
                </div>

                <div>
                  <h2 className="text-base font-bold text-slate-900 leading-tight">
                    {user.name || user.email}
                  </h2>
                  <p className="text-xs text-slate-500 font-mono mt-0.5">{user.email}</p>
                  <div className="flex items-center gap-2 mt-1.5">
                    <StatusBadge status={user.role || 'INVESTIGATOR'} />
                    <span className="text-[11px] text-slate-400 font-sans">
                      {user.organization || 'Not specified'}
                    </span>
                  </div>
                </div>
              </div>

              {/* Avatar upload/remove buttons */}
              <div className="flex items-center gap-2 shrink-0">
                <input
                  ref={fileInputRef}
                  type="file"
                  accept="image/png,image/jpeg,image/webp"
                  className="hidden"
                  onChange={handleAvatarFileChange}
                />
                <Button
                  variant="secondary"
                  size="sm"
                  icon={<Upload className="w-3.5 h-3.5" />}
                  loading={uploadAvatarMutation.isPending}
                  onClick={() => fileInputRef.current?.click()}
                >
                  Upload Photo
                </Button>
                {user.avatar_url && (
                  <Button
                    variant="ghost"
                    size="sm"
                    icon={<Trash2 className="w-3.5 h-3.5 text-red-500" />}
                    loading={deleteAvatarMutation.isPending}
                    onClick={() => deleteAvatarMutation.mutate()}
                    title="Remove avatar"
                  >
                    Remove
                  </Button>
                )}
              </div>
            </div>

            {avatarError && (
              <div className="mt-3 p-2.5 bg-red-50 border border-red-200 rounded text-xs text-red-700 flex items-center gap-2">
                <AlertTriangle className="w-4 h-4 shrink-0 text-red-500" />
                <span>{avatarError}</span>
              </div>
            )}
            <p className="text-[11px] text-slate-400 mt-3 pt-3 border-t border-stone-100">
              Avatar images are stored on your secure forensic workstation. Allowed formats: PNG, JPEG, WebP (max 2MB).
            </p>
          </Card>

          {/* Editable Investigator Information Form */}
          <Card className="p-5">
            <h3 className="text-sm font-semibold text-slate-900 mb-1">
              Investigator Credentials
            </h3>
            <p className="text-xs text-slate-500 mb-4">
              Update your workstation investigator display name and official badge identifier for audit trail attribution.
            </p>

            {saveSuccess && (
              <div className="mb-4 p-2.5 bg-emerald-50 border border-emerald-200 rounded text-xs text-emerald-800 flex items-center gap-2">
                <CheckCircle2 className="w-4 h-4 shrink-0 text-emerald-600" />
                <span>{saveSuccess}</span>
              </div>
            )}

            {saveError && (
              <div className="mb-4 p-2.5 bg-red-50 border border-red-200 rounded text-xs text-red-700 flex items-center gap-2">
                <AlertTriangle className="w-4 h-4 shrink-0 text-red-500" />
                <span>{saveError}</span>
              </div>
            )}

            <form onSubmit={handleSaveProfile} className="space-y-4">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <Input
                  label="Full Name"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="e.g. John Doe"
                  required
                />
                <Input
                  label="Badge ID / Number"
                  value={badgeNumber}
                  onChange={(e) => setBadgeNumber(e.target.value)}
                  placeholder="e.g. DFU-4029"
                  helper="Included in evidence chain-of-custody and final reports"
                />
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-2 border-t border-stone-100">
                <Input
                  label="Email Address"
                  value={user.email}
                  readOnly
                  disabled
                  helper="Account identifier cannot be modified"
                />
                <Input
                  label="Assigned Role"
                  value={user.role || 'INVESTIGATOR'}
                  readOnly
                  disabled
                  helper="Roles are governed by system administration"
                />
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <Input
                  label="Forensic Unit / Organization"
                  value={user.organization || 'Not specified'}
                  readOnly
                  disabled
                />
                <Input
                  label="Registered Member Since"
                  value={formatTimestamp(user.created_at)}
                  readOnly
                  disabled
                />
              </div>

              <div className="flex items-center justify-end pt-3 border-t border-stone-100">
                <Button
                  type="submit"
                  variant="primary"
                  size="sm"
                  icon={<Save className="w-3.5 h-3.5" />}
                  loading={updateProfileMutation.isPending}
                >
                  Save Changes
                </Button>
              </div>
            </form>
          </Card>
        </>
      )}
    </div>
  );
};
