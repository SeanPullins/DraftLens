import { scoreStyle } from "../lib/scoring";

interface Props {
  score: number;
  size?: "sm" | "md" | "lg";
}

const SIZES = {
  sm: "h-7 w-7 text-xs",
  md: "h-10 w-10 text-sm",
  lg: "h-16 w-16 text-2xl",
};

export function ScoreBadge({ score, size = "md" }: Props) {
  const s = scoreStyle(score);
  return (
    <span
      className={`inline-flex items-center justify-center rounded-lg font-bold tabular-nums ring-1 ${s.bg} ${s.text} ${s.ring} ${SIZES[size]}`}
      title={`DraftLens Score ${score}`}
    >
      {Math.round(score)}
    </span>
  );
}
