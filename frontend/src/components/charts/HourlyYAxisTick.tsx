type TickProps = {
  x?: string | number;
  y?: string | number;
  payload?: { value: number };
  fill?: string;
  text?: string;
  orientation?: "left" | "right";
};

export function HourlyYAxisTick({
  x = 0,
  y = 0,
  payload,
  fill = "#9fb0d0",
  text,
  orientation = "left",
}: TickProps) {
  const label = text ?? (payload ? String(payload.value) : "");
  if (!label) return null;

  const isRight = orientation === "right";
  const xPos = typeof x === "number" ? x : Number(x);
  const yPos = typeof y === "number" ? y : Number(y);

  return (
    <text
      x={xPos}
      y={yPos}
      dy={4}
      dx={isRight ? 6 : -4}
      textAnchor={isRight ? "start" : "end"}
      fill={fill}
      fontSize={11}
    >
      {label}
    </text>
  );
}
