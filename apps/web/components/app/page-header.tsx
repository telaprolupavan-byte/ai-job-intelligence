import SectionLabel from "./section-label";

type PageHeaderProps = {
  eyebrow?: string;
  title: string;
  description?: string;
  action?: React.ReactNode;
};

export default function PageHeader({
  eyebrow,
  title,
  description,
  action,
}: PageHeaderProps) {
  return (
    <div className="mb-8 flex flex-col justify-between gap-5 md:flex-row md:items-end">
      <div className="min-w-0">
        {eyebrow && <SectionLabel tone="red">{eyebrow}</SectionLabel>}

        <h1 className="mt-3 text-3xl font-bold tracking-tight text-app-text">
          {title}
        </h1>

        {description && (
          <p className="mt-2 max-w-2xl text-sm leading-7 text-app-muted">
            {description}
          </p>
        )}
      </div>

      {action && <div className="shrink-0">{action}</div>}
    </div>
  );
}
