"use client";

/**
 * 表达润色选项卡（ADR-026）：3 个可选项像选择题一样点选，
 * 替换词高亮、未改动部分正常色；点击"替换"或 Tab 一键替换；
 * 翻页查看更多/返回；选中项可加入知识库。
 */

import type { PolishCardState } from "@/features/editor/use-polish";
import { wordDiff } from "@/lib/word-diff";

export function PolishCard({
  state,
  onSelect,
  onAccept,
  onNextPage,
  onPrevPage,
  onAddToKb,
  onMouseEnter,
  onMouseLeave,
}: {
  state: PolishCardState;
  onSelect: (itemId: string) => void;
  onAccept: () => void;
  onNextPage: () => void;
  onPrevPage: () => void;
  onAddToKb: () => void;
  onMouseEnter: () => void;
  onMouseLeave: () => void;
}) {
  const options = state.pages[state.pageIndex] ?? [];
  const selected = options.find((option) => option.id === state.selectedItemId) ?? null;

  return (
    <div
      data-testid="polish-card"
      className="awc-polish-card awc-scroll fixed z-40 max-h-[70vh] w-96 max-w-[calc(100vw-2rem)] overflow-y-auto rounded-lg border border-amber-200/70 bg-white/95 p-3 shadow-lg backdrop-blur-sm dark:border-amber-700/50 dark:bg-zinc-900/95"
      style={{
        top: Math.min(state.top + 6, window.innerHeight - 260),
        left: Math.max(8, Math.min(state.left, window.innerWidth - 400)),
      }}
      onMouseEnter={onMouseEnter}
      onMouseLeave={onMouseLeave}
    >
      <p className="text-xs leading-relaxed text-zinc-600 dark:text-zinc-300">
        <span className="font-medium text-amber-700 dark:text-amber-400">表达润色：</span>
        {state.fragment.note}
      </p>
      <p className="mt-1 text-[11px] text-zinc-400 dark:text-zinc-500">
        原片段：<span className="line-through">{state.fragment.anchor_text}</span>
        （第 {state.pageIndex + 1} 页，共 {state.pages.length} 页）
      </p>

      <div className="mt-2 space-y-1.5" data-testid="polish-options">
        {options.map((option) => {
          const segments = wordDiff(state.fragment.anchor_text, option.english_text);
          const isSelected = option.id === state.selectedItemId;
          return (
            <button
              key={option.id}
              type="button"
              data-testid={`polish-option-${option.id}`}
              onClick={() => onSelect(option.id)}
              className={`w-full rounded-md border p-2 text-left transition-colors ${
                isSelected
                  ? "border-amber-400 bg-amber-50 dark:border-amber-500 dark:bg-amber-950"
                  : "border-zinc-200 hover:border-zinc-400 dark:border-zinc-700 dark:hover:border-zinc-500"
              }`}
            >
              <span className="flex items-center gap-2">
                <span
                  aria-hidden="true"
                  className={`flex h-3.5 w-3.5 shrink-0 items-center justify-center rounded-full border text-[9px] ${
                    isSelected
                      ? "border-amber-500 bg-amber-500 text-white"
                      : "border-zinc-300 dark:border-zinc-600"
                  }`}
                >
                  {isSelected ? "✓" : ""}
                </span>
                <span className="text-sm text-zinc-900 dark:text-zinc-100">
                  {segments.map((segment, index) =>
                    segment.changed ? (
                      <strong
                        key={index}
                        className="font-semibold text-amber-700 dark:text-amber-400"
                      >
                        {segment.text}
                      </strong>
                    ) : (
                      <span key={index}>{segment.text}</span>
                    ),
                  )}
                </span>
                {option.previously_learned && (
                  <span className="rounded-full bg-sky-100 px-1.5 py-0.5 text-[10px] font-medium text-sky-800 dark:bg-sky-950 dark:text-sky-300">
                    曾学过
                  </span>
                )}
              </span>
              {option.chinese_meaning && (
                <span className="mt-0.5 block pl-5 text-xs text-zinc-500 dark:text-zinc-400">
                  {option.chinese_meaning}
                </span>
              )}
              {option.usage_note && (
                <span className="mt-0.5 block pl-5 text-xs text-zinc-400 dark:text-zinc-500">
                  {option.usage_note}
                </span>
              )}
            </button>
          );
        })}
      </div>

      {state.moreError && (
        <p className="mt-1.5 text-xs text-zinc-500 dark:text-zinc-400">{state.moreError}</p>
      )}

      <div className="mt-2 flex flex-wrap items-center gap-2">
        <button
          type="button"
          data-testid="polish-accept"
          disabled={!selected}
          onClick={onAccept}
          className="rounded-md bg-amber-600 px-3 py-1 text-xs font-medium text-white hover:bg-amber-700 disabled:opacity-50"
        >
          替换（Tab）
        </button>
        <button
          type="button"
          data-testid="polish-add-kb"
          disabled={!selected || state.savedToKb}
          onClick={onAddToKb}
          className="rounded-md border border-zinc-300 px-3 py-1 text-xs font-medium text-zinc-600 hover:bg-zinc-100 disabled:opacity-50 dark:border-zinc-600 dark:text-zinc-300 dark:hover:bg-zinc-800"
        >
          {state.savedToKb ? "已加入知识库" : "加入知识库"}
        </button>
        <span className="ml-auto flex items-center gap-1">
          <button
            type="button"
            data-testid="polish-prev-page"
            disabled={state.pageIndex === 0}
            onClick={onPrevPage}
            className="rounded border border-zinc-300 px-2 py-0.5 text-xs text-zinc-600 hover:bg-zinc-100 disabled:opacity-40 dark:border-zinc-600 dark:text-zinc-300 dark:hover:bg-zinc-800"
          >
            上一页
          </button>
          <button
            type="button"
            data-testid="polish-next-page"
            disabled={state.loadingMore}
            onClick={onNextPage}
            className="rounded border border-zinc-300 px-2 py-0.5 text-xs text-zinc-600 hover:bg-zinc-100 disabled:opacity-40 dark:border-zinc-600 dark:text-zinc-300 dark:hover:bg-zinc-800"
          >
            {state.loadingMore ? "加载中…" : "查看更多"}
          </button>
        </span>
      </div>
      <p className="mt-1.5 text-[10px] text-zinc-400 dark:text-zinc-500">
        点选一个表达 → 点击「替换」或按 Tab 一键替换 · Esc 关闭
      </p>
    </div>
  );
}
