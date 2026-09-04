import { Activity, Bot, Braces, CheckCircle2, CircleDashed, Command, DatabaseZap, ShieldCheck, Workflow } from "lucide-react";
import type { DecisionSnapshot, PlatformSnapshot } from "@/lib/types";

const integrationIcons = { "trading-api": DatabaseZap, mcp: Braces, cli: Command };

export function AgentOps({ platform, snapshot }: { platform: PlatformSnapshot; snapshot: DecisionSnapshot }) {
  return (
    <div className="view-stack">
      <header className="view-heading"><div><p className="eyebrow">Runtime transparency</p><h1>Agent operations</h1><p>See how the autonomous system uses Alpaca and reaches each decision.</p></div><span className="decision-chip approved"><Activity size={15} aria-hidden="true" /> Observability on</span></header>
      <section className="integration-grid">
        {platform.integrations.map((integration) => {
          const Icon = integrationIcons[integration.id as keyof typeof integrationIcons] ?? Workflow;
          const connected = ["connected", "configured", "external_runner"].includes(integration.status);
          return <article className="panel integration-card" key={integration.id}><div><span className="integration-icon"><Icon size={20} aria-hidden="true" /></span><span className={`integration-state ${connected ? "connected" : "pending"}`}>{connected ? <CheckCircle2 size={13} aria-hidden="true" /> : <CircleDashed size={13} aria-hidden="true" />}{integration.status.replace("_", " ")}</span></div><h2>{integration.name}</h2><p>{integration.detail}</p><small>{integration.capability}</small></article>;
        })}
      </section>
      <section className="ops-grid">
        <article className="panel pipeline-panel"><div className="panel-heading"><div><p className="eyebrow">Autonomous decision graph</p><h2>Current run pipeline</h2></div><span className="source-label">{snapshot.market.symbol}</span></div><div className="pipeline-flow">{["Macro QUAD", "Bottom-up QUAD", "MOOD / VIBE", "Agent vote", "Risk gate", "CLI paper order"].map((node, index) => <div key={node} className="pipeline-node"><span>{index + 1}</span><strong>{node}</strong>{index < 5 && <i aria-hidden="true" />}</div>)}</div><div className="run-summary"><Bot size={19} aria-hidden="true" /><div><strong>{snapshot.strategy.display_name}</strong><p>{snapshot.strategy.thesis}</p></div><span className={snapshot.risk.approved ? "positive" : "negative"}>{snapshot.risk.approved ? "authorized" : "vetoed"}</span></div></article>
        <aside className="panel activity-panel"><div className="panel-heading"><div><p className="eyebrow">Decision telemetry</p><h2>Activity stream</h2></div><Activity size={19} aria-hidden="true" /></div><ol>{platform.activity.map((event) => <li key={`${event.timestamp}-${event.title}`}><span className={`event-dot ${event.status}`} /><div><header><strong>{event.source}</strong><time>{new Date(event.timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</time></header><h3>{event.title}</h3><p>{event.detail}</p></div></li>)}</ol></aside>
      </section>
      <section className="panel safety-manifest"><ShieldCheck size={22} aria-hidden="true" /><div><p className="eyebrow">Non-negotiable invariant</p><h2>LLMs advise. Deterministic policy authorizes.</h2><p>Every run records its evidence, constraints, risk decision, and proposed structure. No agent can bypass the risk gate or paper-only execution lock.</p></div></section>
    </div>
  );
}
