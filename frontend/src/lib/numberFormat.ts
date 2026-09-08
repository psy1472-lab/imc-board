export function formatThousandUnit(value: unknown, maximumFractionDigits = 1): string {
  const num = typeof value === "number" ? value : Number(value);
  if (!num || Number.isNaN(num)) return "";

  const hasFraction = !Number.isInteger(num);
  const fractionDigits = hasFraction ? maximumFractionDigits : 0;
  const [integerPart, decimalPart = ""] = num.toFixed(fractionDigits).split(".");
  const formattedInteger = integerPart.replace(/\B(?=(\d{3})+(?!\d))/g, ",");

  if (!decimalPart || Number(decimalPart) === 0) {
    return formattedInteger;
  }

  return `${formattedInteger}.${decimalPart}`;
}
