import { Loader2, X } from "lucide-react";
import { clsx } from "clsx";
import type {
  ButtonHTMLAttributes,
  InputHTMLAttributes,
  PropsWithChildren,
  ReactNode,
  SelectHTMLAttributes,
  TextareaHTMLAttributes,
} from "react";
import { useEffect } from "react";

export function Panel({ className, children }: PropsWithChildren<{ className?: string }>) {
  return (
    <section
      className={clsx(
        "rounded-xl border border-dify-border bg-dify-surface p-5 shadow-card",
        className,
      )}
    >
      {children}
    </section>
  );
}

export function Button({
  className,
  children,
  busy,
  size = "md",
  ...props
}: PropsWithChildren<
  {
    className?: string;
    busy?: boolean;
    size?: "sm" | "md" | "lg" | "icon";
  } & ButtonHTMLAttributes<HTMLButtonElement>
>) {
  const sizeClassName = {
    sm: "h-8 px-3 text-xs",
    md: "h-10 px-4 text-sm",
    lg: "h-11 px-5 text-sm",
    icon: "h-9 w-9 p-0",
  }[size];

  return (
      <button
        className={clsx(
          "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-xl border font-medium transition duration-150",
          "focus-visible:outline-none focus-visible:ring-4 active:translate-y-px disabled:cursor-not-allowed disabled:translate-y-0",
          sizeClassName,
          className,
        )}
        disabled={busy || props.disabled}
        {...props}
    >
      {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
      {children}
    </button>
  );
}

export function PrimaryButton({ className, ...props }: Parameters<typeof Button>[0]) {
  return (
    <Button
      className={clsx(
        "border-dify-blue text-white shadow-[0_10px_28px_rgba(37,99,235,0.22)] [background-image:var(--gradient-primary)]",
        "focus-visible:ring-dify-blue/30 disabled:opacity-70 disabled:shadow-none",
        "hover:border-dify-accent/50 hover:shadow-[0_14px_34px_rgba(8,145,178,0.2)] hover:[background-image:var(--gradient-primary-hover)]",
        className,
      )}
      {...props}
    />
  );
}

export function SecondaryButton({ className, ...props }: Parameters<typeof Button>[0]) {
  return (
    <Button
      className={clsx(
        "border-dify-border bg-dify-surface text-dify-text focus-visible:ring-dify-blue/20",
        "hover:border-dify-borderStrong hover:bg-dify-muted disabled:border-dify-border/70 disabled:bg-dify-muted/40 disabled:text-dify-subtext",
        className,
      )}
      {...props}
    />
  );
}

export function DangerButton({ className, ...props }: Parameters<typeof Button>[0]) {
  return (
    <Button
      className={clsx(
        "border-dify-danger/35 bg-dify-dangerSoft/55 text-dify-danger focus-visible:ring-dify-danger/30",
        "hover:border-dify-danger/45 hover:bg-dify-dangerSoft disabled:border-dify-danger/20 disabled:bg-dify-dangerSoft/35 disabled:text-dify-danger/70",
        className,
      )}
      {...props}
    />
  );
}

export function Input(
  props: InputHTMLAttributes<HTMLInputElement> & {
    label?: string;
    help?: string;
  },
) {
  const { label, help, className, ...rest } = props;
  return (
    <label className="block space-y-1.5">
      {label ? <span className="text-sm font-medium text-dify-text">{label}</span> : null}
      <input
        className={clsx(
          "w-full rounded-xl border border-dify-border bg-dify-surface px-3 py-2.5 text-sm text-dify-text outline-none",
          "placeholder:text-dify-softText focus:border-dify-blue focus:ring-4 focus:ring-dify-blue/10",
          className,
        )}
        {...rest}
      />
      {help ? <p className="text-xs text-dify-subtext">{help}</p> : null}
    </label>
  );
}

export function Select(
  props: SelectHTMLAttributes<HTMLSelectElement> & {
    label?: string;
  },
) {
  const { label, className, children, ...rest } = props;
  return (
    <label className="block space-y-1.5">
      {label ? <span className="text-sm font-medium text-dify-text">{label}</span> : null}
      <select
        className={clsx(
          "w-full rounded-xl border border-dify-border bg-dify-surface px-3 py-2.5 text-sm text-dify-text outline-none",
          "focus:border-dify-blue focus:ring-4 focus:ring-dify-blue/10",
          className,
        )}
        {...rest}
      >
        {children}
      </select>
    </label>
  );
}

export function Checkbox(
  props: Omit<InputHTMLAttributes<HTMLInputElement>, "type"> & {
    label: string;
    help?: string;
  },
) {
  const { label, help, className, ...rest } = props;
  return (
    <label className="flex items-start gap-3 rounded-xl border border-dify-border bg-dify-surface px-3 py-3">
      <input
        type="checkbox"
        className={clsx(
          "mt-0.5 h-4 w-4 rounded border-dify-border text-dify-blue focus:ring-4 focus:ring-dify-blue/10",
          className,
        )}
        {...rest}
      />
      <span className="space-y-1">
        <span className="block text-sm font-medium text-dify-text">{label}</span>
        {help ? <span className="block text-xs leading-5 text-dify-subtext">{help}</span> : null}
      </span>
    </label>
  );
}

export function Textarea(
  props: TextareaHTMLAttributes<HTMLTextAreaElement> & {
    label?: string;
  },
) {
  const { label, className, ...rest } = props;
  return (
    <label className="block space-y-1.5">
      {label ? <span className="text-sm font-medium text-dify-text">{label}</span> : null}
      <textarea
        className={clsx(
          "min-h-20 w-full rounded-xl border border-dify-border bg-dify-surface px-3 py-2.5 text-sm text-dify-text outline-none",
          "placeholder:text-dify-softText focus:border-dify-blue focus:ring-4 focus:ring-dify-blue/10",
          className,
        )}
        {...rest}
      />
    </label>
  );
}

export function StatusMessage({
  title,
  description,
  action,
}: {
  title: string;
  description?: string;
  action?: ReactNode;
}) {
  return (
    <div className="rounded-xl border border-dify-borderStrong/70 bg-dify-muted/80 px-4 py-8 text-center shadow-[inset_0_1px_0_rgba(255,255,255,0.04)]">
      <p className="font-medium text-dify-text">{title}</p>
      {description ? <p className="mt-1 text-sm text-dify-subtext">{description}</p> : null}
      {action ? <div className="mt-4">{action}</div> : null}
    </div>
  );
}

export function Badge({ children, className }: PropsWithChildren<{ className?: string }>) {
  return (
    <span
      className={clsx(
        "inline-flex items-center rounded-full border border-dify-borderStrong/70 bg-dify-muted/80 px-2.5 py-1 text-xs text-dify-subtext",
        className,
      )}
    >
      {children}
    </span>
  );
}

export function PanelHeader({
  title,
  description,
  action,
  icon,
  bordered = false,
}: {
  title: string;
  description?: string;
  action?: ReactNode;
  icon?: ReactNode;
  bordered?: boolean;
}) {
  return (
    <div
      className={clsx(
        "flex flex-wrap items-start justify-between gap-4",
        bordered ? "border-b border-dify-border px-5 py-4" : "mb-4",
      )}
    >
      <div className="space-y-1.5">
        <div className="flex items-center gap-2">
          <h2 className="text-lg font-semibold text-dify-text">{title}</h2>
          {icon ? <span className="text-dify-subtext">{icon}</span> : null}
        </div>
        {description ? <p className="text-sm text-dify-subtext">{description}</p> : null}
      </div>
      {action ? <div className="shrink-0">{action}</div> : null}
    </div>
  );
}

export function PageHeader({
  eyebrow,
  title,
  description,
  action,
}: {
  eyebrow?: string;
  title: string;
  description?: string;
  action?: ReactNode;
}) {
  return (
    <div
      className="relative overflow-hidden rounded-2xl border border-dify-border/70 px-5 py-5 shadow-[var(--header-shadow)]"
      style={{ backgroundColor: "var(--header-surface)" }}
    >
      <div className="pointer-events-none absolute inset-0 opacity-100">
        <div className="absolute inset-0" style={{ backgroundImage: "var(--header-aura-left), var(--header-aura-right)" }} />
        <div className="absolute inset-x-6 bottom-0 h-px bg-gradient-to-r from-transparent via-dify-accent/25 to-transparent" />
      </div>
      <div className="relative flex flex-wrap items-start justify-between gap-4">
      <div className="space-y-2">
        {eyebrow ? <p className="text-xs font-medium uppercase tracking-[0.14em] text-dify-accent/80">{eyebrow}</p> : null}
        <h1 className="text-[28px] font-semibold tracking-[-0.02em] text-dify-text">{title}</h1>
        {description ? <p className="max-w-3xl text-sm leading-6 text-dify-subtext">{description}</p> : null}
      </div>
      {action ? <div className="shrink-0">{action}</div> : null}
      </div>
    </div>
  );
}

export function Modal({
  open,
  title,
  onClose,
  children,
}: {
  open: boolean;
  title: string;
  onClose: () => void;
  children: ReactNode;
}) {
  useEffect(() => {
    if (!open) {
      return;
    }

    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        onClose();
      }
    }

    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [open, onClose]);

  if (!open) {
    return null;
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-dify-overlay/40 p-4 animate-rise-in"
      onClick={onClose}
    >
      <div
        className="w-full max-w-2xl rounded-2xl border border-dify-border bg-dify-surface shadow-card animate-rise-in"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="flex items-center justify-between border-b border-dify-border px-5 py-4">
          <h2 className="text-lg font-semibold text-dify-text">{title}</h2>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg p-1.5 text-dify-subtext transition hover:bg-dify-muted hover:text-dify-text"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
        <div className="px-5 py-5">{children}</div>
      </div>
    </div>
  );
}
