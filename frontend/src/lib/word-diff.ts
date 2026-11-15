/**
 * 词级 diff（ADR-026）：润色选项高亮显示替换词。
 * 未改动的词正常显示，新增/替换的词高亮。基于 LCS，片段很短，O(mn) 足够。
 */

export interface DiffSegment {
  text: string;
  changed: boolean;
}

export function wordDiff(original: string, replacement: string): DiffSegment[] {
  const a = original.split(/\s+/).filter(Boolean);
  const b = replacement.split(/\s+/).filter(Boolean);
  const m = a.length;
  const n = b.length;
  const dp: number[][] = Array.from({ length: m + 1 }, () => new Array<number>(n + 1).fill(0));
  for (let i = m - 1; i >= 0; i -= 1) {
    for (let j = n - 1; j >= 0; j -= 1) {
      dp[i][j] = a[i] === b[j] ? dp[i + 1][j + 1] + 1 : Math.max(dp[i + 1][j], dp[i][j + 1]);
    }
  }
  const segments: DiffSegment[] = [];
  const push = (text: string, changed: boolean) => {
    const last = segments[segments.length - 1];
    if (last && last.changed === changed) {
      last.text += ` ${text}`;
    } else {
      segments.push({ text, changed });
    }
  };
  let i = 0;
  let j = 0;
  while (j < n) {
    if (i < m && a[i] === b[j]) {
      push(b[j], false);
      i += 1;
      j += 1;
    } else if (i < m && dp[i + 1][j] >= dp[i][j + 1]) {
      i += 1; // word removed from the original
    } else {
      push(b[j], true);
      j += 1;
    }
  }
  return segments;
}
