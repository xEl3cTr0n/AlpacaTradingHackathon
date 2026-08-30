import { Dashboard } from "@/app/_components/dashboard";
import { fetchSnapshot } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function Home() {
  const snapshot = await fetchSnapshot("SPY");
  return <Dashboard initialSnapshot={snapshot} />;
}

