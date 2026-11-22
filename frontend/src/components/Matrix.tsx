import { cn } from "@/lib/utils";

/** Renders a matrix with bracket styling. `augmentAt` draws the vertical bar of [A|B]. */
export function Matrix({ data, cols, augment = false, highlight, className, light = false }: {
  data: string[][]; cols?: string[]; augment?: boolean; highlight?: [number, number] | null; className?: string; light?: boolean;
}) {
  if (!data.length || !data[0].length) return <span className="text-sm text-slate-500">(empty)</span>;
  const n = data[0].length;
  return (
    <div className={cn("inline-block", className)}>
      {cols && (
        <div className="mb-1 flex px-3 font-mono text-[11px] text-slate-400">
          {cols.map((c, i) => <span key={i} className={cn("w-12 text-center", augment && i === cols.length - 1 && "ml-2")}>{c}</span>)}
        </div>
      )}
      <div className={cn("flex items-stretch font-mono text-sm", light ? "text-white" : "text-navy-900 dark:text-slate-100")}>
        <div className={cn("w-2 rounded-l-md border-y-2 border-l-2 border-navy-900 dark:border-slate-300", light && "!border-slate-200")} />
        <div className="py-1">
          {data.map((row, i) => (
            <div key={i} className="flex">
              {row.map((v, j) => (
                <span key={j} className={cn("w-12 px-1 py-0.5 text-center",
                  augment && j === n - 1 && "ml-2 border-l-2 border-dashed border-cyan2 pl-2",
                  highlight && highlight[0] === i && highlight[1] === j && "rounded bg-cyan2-100 font-bold text-cyan-900")}>{v}</span>
              ))}
            </div>
          ))}
        </div>
        <div className={cn("w-2 rounded-r-md border-y-2 border-r-2 border-navy-900 dark:border-slate-300", light && "!border-slate-200")} />
      </div>
    </div>
  );
}

export function Vector({ data, label }: { data: string[]; label?: string[] }) {
  return <Matrix data={data.map((v) => [v])} className="align-top" cols={undefined} />;
}
