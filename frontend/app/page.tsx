import { Dashboard } from "@/app/_components/dashboard";
import { fetchPlatform, fetchSnapshot } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function Home() {
  const [snapshot, platform] = await Promise.all([fetchSnapshot("SPY"), fetchPlatform()]);
  return <Dashboard initialSnapshot={snapshot} initialPlatform={platform} />;
}
