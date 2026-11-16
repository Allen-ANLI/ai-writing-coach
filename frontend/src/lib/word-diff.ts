/**
 * 词级 diff（ADR-026，ADR-028 修复空格丢失）：润色选项高亮显示替换词。
 * 未改动的词正常显示，新增/替换的词高亮。基于 LCS，片段很短，O(mn) 足够。
 * 分词保留词后空白，片段拼接必须精确还原 replacement（含空格），
 * 否则选项渲染会出现 "reallylike" 这类粘连。
 */

export interface DiffSegment {
  text: string;
  changed: boolean;
}

interface Token {
  word: string;
  raw: string;
}

function tokenize(text: string): Token[] {
  const tokens: Token[] = [];
  const re = /\S+\s*/g;
  let match: RegExpExecArray | null;
  while ((match = re.exec(text)) !== null) {
    tokens.push({ word: match[0].trimEnd(), raw: match[0] });
  }
  return tokens;
}

export function wordDiff(original: string, replacement: string): DiffSegment[] {
  const a = tokenize(original);
  const b = tokenize(replacement);
  const m = a.length;
  const n = b.length;
  const dp: number[][] = Array.from({ length: m + 1 }, () => new Array<number>(n + 1).fill(0));
  for (let i = m - 1; i >= 0; i -= 1) {
    for (let j = n - 1; j >= 0; j -= 1) {
      dp[i][j] = a[i].word === b[j].word ? dp[i + 1][j + 1] + 1 : Math.max(dp[i + 1][j], dp[i][j + 1]);
    }
  }
  const segments: DiffSegment[] = [];
  const push = (text: string, changed: boolean) => {
    if (text === "") {
      return;
    }
    const last = segments[segments.length - 1];
    if (last && last.changed === changed) {
      last.text += text;
    } else {
      segments.push({ text, changed });
    }
  };
  const leading = replacement.match(/^\s+/)?.[0];
  if (leading) {
    push(leading, false);
  }
  let i = 0;
  let j = 0;
  while (j < n) {
    if (i < m && a[i].word === b[j].word) {
      push(b[j].raw, false);
      i += 1;
      j += 1;
    } else if (i < m && dp[i + 1][j] >= dp[i][j + 1]) {
      i += 1; // word removed from the original
    } else {
      push(b[j].raw, true);
      j += 1;
    }
  }
  return segments;
}