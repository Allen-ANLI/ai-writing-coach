"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { useAuth } from "@/features/auth/auth-provider";
import { RequireAuth } from "@/features/auth/require-auth";
import { fetchMe, fetchSessions } from "@/services/auth";

function ProfileContent() {
  const { user, logout } = useAuth();
  const router = useRouter();

  const meQuery = useQuery({
    queryKey: ["me"],
    queryFn: async () => (await fetchMe()).data,
  });
  const sessionsQuery = useQuery({
    queryKey: ["auth-sessions"],
    queryFn: async () => (await fetchSessions()).data,
  });

  async function handleLogout() {
    await logout();
    router.replace("/login");
  }

  const me = meQuery.data;
  const sessions = sessionsQuery.data;

  return (
    <main className="mx-auto w-full max-w-2xl flex-1 space-y-8 px-6 py-12">
      <header className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-zinc-900 dark:text-zinc-50">
            Your profile
          </h1>
          <p className="mt-1 text-sm text-zinc-500 dark:text-zinc-400">
            Signed in as <span data-testid="profile-email">{user?.email}</span>
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Link
            href="/dashboard"
            className="rounded-md border border-zinc-300 px-3 py-1.5 text-sm font-medium text-zinc-700 transition-colors hover:bg-zinc-100 dark:border-zinc-700 dark:text-zinc-300 dark:hover:bg-zinc-900"
          >
            Dashboard
          </Link>
          <button
            type="button"
            data-testid="refresh-data"
            onClick={() => {
              void meQuery.refetch();
              void sessionsQuery.refetch();
            }}
            className="rounded-md border border-zinc-300 px-3 py-1.5 text-sm font-medium text-zinc-700 transition-colors hover:bg-zinc-100 dark:border-zinc-700 dark:text-zinc-300 dark:hover:bg-zinc-900"
          >
            Refresh data
          </button>
          <button
            type="button"
            onClick={() => void handleLogout()}
            className="rounded-md border border-zinc-300 px-3 py-1.5 text-sm font-medium text-zinc-700 transition-colors hover:bg-zinc-100 dark:border-zinc-700 dark:text-zinc-300 dark:hover:bg-zinc-900"
          >
            Sign out
          </button>
        </div>
      </header>

      <section
        aria-label="Account details"
        className="rounded-xl border border-zinc-200 bg-white p-6 dark:border-zinc-800 dark:bg-zinc-950"
      >
        <h2 className="text-sm font-medium uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
          Account
        </h2>
        {meQuery.isPending && <p className="mt-3 text-sm text-zinc-500">Loading profile…</p>}
        {meQuery.isError && (
          <p role="alert" className="mt-3 text-sm text-red-600 dark:text-red-400">
            Could not load your profile.
          </p>
        )}
        {me && (
          <dl className="mt-3 grid grid-cols-1 gap-x-6 gap-y-2 text-sm sm:grid-cols-2">
            <div>
              <dt className="text-zinc-500 dark:text-zinc-400">Display name</dt>
              <dd className="font-medium text-zinc-900 dark:text-zinc-100" data-testid="display-name">
                {me.profile.display_name ?? "—"}
              </dd>
            </div>
            <div>
              <dt className="text-zinc-500 dark:text-zinc-400">Status</dt>
              <dd className="font-medium text-zinc-900 dark:text-zinc-100">{me.status}</dd>
            </div>
            <div>
              <dt className="text-zinc-500 dark:text-zinc-400">Native language</dt>
              <dd className="font-medium text-zinc-900 dark:text-zinc-100">{me.profile.native_language}</dd>
            </div>
            <div>
              <dt className="text-zinc-500 dark:text-zinc-400">Target exam</dt>
              <dd className="font-medium text-zinc-900 dark:text-zinc-100">{me.profile.target_exam ?? "—"}</dd>
            </div>
            <div>
              <dt className="text-zinc-500 dark:text-zinc-400">Email verified</dt>
              <dd className="font-medium text-zinc-900 dark:text-zinc-100">
                {me.email_verified_at ? "Yes" : "Not yet"}
              </dd>
            </div>
            <div>
              <dt className="text-zinc-500 dark:text-zinc-400">Member since</dt>
              <dd className="font-medium text-zinc-900 dark:text-zinc-100">
                {new Date(me.created_at).toLocaleDateString()}
              </dd>
            </div>
          </dl>
        )}
      </section>

      <section
        aria-label="Device sessions"
        className="rounded-xl border border-zinc-200 bg-white p-6 dark:border-zinc-800 dark:bg-zinc-950"
      >
        <h2 className="text-sm font-medium uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
          Device sessions
        </h2>
        {sessionsQuery.isPending && <p className="mt-3 text-sm text-zinc-500">Loading sessions…</p>}
        {sessionsQuery.isError && (
          <p role="alert" className="mt-3 text-sm text-red-600 dark:text-red-400">
            Could not load your sessions.
          </p>
        )}
        {sessions && (
          <ul className="mt-3 space-y-2" data-testid="session-list">
            {sessions.map((session) => (
              <li
                key={session.id}
                className="flex items-center justify-between gap-3 rounded-lg border border-zinc-100 px-3 py-2 text-sm dark:border-zinc-900"
              >
                <div className="min-w-0">
                  <p className="truncate font-medium text-zinc-900 dark:text-zinc-100">
                    {session.ip_address ?? "Unknown IP"}
                    {session.is_current && (
                      <span className="ml-2 rounded-full bg-emerald-100 px-2 py-0.5 text-xs font-medium text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300">
                        This device
                      </span>
                    )}
                  </p>
                  <p className="truncate text-xs text-zinc-500 dark:text-zinc-400">
                    Started {new Date(session.created_at).toLocaleString()}
                  </p>
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>
    </main>
  );
}

export default function ProfilePage() {
  return (
    <RequireAuth>
      <ProfileContent />
    </RequireAuth>
  );
}
