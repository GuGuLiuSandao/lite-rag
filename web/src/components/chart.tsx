import { clsx } from "clsx";
import type { CSSProperties, ReactNode } from "react";

type ChartConfigItem = {
  label?: string;
  color?: string;
};

export type ChartConfig = Record<string, ChartConfigItem>;

export function ChartContainer({
  config,
  className,
  children,
}: {
  config: ChartConfig;
  className?: string;
  children: ReactNode;
}) {
  const style = Object.entries(config).reduce<CSSProperties>((acc, [key, item]) => {
    if (item.color) {
      (acc as Record<string, string>)[`--color-${key}`] = item.color;
    }
    return acc;
  }, {});

  return (
      <div
        data-chart="true"
        className={clsx(
        "[&_.recharts-cartesian-grid-horizontal_line]:stroke-dify-border [&_.recharts-cartesian-axis-tick_text]:fill-dify-subtext [&_.recharts-tooltip-cursor]:stroke-dify-border",
        className,
      )}
      style={style}
    >
      {children}
    </div>
  );
}

export function ChartTooltipContent({
  active,
  payload,
  label,
  hideLabel = false,
}: {
  active?: boolean;
  payload?: Array<{ value?: number | string; name?: string; color?: string }>;
  label?: string;
  hideLabel?: boolean;
}) {
  if (!active || !payload || payload.length === 0) {
    return null;
  }

  return (
    <div className="rounded-xl border border-dify-border bg-dify-surface/95 px-3 py-2 text-dify-text shadow-card backdrop-blur">
      {!hideLabel && label ? <p className="text-[11px] text-dify-softText">{label}</p> : null}
      <div className="mt-1 space-y-1">
        {payload.map((item) => (
          <div key={item.name} className="flex items-center gap-2 text-sm text-dify-text">
            <span className="h-2 w-2 rounded-full" style={{ backgroundColor: item.color || "rgb(var(--color-chart-1))" }} />
            <span>{item.name}</span>
            <span className="font-medium">{item.value}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
