export const Metric = ({ label, value, tone }: { label: string; value: string; tone: 'green' | 'red' | 'amber' | 'blue' }) => (
  <div className="metric-card">
    <span>{label}</span>
    <strong className={`metric-card__value metric-card__value--${tone}`}>{value}</strong>
    {tone === 'green' && <div className="metric-bar"><span style={{ width: value.endsWith('%') ? value : '0%' }} /></div>}
  </div>
);
