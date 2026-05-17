import type { ReactNode } from "react";

export function Panel(props: { title: string; badge?: string; children: ReactNode }) {
  return (
    <div className="panel mini">
      <p className="eyebrow">
        {props.title}
        {props.badge && <span className="mode-badge">{props.badge}</span>}
      </p>
      {props.children}
    </div>
  );
}
