interface Props {
  title: string;
  message?: string;
  showPipeline?: boolean;
}

const PIPELINE = [
  "npm run data:inventory",
  "npm run data:build",
  "npm run model:train",
  "npm run model:export",
];

export function EmptyState({ title, message, showPipeline }: Props) {
  return (
    <div className="mx-auto max-w-lg rounded-xl border border-line bg-ink-900 p-8 text-center">
      <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-ink-700 text-xl">
        ◎
      </div>
      <h3 className="text-base font-semibold text-slate-100">{title}</h3>
      {message && <p className="mt-2 text-sm text-slate-400">{message}</p>}
      {showPipeline && (
        <div className="mt-5 text-left">
          <p className="mb-2 text-xs uppercase tracking-wider text-slate-500">
            Run the pipeline locally
          </p>
          <pre className="overflow-x-auto rounded-lg border border-line bg-ink-950 p-3 text-xs leading-relaxed text-slate-300">
            {PIPELINE.join("\n")}
          </pre>
        </div>
      )}
    </div>
  );
}
