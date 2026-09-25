import type { LucideIcon } from 'lucide-react';

interface MetricCardProps {
  label: string;
  value: string;
  unit?: string;
  icon: LucideIcon;
  detail?: string;
}

export default function MetricCard({ label, value, unit, icon: Icon, detail }: MetricCardProps) {
  return (
    <article className="rounded-2xl border border-line bg-white p-5 shadow-card sm:p-6">
      <div className="flex items-center justify-between gap-3">
        <h3 className="text-sm font-medium text-muted">{label}</h3>
        <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-blue-50 text-brand">
          <Icon size={18} strokeWidth={1.8} aria-hidden="true" />
        </span>
      </div>
      <p className="mt-5 text-2xl font-semibold tracking-tight text-ink">
        {value}<span className="ml-1 text-sm font-medium text-muted">{unit}</span>
      </p>
      {detail && <p className="mt-1 text-xs text-muted">{detail}</p>}
    </article>
  );
}
