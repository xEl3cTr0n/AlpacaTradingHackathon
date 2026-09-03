import { Activity, BookOpen, ChartNoAxesCombined, Scale, ShieldCheck, TrendingUp } from "lucide-react";
import type { AgentVerdict } from "@/lib/types";

const icons = {
  Technical: Activity,
  Swing: ChartNoAxesCombined,
  Rotation: ChartNoAxesCombined,
  Research: BookOpen,
  Bull: TrendingUp,
  Bear: Scale,
  Risk: ShieldCheck,
};

export function AgentCard({ verdict }: { verdict: AgentVerdict }) {
  const Icon = icons[verdict.agent as keyof typeof icons] ?? Activity;
  return (
    <article className="agent-card">
      <div className="agent-heading">
        <span className="icon-tile"><Icon size={18} aria-hidden="true" /></span>
        <div>
          <p className="eyebrow">{verdict.agent} agent</p>
          <span className={`stance stance-${verdict.stance}`}>{verdict.stance}</span>
        </div>
        <strong>{Math.round(verdict.confidence * 100)}%</strong>
      </div>
      <p className="agent-summary">{verdict.summary}</p>
      <ul>
        {verdict.evidence.slice(0, 2).map((item) => <li key={item}>{item}</li>)}
      </ul>
    </article>
  );
}
