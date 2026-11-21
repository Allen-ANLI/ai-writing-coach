"use client";

/**
 * 幽灵提示“表达·句式”卡（ADR-037）：展示范文生成时预提取的逐句注释
 * （与中文范文句子 1:1 对齐）。零 LLM、零额度；点击表达可加入知识库。
 * 仅供参考引导——不写入正文、不计字数、不自动插入。
 */

import { useEffect, useState } from "react";

import type { SentenceAnnotation, SentenceExpressionAnnotation } from "@/types/api";

export interface GhostInsightState {
  index: number;
  top: number;
  left: number;
}

export function GhostInsightCard({
  state,
  annotation,
  addedTexts,
  onAddExpression,
  onClose,
}: {
  state: GhostInsightState;
  annotation: SentenceAnnotation;
  addedTexts: Record<string, boolean>;
  onAddExpression: (expression: SentenceExpressionAnnotation) => Promise<void>;
  onClose: () => void;
}) {
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState<string | null>(null);

  useEffect(() => {
    const handler = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        onClose();
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [onClose]);

  const add = async (expression: SentenceExpressionAnnotation) => {
    setPending(expression.text);
    setError(null);
    try {
      await onAddExpression(expression);
    } catch {
      setError("加入知识库失败（可能已存在）。");
    } finally {
      setPending(null);
    }
  };

  return (
    <div
      data-testid="ghost-insight-card"
      className="awc-hint-card awc-scroll fixed z-40 max-h-[70vh] w-96 max-w-[calc(100vw-2rem)] overflow-y-auto rounded-lg border border-zinc-200/70 bg-white/95 p-3 shadow-lg backdrop-blur-sm dark:border-zinc-700/70 dark:bg-zinc-900/95"
      style={{
        top: Math.min(state.top + 6, window.innerHeight - 220),
        left: Math.max(8, Math.min(state.left, window.innerWidth - 400)),
      }}
    >
      <div className="flex items-center justify-between gap-2">
        <h3 className="text-[11px] font-semibold uppercase tracking-wide text-zinc-400 dark:text-zinc-500">
          表达 · 句式（第 {state.index + 1} 句）
        </h3>
        <button
          type="button"
          data-testid="ghost-insight-close"
          onClick={onClose}
          aria-label="关闭"
          className="rounded px-1.5 text-xs text-zinc-400 hover:bg-zinc-100 hover:text-zinc-600 dark:hover:bg-zinc-800 dark:hover:text-zinc-300"
        >
          ✕
        </button>
      </div>

      <div className="mt-2 space-y-1.5" data-testid="ghost-insight-expressions">
        {annotation.expressions.map((expression) => {
          const added = Boolean(addedTexts[expression.text]);
          return (
            <div
              key={expression.text}
              className="rounded-md border border-zinc-100 p-2 dark:border-zinc-800"
            >
              <div className="flex flex-wrap items-center gap-2">
                <button
                  type="button"
                  data-testid={`ghost-expression-${expression.text}`}
                  onClick={() => void add(expression)}
                  disabled={added || pending === expression.text}
                  className="rounded-md border border-emerald-300 bg-emerald-50 px-2 py-0.5 text-sm font-semibold text-emerald-800 hover:border-emerald-500 disabled:opacity-70 dark:border-emerald-700 dark:bg-emerald-950 dark:text-emerald-300"
                >
                  {expression.text}
                </button>
                <span className="text-xs text-zinc-600 dark:text-zinc-300">
                  {expression.meaning}
                </span>
                {added && (
                  <span
                    data-testid="ghost-expression-added"
                    className="rounded bg-emerald-100 px-1 text-[10px] font-medium text-emerald-700 dark:bg-emerald-900 dark:text-emerald-300"
                  >
                    已加入知识库
                  </span>
                )}
              </div>
              <p className="mt-1 text-[11px] text-zinc-400 dark:text-zinc-500">
                {expression.usage}
              </p>
            </div>
          );
        })}
      </div>

      <div className="mt-2 rounded-md bg-zinc-50 p-2 dark:bg-zinc-800" data-testid="ghost-insight-pattern">
        <p className="text-[10px] font-semibold uppercase tracking-wide text-zinc-400">
          句式 · {annotation.pattern.label}
        </p>
        <p className="mt-1 inline-block rounded bg-sky-100 px-2 py-0.5 font-mono text-[11px] font-medium text-sky-800 dark:bg-sky-950 dark:text-sky-300">
          {annotation.pattern.skeleton}
        </p>
        <p className="mt-1 text-xs leading-relaxed text-zinc-600 dark:text-zinc-300">
          {annotation.pattern.explanation}
        </p>
      </div>

      {error && (
        <p className="mt-1.5 text-xs text-red-600 dark:text-red-400" data-testid="ghost-insight-error">
          {error}
        </p>
      )}
      <p className="mt-1.5 text-[11px] text-zinc-400 dark:text-zinc-500">
        点击表达可加入知识库 · 仅供参考，不会写入正文 · Esc 关闭
      </p>
    </div>
  );
}