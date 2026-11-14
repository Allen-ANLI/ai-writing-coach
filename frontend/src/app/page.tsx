import { AuthNav } from "@/components/auth-nav";
import { HealthStatus } from "@/components/health-status";

export default function Home() {
  return (
    <main className="flex flex-1 flex-col items-center justify-center gap-8 px-6 py-16">
      <div className="text-center">
        <h1 className="text-3xl font-semibold tracking-tight text-zinc-900 dark:text-zinc-50">
          AI Writing Coach
        </h1>
        <p className="mt-2 text-zinc-600 dark:text-zinc-400">
          English writing training — backend authentication is live.
        </p>
      </div>
      <AuthNav />
      <HealthStatus />
    </main>
  );
}
