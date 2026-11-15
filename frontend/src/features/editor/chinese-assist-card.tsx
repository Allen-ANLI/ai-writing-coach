"use client";

/**
 * 中译英表达选项卡（ADR-027）：输入中文即自动弹出，无需悬浮/按钮。
 * 与表达润色卡一致的交互：点选、Tab/点击替换、翻页查看更多、加入知识库。
 */

import type { SuggestionItemData } from "@/types/api";

export interface AssistPage {
  suggestionId: string;
  items: SuggestionItemData[];
}

export interface AssistCardState {
  runKey: string;
  from: number;
  to: number;
  chineseText: string;
  top: number;
  left: number;
  pages: AssistPage[];
  pageIndex: number;
  selectedItemId: string | null;
  loading: boolean;
  loadingMore: boolean;
  error: string | null;
  moreError: string | null;
  savedToKb: boolean;
}

const REGISTER_LABELS: Record<string, string> = {
  formal: "正式",
  neutral: "中性",
  informal: "口语",
};

export function ChineseAssistCard({
  state,
  onSelect,
  onAccept,
  onNextPage,
  onPrevPage,
  onAddToKb,
  onClose,
  onRetry,
}: {
  state: AssistCardState;
  onSelect: (itemId: string) => void;
  onAccept: () => void;
  onNextPage: () => void;
  onPrevPage: () => void;
  onAddToKb: () => void;
  onClose: () => void;
  onRetry: () => void;
}) {
  const page = state.pages[state.pageIndex];
  const options = page?.items ?? [];
  const selected = options.find((option) => option.id === state.selectedItemId) ?? null;

  return (
    <div
      data-testid="expression-assist"
      className="awc-scroll fixed z-40 max-h-[70vh] w-96 max-w-[calc(100vw-2rem)] overflow-y-auto rounded-lg border border-sky-200/70 bg-white/95 p-3 shadow-lg backdrop-blur-sm dark:border-sky-700/50 dark:bg-zinc-900/95"
      style={{
        top: Math.min(state.top, window.innerHeight - 260),
        left: Math.max(8, Math.min(state.left, window.innerWidth - 400)),
      }}
    >
      <div className="flex items-center justify-between gap-2">
        <p className="text-xs font-semibold text-sky-700 dark:text-sky-400">
          中译英 · 结合句子推荐表达
        </p>
        <button
          type="button"
          aria-label="关闭表达辅助"
          data-testid="close-expression-assist"
          onClick={onClose}
          className="rounded px-1.5 text-zinc-400 hover:bg-zinc-100 hover:text-zinc-700 dark:hover:bg-zinc-800"
        >
          ×
        </button>
      </div>
      <p className="mt-1 text-[11px] text-zinc-500 dark:text-zinc-400">
        原文：<span className="font-medium text-zinc-700 dark:text-zinc-200">{state.chineseText}</span>
        {state.pages.length > 0 && (
          <span className="ml-1 text-zinc-400 dark:text-zinc-500">
            （第 {state.pageIndex + 1} 页，共 {state.pages.length} 页）
          </span>
        )}
      </p>

      {state.loading && (
        <p role="status" className="mt-2 text-xs text-zinc-500 dark:text-zinc-400">
          正在结合整句推荐表达…
        </p>
      )}

      {state.error && !state.loading && (
        <div className="mt-2">
          <p role="alert" className="text-xs text-red-600 dark:text-red-400">
            {state.error}
          </p>
          <button
            type="button"
            data-testid="assist-retry"
            onClick={onRetry}
            className="mt-1.5 rounded-md border border-zinc-300 px-2.5 py-1 text-xs font-medium text-zinc-600 hover:bg-zinc-100 dark:border-zinc-600 dark:text-zinc-300 dark:hover:bg-zinc-800"
          >
            重试
          </button>
        </div>
      )}

      {options.length > 0 && (
        <div className="mt-2 space-y-1.5" data-testid="expression-candidates">
          {options.map((option) => {
            const isSelected = option.id === state.selectedItemId;
            return (
              <button
                key={option.id}
                type="button"
                data-testid={`expression-item-${option.id}`}
                onClick={() => onSelect(option.id)}
                className={`w-full rounded-md border p-2 text-left transition-colors ${
                  isSelected
                    ? "border-sky-400 bg-sky-50 dark:border-sky-500 dark:bg-sky-950"
                    : "border-zinc-200 hover:border-zinc-400 dark:border-zinc-700 dark:hover:border-zinc-500"
                }`}
              >
                <span className="flex items-center gap-2">
                  <span
                    aria-hidden="true"
                    className={`flex h-3.5 w-3.5 shrink-0 items-center justify-center rounded-full border text-[9px] ${
                      isSelected
                        ? "border-sky-500 bg-sky-500 text-white"
                        : "border-zinc-300 dark:border-zinc-600"
                    }`}
                  >
                    {isSelected ? "✓" : ""}
                  </span>
                  <span className="text-sm font-medium text-zinc-900 dark:text-zinc-100">
                    {option.english_text}
                  </span>
                  {option.previously_learned && (
                    <span
                      data-testid="previously-learned-badge"
                      className="rounded-full bg-sky-100 px-1.5 py-0.5 text-[10px] font-medium text-sky-800 dark:bg-sky-950 dark:text-sky-300"
                    >
                      曾学过
                    </span>
                  )}
                  {option.register && REGISTER_LABELS[option.register] && (
                    <span className="rounded-full bg-zinc-100 px-1.5 py-0.5 text-[10px] text-zinc-500 dark:bg-zinc-800 dark:text-zinc-400">
                      {REGISTER_LABELS[option.register]}
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
      )}

      {state.moreError && (
        <p className="mt-1.5 text-xs text-zinc-500 dark:text-zinc-400">{state.moreError}</p>
      )}

      {!state.loading && !state.error && options.length > 0 && (
        <div className="mt-2 flex flex-wrap items-center gap-2">
          <button
            type="button"
            data-testid="assist-accept"
            disabled={!selected}
            onClick={onAccept}
            className="rounded-md bg-sky-600 px-3 py-1 text-xs font-medium text-white hover:bg-sky-700 disabled:opacity-50"
          >
            替换（Tab）
          </button>
          <button
            type="button"
            data-testid="assist-add-kb"
            disabled={!selected || state.savedToKb}
            onClick={onAddToKb}
            className="rounded-md border border-zinc-300 px-3 py-1 text-xs font-medium text-zinc-600 hover:bg-zinc-100 disabled:opacity-50 dark:border-zinc-600 dark:text-zinc-300 dark:hover:bg-zinc-800"
          >
            {state.savedToKb ? "已加入知识库" : "加入知识库"}
          </button>
          <span className="ml-auto flex items-center gap-1">
            <button
              type="button"
              data-testid="assist-prev-page"
              disabled={state.pageIndex === 0}
              onClick={onPrevPage}
              className="rounded border border-zinc-300 px-2 py-0.5 text-xs text-zinc-600 hover:bg-zinc-100 disabled:opacity-40 dark:border-zinc-600 dark:text-zinc-300 dark:hover:bg-zinc-800"
            >
              上一页
            </button>
            <button
              type="button"
              data-testid="assist-next-page"
              disabled={state.loadingMore}
              onClick={onNextPage}
              className="rounded border border-zinc-300 px-2 py-0.5 text-xs text-zinc-600 hover:bg-zinc-100 disabled:opacity-40 dark:border-zinc-600 dark:text-zinc-300 dark:hover:bg-zinc-800"
            >
              {state.loadingMore ? "加载中…" : "查看更多"}
            </button>
          </span>
        </div>
      )}
      <p className="mt-1.5 text-[10px] text-zinc-400 dark:text-zinc-500">
        点选一个表达 → 点击「替换」或按 Tab 一键替换 · Esc 关闭
      </p>
    </div>
  );
}