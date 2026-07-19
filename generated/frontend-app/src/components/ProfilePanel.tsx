import { useEffect, useRef, useState } from 'react';
import { updateProfile } from '../api';
import type { CurrentUser } from '../types';
import { FoundationalQuestionnaire } from './FoundationalQuestionnaire';
import { CoachingContract } from './CoachingContract';

interface ProfilePanelProps {
  currentUser: CurrentUser;
  onProfileUpdated: (user: CurrentUser) => void;
}

const MAX_AVATAR_BYTES = 5 * 1024 * 1024; // 5 MB

function initialsFor(name: string): string {
  const trimmed = name.trim();
  if (!trimmed) return '?';
  const parts = trimmed.split(/[\s._-]+/).filter(Boolean);
  const letters = parts.length >= 2 ? parts[0][0] + parts[1][0] : trimmed.slice(0, 2);
  return letters.toUpperCase();
}

export function ProfilePanel({ currentUser, onProfileUpdated }: ProfilePanelProps): JSX.Element {
  const [username, setUsername] = useState(currentUser.username);
  const [phone, setPhone] = useState(currentUser.phone);
  const [email, setEmail] = useState(currentUser.email);
  const [avatarFile, setAvatarFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    setUsername(currentUser.username);
  }, [currentUser.username]);

  useEffect(() => {
    setPhone(currentUser.phone);
  }, [currentUser.phone]);

  useEffect(() => {
    setEmail(currentUser.email);
  }, [currentUser.email]);

  // Build (and clean up) an object URL for the locally selected image preview.
  useEffect(() => {
    if (!avatarFile) {
      setPreviewUrl(null);
      return;
    }
    const url = URL.createObjectURL(avatarFile);
    setPreviewUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [avatarFile]);

  const trimmedUsername = username.trim();
  const usernameChanged = trimmedUsername !== currentUser.username;
  const phoneChanged = phone.trim() !== currentUser.phone;
  const emailChanged = email.trim() !== currentUser.email;
  const hasChanges = usernameChanged || phoneChanged || emailChanged || avatarFile !== null;
  const shownAvatar = previewUrl ?? currentUser.avatarUrl;

  function handleFileChange(event: React.ChangeEvent<HTMLInputElement>): void {
    setError(null);
    setSuccess(null);
    const file = event.target.files?.[0] ?? null;
    if (!file) {
      setAvatarFile(null);
      return;
    }
    if (!file.type.startsWith('image/')) {
      setError('Please choose an image file.');
      setAvatarFile(null);
      return;
    }
    if (file.size > MAX_AVATAR_BYTES) {
      setError('Image must be 5 MB or smaller.');
      setAvatarFile(null);
      return;
    }
    setAvatarFile(file);
  }

  async function handleSave(event: React.FormEvent): Promise<void> {
    event.preventDefault();
    setError(null);
    setSuccess(null);

    if (!trimmedUsername) {
      setError('Username cannot be empty.');
      return;
    }
    if (!hasChanges) return;

    setSaving(true);
    try {
      const updated = await updateProfile({
        username: usernameChanged ? trimmedUsername : undefined,
        avatarFile,
        phone: phoneChanged ? phone.trim() : undefined,
        email: emailChanged ? email.trim() : undefined,
      });
      onProfileUpdated(updated);
      setAvatarFile(null);
      if (fileInputRef.current) fileInputRef.current.value = '';
      setSuccess('Profile updated.');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not update profile.');
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className='profile-panel'>
      <section className='card' aria-labelledby='profile-account-heading'>
        <h2 id='profile-account-heading'>Account</h2>
        <p className='muted'>View and update your username and profile picture.</p>

        <form onSubmit={(e) => { void handleSave(e); }}>
          <div className='profile-account-row'>
            <div className='avatar avatar-lg' aria-hidden={shownAvatar ? undefined : true}>
              {shownAvatar ? (
                <img src={shownAvatar} alt='Profile picture preview' />
              ) : (
                <span>{initialsFor(currentUser.username)}</span>
              )}
            </div>
            <div className='profile-account-fields'>
              <label htmlFor='profile-username'>Username</label>
              <input
                id='profile-username'
                type='text'
                value={username}
                maxLength={150}
                onChange={(e) => {
                  setUsername(e.target.value);
                  setSuccess(null);
                }}
                autoComplete='username'
              />

              <label htmlFor='profile-phone'>Contact phone number</label>
              <input
                id='profile-phone'
                type='tel'
                value={phone}
                maxLength={40}
                onChange={(e) => {
                  setPhone(e.target.value);
                  setSuccess(null);
                }}
                autoComplete='tel'
                placeholder='e.g. +61 400 000 000'
              />

              <label htmlFor='profile-email'>Email address</label>
              <input
                id='profile-email'
                type='email'
                value={email}
                maxLength={254}
                onChange={(e) => {
                  setEmail(e.target.value);
                  setSuccess(null);
                }}
                autoComplete='email'
                placeholder='e.g. you@example.com'
              />

              <label htmlFor='profile-avatar'>Profile picture</label>
              <input
                id='profile-avatar'
                ref={fileInputRef}
                type='file'
                accept='image/*'
                onChange={handleFileChange}
              />
              <p className='muted'>PNG or JPG, up to 5 MB. Appears in the top-right of the app.</p>
            </div>
          </div>

          {error && <p className='muted' role='alert' style={{ color: '#e5484d' }}>{error}</p>}
          {success && <p className='muted' role='status'>{success}</p>}

          <button type='submit' className='primary' disabled={saving || !hasChanges}>
            {saving ? 'Saving...' : 'Save changes'}
          </button>
        </form>
      </section>

      <CoachingContract currentUser={currentUser} />

      <FoundationalQuestionnaire currentUsername={currentUser.username} />
    </div>
  );
}
