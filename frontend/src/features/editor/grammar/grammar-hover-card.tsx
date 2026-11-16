"use client";

/**
 * 语法反馈悬浮卡（ADR-024/026/029）：
 * 悬浮错误即直接显示修改建议；全部建议（含备选）为可点选芯片，
 * 点击"接受修改"或 Tab 替换当前选中项。拼写错误不提供详细讲解
 * （单词错误无需 LLM 讲解）；其他类别按需点击"请求详细解释"。
 */

import type { RevealedSuggestion, TeachingData } from "@/types/api";

export interface HoverCardState {
  issueId: string;
  category: string | null;
  top: number;
  left: number;
  explanation: string | null;
  suggestions: RevealedSuggestion[] | null;
  suggestionsLoading: boolean;
  selectedSuggestionId: string | null;
  teaching: TeachingData | null;
  teachingLoading: boolean;
  teachingError: string | null;
  /** ADR-034: ephemeral live finding — pre-revealed, no DB teaching available. */
  live?: boolean;
}

export function GrammarHoverCard({
  state,
  onSelectSuggestion,
  onAccept,
  onIgnore,
  onRequestTeaching,
  onMouseEnter,
  onMouseLeave,
}: {
  state: HoverCardState;
  onSelectSuggestion: (suggestionId: string) => void;
  onAccept: () => void;
  onIgnore: () => void;
  onRequestTeaching: () => void;
  onMouseEnter: () => void;
  onMouseLeave: () => void;
}) {
  const suggestions = state.suggestions ?? [];
  const selected =
    suggestions.find((s) => s.id === state.selectedSuggestionId) ??
    suggestions.find((s) => s.is_recommended) ??
    suggestions[0] ??
    null;
  const isSpelling = state.category === "spelling";

  return (
    <div
      data-testid="grammar-hover-card"
      className="awc-hint-card awc-scroll fixed z-40 max-h-[70vh] w-96 max-w-[calc(100vw-2rem)] overflow-y-auto rounded-lg border border-zinc-200/70 bg-white/95 p-3 shadow-lg backdrop-blur-sm dark:border-zinc-700/70 dark:bg-zinc-900/95"
      style={{
        top: Math.min(state.top + 6, window.innerHeight - 200),
        left: Math.max(8, Math.min(state.left, window.innerWidth - 400)),
      }}
      onMouseEnter={onMouseEnter}
      onMouseLeave={onMouseLeave}
    >
      <p className="text-xs leading-relaxed text-zinc-700 dark:text-zinc-300">
        {state.explanation ?? "此处可能存在问题。"}
      </p>

      <div className="mt-2">
        {state.suggestionsLoading && (
          <p className="text-xs text-zinc-400" data-testid="suggestions-loading">
            正在加载修改建议…
          </p>
        )}
        {suggestions.length > 0 && (
          <div className="flex flex-wrap items-center gap-1.5" data-testid="suggestion-options">
            {suggestions.map((suggestion) => {
              const isSelected = selected?.id === suggestion.id;
              return (
                <button
                  key={suggestion.id}
                  type="button"
                  data-testid={`suggestion-option-${suggestion.id}`}
                  onClick={() => onSelectSuggestion(suggestion.id)}
                  className={`rounded-md border px-2 py-0.5 text-sm font-semibold transition-colors ${
                    isSelected
                      ? "border-emerald-500 bg-emerald-50 text-emerald-800 dark:border-emerald-500 dark:bg-emerald-950 dark:text-emerald-300"
                      : "border-zinc-200 text-zinc-600 hover:border-zinc-400 dark:border-zinc-700 dark:text-zinc-300 dark:hover:border-zinc-500"
                  }`}
                >
                  {isSelected ? (
                    <span data-testid="revealed-answer">{suggestion.suggested_text}</span>
                  ) : (
                    suggestion.suggested_text
                  )}
                  {suggestion.is_recommended && (
                    <span className="ml-1 rounded bg-emerald-100 px-1 text-[10px] font-medium text-emerald-700 dark:bg-emerald-900 dark:text-emerald-300">
                      推荐
                    </span>
                  )}
                </button>
              );
            })}
          </div>
        )}
        {selected && (
          <div className="mt-1.5 flex flex-wrap items-center gap-2">
            <button
              type="button"
              data-testid="accept-correction"
              onClick={onAccept}
              className="rounded-md bg-emerald-600 px-2 py-0.5 text-xs font-medium text-white hover:bg-emerald-700"
            >
              接受修改
            </button>
            <button
              type="button"
              data-testid="ignore-issue"
              onClick={onIgnore}
              className="rounded-md border border-zinc-300 px-2 py-0.5 text-xs text-zinc-500 hover:bg-zinc-100 dark:border-zinc-600 dark:text-zinc-400 dark:hover:bg-zinc-800"
            >
              忽略
            </button>
          </div>
        )}
        {selected && (
          <p
            data-testid="tab-instruction"
            className="mt-1.5 text-[11px] font-medium text-zinc-500 dark:text-zinc-400"
          >
            点选一个修改 → 按{" "}
            <kbd className="rounded border border-zinc-300 px-1 dark:border-zinc-600">Tab</kbd>{" "}
            替换原文 · Esc 关闭
          </p>
        )}
      </div>

      {!isSpelling && !state.live && (
        <div className="mt-2 border-t border-zinc-100 pt-2 dark:border-zinc-800">
          <div className="flex items-center justify-between gap-2">
            <h3 className="text-[11px] font-semibold uppercase tracking-wide text-zinc-400 dark:text-zinc-500">
              详细讲解
            </h3>
            {!state.teaching && !state.teachingLoading && (
              <button
                type="button"
                data-testid="request-teaching"
                onClick={onRequestTeaching}
                className="rounded-md bg-zinc-900 px-2.5 py-1 text-[11px] font-medium text-white hover:bg-zinc-700 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-300"
              >
                请求详细解释
              </button>
            )}
          </div>
          {state.teachingLoading && (
            <p className="mt-1 text-xs text-zinc-400" data-testid="teaching-loading">
              正在结合你的句子生成讲解…
            </p>
          )}
          {state.teachingError && (
            <div className="mt-1" data-testid="teaching-error">
              <p className="text-xs text-red-600 dark:text-red-400">{state.teachingError}</p>
              <button
                type="button"
                data-testid="retry-teaching"
                onClick={onRequestTeaching}
                className="mt-1 rounded border border-zinc-300 px-2 py-0.5 text-xs text-zinc-600 hover:bg-zinc-100 dark:border-zinc-600 dark:text-zinc-300 dark:hover:bg-zinc-800"
              >
                重试
              </button>
            </div>
          )}
          {state.teaching && (
            <div className="mt-1.5 space-y-2" data-testid="teaching-content">
              <p className="text-xs font-semibold text-zinc-800 dark:text-zinc-200">
                {state.teaching.title}
              </p>
              {/* 先：语法知识点（可视化） */}
              <div className="rounded-md bg-zinc-50 p-2 dark:bg-zinc-800">
                <p className="text-[10px] font-semibold uppercase tracking-wide text-zinc-400">
                  语法知识点
                </p>
                <p className="mt-1 text-xs leading-relaxed text-zinc-600 dark:text-zinc-300">
                  {state.teaching.knowledge_point.explanation}
                </p>
                <p className="mt-1.5 inline-block rounded bg-sky-100 px-2 py-0.5 font-mono text-[11px] font-medium text-sky-800 dark:bg-sky-950 dark:text-sky-300">
                  {state.teaching.knowledge_point.pattern}
                </p>
                <div className="mt-1.5 space-y-1">
                  {state.teaching.knowledge_point.examples.map((example, index) => (
                    <div key={index} className="text-xs">
                      <p>
                        <span className="text-red-600 line-through dark:text-red-400">
                          {example.wrong}
                        </span>
                        <span className="mx-1 text-zinc-400">→</span>
                        <span className="font-medium text-emerald-700 dark:text-emerald-400">
                          {example.correct}
                        </span>
                      </p>
                      <p className="text-[11px] text-zinc-400 dark:text-zinc-500">{example.note}</p>
                    </div>
                  ))}
                </div>
              </div>
              {/* 后：本句为什么这样改（简短） */}
              <div>
                <p className="text-[10px] font-semibold uppercase tracking-wide text-zinc-400">
                  本句为什么这样改
                </p>
                <p className="mt-0.5 text-xs leading-relaxed text-zinc-600 dark:text-zinc-300">
                  {state.teaching.sentence_reason}
                </p>
                <p className="mt-1 text-xs text-zinc-600 dark:text-zinc-300">
                  <span className="font-medium text-zinc-700 dark:text-zinc-200">推荐写法：</span>
                  <span className="font-semibold text-emerald-700 dark:text-emerald-300">
                    {state.teaching.recommended_correction}
                  </span>
                </p>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}