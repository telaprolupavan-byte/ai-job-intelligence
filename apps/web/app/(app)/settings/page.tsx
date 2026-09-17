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
  // Hard eligibility fields (AJI-011). Unlike the soft preferences
  // above, these can make a job INELIGIBLE outright, independent of any
  // Job Match score. Leaving one unset never excludes a job.
  excluded_locations: string[] | null;
  requires_sponsorship: boolean | null;
  is_us_citizen: boolean | null;
  has_security_clearance: boolean | null;
  enforce_minimum_experience: boolean;
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
  excluded_locations: [],
  requires_sponsorship: null,
  is_us_citizen: null,
  has_security_clearance: null,
  enforce_minimum_experience: false,
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

// HTML <select> values are always strings, so a tri-state
// (unspecified/yes/no) preference is encoded as "" / "true" / "false".
function triStateToSelectValue(value: boolean | null): string {
  if (value === null) return "";
  return value ? "true" : "false";
}

function selectValueToTriState(value: string): boolean | null {
  if (value === "true") return true;
  if (value === "false") return false;
  return null;
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
            <p className="mt-2 max-w-2xl text-xs leading-6 text-[#8D9AAA]">
              Locations, employment types, and remote preference below are
              also treated as hard requirements: a job that does not match
              them will be marked ineligible, not just scored lower.
            </p>

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

          <section className="border border-[#1A3048] bg-[#0B1626] p-6">
            <h2 className="font-mono text-[10px] uppercase tracking-[0.2em] text-[#1677E8]">
              Hard eligibility
            </h2>
            <p className="mt-2 max-w-2xl text-xs leading-6 text-[#8D9AAA]">
              These requirements can rule a job out entirely. Leave any of
              them unspecified if you don&apos;t want it to affect
              eligibility.
            </p>

            <div className="mt-6 grid gap-5 md:grid-cols-2">
              <ListField
                label="Excluded locations"
                value={joinList(preferences.excluded_locations)}
                onChange={(value) =>
                  setPreferences({
                    ...preferences,
                    excluded_locations: splitList(value),
                  })
                }
              />
              <TriStateField
                label="Do you require visa sponsorship?"
                value={preferences.requires_sponsorship}
                onChange={(value) =>
                  setPreferences({
                    ...preferences,
                    requires_sponsorship: value,
                  })
                }
              />
              <TriStateField
                label="Are you a U.S. citizen?"
                value={preferences.is_us_citizen}
                onChange={(value) =>
                  setPreferences({ ...preferences, is_us_citizen: value })
                }
              />
              <TriStateField
                label="Do you hold an active security clearance?"
                value={preferences.has_security_clearance}
                onChange={(value) =>
                  setPreferences({
                    ...preferences,
                    has_security_clearance: value,
                  })
                }
              />
            </div>

            <label className="mt-5 flex items-center gap-3">
              <input
                type="checkbox"
                checked={preferences.enforce_minimum_experience}
                onChange={(event) =>
                  setPreferences({
                    ...preferences,
                    enforce_minimum_experience: event.target.checked,
                  })
                }
                className="h-4 w-4 border border-[#294B70] bg-[#05070A]"
              />
              <span className="text-sm text-[#F2F5F8]">
                Rule out jobs whose stated minimum years of experience
                exceeds my years of experience
              </span>
            </label>
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

function TriStateField({
  label,
  value,
  onChange,
}: {
  label: string;
  value: boolean | null;
  onChange: (value: boolean | null) => void;
}) {
  return (
    <label className="block">
      <span className="font-mono text-[10px] uppercase tracking-wider text-[#8D9AAA]">
        {label}
      </span>
      <select
        value={triStateToSelectValue(value)}
        onChange={(event) =>
          onChange(selectValueToTriState(event.target.value))
        }
        className="mt-2 w-full border border-[#294B70] bg-[#05070A] px-4 py-3 text-sm outline-none focus:border-[#1677E8]"
      >
        <option value="">Prefer not to say / unspecified</option>
        <option value="true">Yes</option>
        <option value="false">No</option>
      </select>
    </label>
  );
}
