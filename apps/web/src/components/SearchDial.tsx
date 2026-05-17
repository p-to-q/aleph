export function SearchDial(props: { progress: number }) {
  return (
    <div className="dial" style={{ "--dial": `${Math.round(props.progress * 360)}deg` } as React.CSSProperties}>
      <span>{Math.round(props.progress * 100)}%</span>
    </div>
  );
}
