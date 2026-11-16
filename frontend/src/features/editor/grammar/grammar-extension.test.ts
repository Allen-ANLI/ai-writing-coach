import { describe, expect, it } from "vitest";

import type { IssueData } from "@/types/api";

import { mergeIssueStates, type GrammarIssueState } from "./grammar-extension";

function state(
  id: string,
  ruleId: string,
  from: number,
  to: number,
  live = false,
): GrammarIssueState {
  const issue: IssueData = {
    id,
    category: "grammar",
    sub_category: null,
    source: "rule_engine",
    rule_id: ruleId,
    severity: "high",
    source_server_revision: 2,
    essay_version_id: null,
    start_offset: from,
    end_offset: to,
    offset_unit: "unicode_codepoint",
    anchor_text: "x",
    short_explanation: null,
    status: "detected",
    suggestions: [],
    live,
  };
  return { issue, from, to, revealed: null };
}

describe("mergeIssueStates (ADR-025/034)", () => {
  it("full merge replaces in-span findings and keeps outside ones", () => {
    const previous = [state("a", "R1", 0, 5), state("b", "R2", 10, 15), state("c", "R3", 20, 25)];
    const next = mergeIssueStates(previous, {
      start: 10,
      end: 15,
      issues: [state("d", "R2", 10, 15)],
    });
    expect(next.map((i) => i.issue.id)).toEqual(["a", "c", "d"]);
  });

  it("live merge keeps persisted in-span findings and swaps live ones", () => {
    const previous = [state("p", "R1", 0, 5, false), state("l", "R2", 0, 5, true)];
    const next = mergeIssueStates(previous, {
      start: 0,
      end: 5,
      issues: [state("l2", "R3", 0, 5, true)],
      live: true,
    });
    expect(next.map((i) => i.issue.id)).toEqual(["p", "l2"]);
  });

  it("live merge dedupes a live finding against an identical persisted one", () => {
    const previous = [state("p", "R1", 0, 5, false)];
    const next = mergeIssueStates(previous, {
      start: 0,
      end: 5,
      issues: [state("l", "R1", 0, 5, true)],
      live: true,
    });
    expect(next.map((i) => i.issue.id)).toEqual(["p"]);
  });

  it("live merge keeps a live finding with a different rule/span", () => {
    const previous = [state("p", "R1", 0, 5, false)];
    const next = mergeIssueStates(previous, {
      start: 0,
      end: 10,
      issues: [state("l", "R2", 6, 9, true)],
      live: true,
    });
    expect(next.map((i) => i.issue.id)).toEqual(["p", "l"]);
  });

  it("full merge clears live findings in the span (persisted replaces them)", () => {
    const previous = [state("l", "R1", 0, 5, true), state("out", "R2", 20, 25, true)];
    const next = mergeIssueStates(previous, {
      start: 0,
      end: 5,
      issues: [state("p", "R1", 0, 5, false)],
    });
    expect(next.map((i) => i.issue.id).sort()).toEqual(["out", "p"]);
  });
});