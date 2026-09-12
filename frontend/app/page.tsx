import { Dashboard } from "@/app/_components/dashboard";
import { fetchPlatform, fetchScanner, fetchSnapshot } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function Home() {
  const [snapshot, platform, scanner] = await Promise.all([
    fetchSnapshot("SPY"),
    // An account endpoint outage should not hide read-only market research.
    fetchPlatform().catch(() => null),
    fetchScanner(),
  ]);
  return (
    <Dashboard
      initialSnapshot={snapshot}
      initialPlatform={platform}
      initialScanner={scanner}
    />
  );
}
