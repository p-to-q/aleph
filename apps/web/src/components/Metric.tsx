export function Metric(props: { label: string; value: string | number }) {
  return <div className="metric"><strong>{props.value}</strong><span>{props.label}</span></div>;
}
