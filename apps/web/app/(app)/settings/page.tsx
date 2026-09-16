"use client";

import { FormEvent, useEffect, useState } from "react";

import { apiRequest, ApiError } from "@/lib/api";
import { getAuthToken } from "@/lib/auth";

type Profile = {
  full_name: string | null;
  phone: string | null;
  location: string | null;
  summary: string | null;
  years_experience: number | null;
  target_titles: string[] | null;
};

type Preferences = {
  employment_types: string[] | null;
  locations: string[] | null;
  remote_preference: string | null;
  target_titles: string[] | null;
};

const emptyProfile: Profile = {
  full_name: "",
  phone: "",
  location: "",
  summary: "",
  years_experience: null,
  target_titles: [],
};

const emptyPreferences: Preferences = {
  employment_types: [],
  locations: [],
  remote_preference: "",
  target_titles: [],
};

function authHeaders(): Record<string, string> {
  const token = getAuthToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

function splitList(value: string) {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function joinList(value: string[] | null) {
  return value?.join(", ") ?? "";
}

export default function SettingsPage() {
  const [profile, setProfile] = useState<Profile>(emptyProfile);
  const [preferences, setPreferences] =
    useState<Preferences>(emptyPreferences);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function loadSettings() {
      try {
        const headers = authHeaders();
        const [profileData, preferenceData] = await Promise.all([
          apiRequest<Profile | null>("/profile/me", { headers }),
          apiRequest<Preferences | null>("/preferences/me", { headers }),
        ]);

        if (!cancelled) {
          setProfile(profileData ?? emptyProfile);
          setPreferences(preferenceData ?? emptyPreferences);
        }
      } catch (err) {
        if (!cancelled) {
          setError(
            err instanceof Error
              ? err.message
              : "Unable to load your settings.",
          );
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    loadSettings();

    return () => {
      cancelled = true;
    };
  }, []);

  async function saveSettings(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true);
    setError(null);
    setMessage(null);

    try {
      const headers = {
        ...authHeaders(),
        "Content-Type": "application/json",
      };

      const [savedProfile, savedPreferences] = await Promise.all([
        apiRequest<Profile>("/profile/me", {
          method: "PUT",
          headers,
          body: JSON.stringify(profile),
        }),
        apiRequest<Preferences>("/preferences/me", {
          method: "PUT",
          headers,
          body: JSON.stringify(preferences),
        }),
      ]);

      setProfile(savedProfile);
      setPreferences(savedPreferences);
      setMessage("Settings saved.");
    } catch (err) {
      setError(
        err instanceof ApiError || err instanceof Error
          ? err.message
          : "Unable to save your settings.",
      );
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return (
      <main className="min-h-screen bg-[#05070A] px-6 py-10 text-[#F2F5F8]">
        <div className="font-mono text-xs uppercase tracking-[0.25em] text-[#1677E8]">
          Loading settings...
        </div>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-[#05070A] px-6 py-10 text-[#F2F5F8]">
      <div className="mx-auto max-w-4xl">
        <header className="border-b border-[#1A3048] pb-8">
          <div className="font-mono text-[10px] uppercase tracking-[0.25em] text-[#E50920]">
            Account / Preferences
          </div>
          <h1 className="mt-4 text-4xl font-bold tracking-tight">
            Settings
          </h1>
          <p className="mt-3 max-w-2xl text-sm leading-7 text-[#8D9AAA]">
            Keep your profile and job-search preferences current so later
            intelligence modules can use accurate inputs.
          </p>
        </header>

        <form onSubmit={saveSettings} className="mt-8 space-y-8">
          <section className="border border-[#1A3048] bg-[#0B1626] p-6">
            <h2 className="font-mono text-[10px] uppercase tracking-[0.2em] text-[#1677E8]">
              Profile
            </h2>

            <div className="mt-6 grid gap-5 md:grid-cols-2">
              <Field
                label="Full name"
                value={profile.full_name ?? ""}
                onChange={(value) =>
                  setProfile({ ...profile, full_name: value })
                }
              />
              <Field
                label="Phone"
                value={profile.phone ?? ""}
                onChange={(value) => setProfile({ ...profile, phone: value })}
              />
              <Field
                label="Location"
                value={profile.location ?? ""}
                onChange={(value) =>
                  setProfile({ ...profile, location: value })
                }
              />
              <Field
                label="Years of experience"
                type="number"
                min="0"
                value={profile.years_experience?.toString() ?? ""}
                onChange={(value) =>
                  setProfile({
                    ...profile,
                    years_experience: value ? Number(value) : null,
                  })
                }
              />
            </div>

            <label className="mt-5 block">
              <span className="font-mono text-[10px] uppercase tracking-wider text-[#8D9AAA]">
                Target titles
              </span>
              <input
                value={joinList(profile.target_titles)}
                onChange={(event) =>
                  setProfile({
                    ...profile,
                    target_titles: splitList(event.target.value),
                  })
                }
                className="mt-2 w-full border border-[#294B70] bg-[#05070A] px-4 py-3 text-sm outline-none focus:border-[#1677E8]"
                placeholder="Machine Learning Engineer, Data Scientist"
              />
            </label>

            <label className="mt-5 block">
              <span className="font-mono text-[10px] uppercase tracking-wider text-[#8D9AAA]">
                Summary
              </span>
              <textarea
                value={profile.summary ?? ""}
                onChange={(event) =>
                  setProfile({ ...profile, summary: event.target.value })
                }
                rows={4}
                className="mt-2 w-full resize-y border border-[#294B70] bg-[#05070A] px-4 py-3 text-sm outline-none focus:border-[#1677E8]"
              />
            </label>
          </section>

          <section className="border border-[#1A3048] bg-[#0B1626] p-6">
            <h2 className="font-mono text-[10px] uppercase tracking-[0.2em] text-[#1677E8]">
              Job preferences
            </h2>

            <div className="mt-6 grid gap-5 md:grid-cols-2">
              <ListField
                label="Preferred locations"
                value={joinList(preferences.locations)}
                onChange={(value) =>
                  setPreferences({
                    ...preferences,
                    locations: splitList(value),
                  })
                }
              />
              <ListField
                label="Employment types"
                value={joinList(preferences.employment_types)}
                onChange={(value) =>
                  setPreferences({
                    ...preferences,
                    employment_types: splitList(value),
                  })
                }
              />
              <ListField
                label="Preference target titles"
                value={joinList(preferences.target_titles)}
                onChange={(value) =>
                  setPreferences({
                    ...preferences,
                    target_titles: splitList(value),
                  })
                }
              />
              <Field
                label="Remote preference"
                value={preferences.remote_preference ?? ""}
                onChange={(value) =>
                  setPreferences({
                    ...preferences,
                    remote_preference: value,
                  })
                }
                placeholder="remote, hybrid, or onsite"
              />
            </div>
          </section>

          {message && (
            <p className="border border-[#1677E8]/40 bg-[#1677E8]/10 p-4 text-sm">
              {message}
            </p>
          )}
          {error && (
            <p className="border border-[#E50920]/40 bg-[#E50920]/10 p-4 text-sm">
              {error}
            </p>
          )}

          <button
            type="submit"
            disabled={saving}
            className="bg-[#E50920] px-6 py-3 text-xs font-bold uppercase tracking-[0.15em] text-white transition hover:bg-[#FF1E32] disabled:cursor-not-allowed disabled:opacity-50"
          >
            {saving ? "Saving..." : "Save settings"}
          </button>
        </form>
      </div>
    </main>
  );
}

function Field({
  label,
  value,
  onChange,
  type = "text",
  min,
  placeholder,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  type?: string;
  min?: string;
  placeholder?: string;
}) {
  return (
    <label className="block">
      <span className="font-mono text-[10px] uppercase tracking-wider text-[#8D9AAA]">
        {label}
      </span>
      <input
        type={type}
        min={min}
        value={value}
        placeholder={placeholder}
        onChange={(event) => onChange(event.target.value)}
        className="mt-2 w-full border border-[#294B70] bg-[#05070A] px-4 py-3 text-sm outline-none focus:border-[#1677E8]"
      />
    </label>
  );
}

function ListField({
  label,
  value,
  onChange,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <Field
      label={label}
      value={value}
      onChange={onChange}
      placeholder="Separate values with commas"
    />
  );
}
