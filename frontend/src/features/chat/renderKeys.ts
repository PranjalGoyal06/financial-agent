export function stableListKey(prefix: string, value: unknown, index: number): string {
  let renderedValue: string;

  try {
    renderedValue = JSON.stringify(value);
  } catch {
    renderedValue = String(value);
  }

  return `${prefix}-${renderedValue}-${index}`;
}
