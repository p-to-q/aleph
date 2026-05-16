export function MetricCard(props: { label: string; value: string | number; note?: string }) {
  return (
    <div className="metric-card">
      <strong>{props.value}</strong>
      <span>{props.label}</span>
      {props.note ? <small>{props.note}</small> : null}
    </div>
  );
}
