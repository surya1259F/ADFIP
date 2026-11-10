import React, { useState, useEffect } from 'react';
import { authService } from '../../services/auth';

interface UserAvatarProps {
  user?: {
    name?: string | null;
    email?: string | null;
    avatar_url?: string | null;
  } | null;
  previewUrl?: string | null;
  size?: 'xs' | 'sm' | 'md' | 'lg' | 'xl';
  className?: string;
  showBorder?: boolean;
}

const sizeClasses = {
  xs: 'w-5 h-5 text-[9px]',
  sm: 'w-6 h-6 text-[10px]',
  md: 'w-8 h-8 text-xs',
  lg: 'w-12 h-12 text-sm',
  xl: 'w-16 h-16 text-lg',
};

export const UserAvatar: React.FC<UserAvatarProps> = ({
  user,
  previewUrl,
  size = 'md',
  className = '',
  showBorder = true,
}) => {
  const [avatarSrc, setAvatarSrc] = useState<string | null>(null);
  const [hasError, setHasError] = useState(false);

  useEffect(() => {
    setHasError(false);
    if (previewUrl) {
      setAvatarSrc(previewUrl);
      return;
    }

    if (!user?.avatar_url) {
      setAvatarSrc(null);
      return;
    }

    let isMounted = true;
    let objectUrl: string | null = null;

    // Fetch avatar securely via authenticated blob retrieval
    authService
      .getAvatarBlob()
      .then((blob) => {
        if (!isMounted) return;
        if (blob && blob.size > 0 && blob.type.startsWith('image/')) {
          objectUrl = URL.createObjectURL(blob);
          setAvatarSrc(objectUrl);
          setHasError(false);
        } else {
          setAvatarSrc(null);
        }
      })
      .catch(() => {
        if (!isMounted) return;
        // Fallback: try direct authenticated URL with session token if blob fails
        const token = sessionStorage.getItem('adfip_token');
        if (user.avatar_url && token) {
          const sep = user.avatar_url.includes('?') ? '&' : '?';
          setAvatarSrc(`${user.avatar_url}${sep}token=${encodeURIComponent(token)}`);
          setHasError(false);
        } else {
          setAvatarSrc(null);
          setHasError(true);
        }
      });

    return () => {
      isMounted = false;
      if (objectUrl) {
        URL.revokeObjectURL(objectUrl);
      }
    };
  }, [user?.avatar_url, previewUrl]);

  const initials = (user?.name || user?.email || 'IN')
    .split(' ')
    .map((part) => part[0])
    .join('')
    .slice(0, 2)
    .toUpperCase();

  const dimensionClass = sizeClasses[size] || sizeClasses.md;
  const borderClass = showBorder ? 'border border-stone-300 shadow-2xs' : '';

  if (avatarSrc && !hasError) {
    return (
      <img
        src={avatarSrc}
        alt={user?.name || 'Investigator Avatar'}
        className={`${dimensionClass} rounded-full object-cover shrink-0 ${borderClass} ${className}`}
        onError={() => setHasError(true)}
      />
    );
  }

  return (
    <div
      className={`${dimensionClass} rounded-full bg-slate-800 text-white font-bold flex items-center justify-center shrink-0 tracking-wider ${borderClass} ${className}`}
      title={user?.name || user?.email || 'Investigator'}
    >
      {initials}
    </div>
  );
};
