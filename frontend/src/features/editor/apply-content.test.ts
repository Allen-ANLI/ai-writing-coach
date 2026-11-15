import { describe, expect, it } from "vitest";
import { Node as ProseMirrorNode, Schema } from "@tiptap/pm/model";
import { EditorState, Plugin, PluginKey } from "@tiptap/pm/state";
import { Decoration, DecorationSet } from "@tiptap/pm/view";

import { computeContentDiff } from "./apply-content";

const schema = new Schema({
  nodes: {
    doc: { content: "block+" },
    paragraph: { group: "block", content: "inline*" },
    text: { group: "inline" },
  },
});

function doc(...paragraphs: string[]): ProseMirrorNode {
  return schema.node(
    "doc",
    null,
    paragraphs.map((text) =>
      schema.node("paragraph", null, text ? [schema.text(text)] : []),
    ),
  );
}

/** Plugin whose inline decorations must survive minimal-diff transactions. */
function decorationPlugin(from: number, to: number) {
  const key = new PluginKey<DecorationSet>("testDecorations");
  const plugin = new Plugin<DecorationSet>({
    key,
    state: {
      init: (_, state) =>
        DecorationSet.create(state.doc, [Decoration.inline(from, to, { class: "mark" })]),
      apply: (tr, old) => old.map(tr.mapping, tr.doc),
    },
    props: {
      decorations: (state) => key.getState(state),
    },
  });
  return { key, plugin };
}

describe("computeContentDiff", () => {
  it("returns null for identical documents", () => {
    expect(computeContentDiff(doc("He go to school."), doc("He go to school."))).toBeNull();
  });

  it("covers only the replaced word", () => {
    const oldDoc = doc("He go to school.");
    const newDoc = doc("He went to school.");
    const diff = computeContentDiff(oldDoc, newDoc);
    expect(diff).not.toBeNull();
    // paragraph open token at 0; "He " = 3 → "go" spans [4, 6)
    expect(diff!.from).toBe(4);
    expect(diff!.to).toBe(6);
    const tr = EditorState.create({ doc: oldDoc }).tr;
    const result = tr.replaceWith(diff!.from, diff!.to, diff!.slice.content).doc;
    expect(result.textContent).toBe("He went to school.");
  });

  it("keeps decorations outside the changed range (ADR-027 regression)", () => {
    const oldDoc = doc("He go to school.", "She like apples.");
    const newDoc = doc("He goes to school.", "She like apples.");
    // paragraph 1 nodeSize = 16 + 2 = 18; paragraph 2 content starts at 19;
    // "She " = 4 → "like" spans [23, 27)
    const { key, plugin } = decorationPlugin(23, 27);
    const state = EditorState.create({ doc: oldDoc, plugins: [plugin] });
    const diff = computeContentDiff(oldDoc, newDoc);
    expect(diff).not.toBeNull();
    const next = state.apply(
      state.tr.replaceWith(diff!.from, diff!.to, diff!.slice.content),
    );
    const marks = key.getState(next)!.find();
    expect(marks).toHaveLength(1);
    // "go" → "goes" lengthens paragraph 1 by 2: the underline shifts, survives.
    expect(marks[0].from).toBe(25);
    expect(marks[0].to).toBe(29);
    expect(next.doc.textContent).toBe("He goes to school.She like apples.");
  });

  it("a full-document replacement would collapse the same decoration", () => {
    const oldDoc = doc("He go to school.", "She like apples.");
    const newDoc = doc("He goes to school.", "She like apples.");
    const { key, plugin } = decorationPlugin(23, 27);
    const state = EditorState.create({ doc: oldDoc, plugins: [plugin] });
    const next = state.apply(
      state.tr.replaceWith(0, oldDoc.content.size, newDoc.content),
    );
    expect(key.getState(next)!.find()).toHaveLength(0);
  });

  it("handles multi-paragraph edits without touching other paragraphs", () => {
    const oldDoc = doc("First stays.", "Second changes here.", "Third stays.");
    const newDoc = doc("First stays.", "Second changed here.", "Third stays.");
    const diff = computeContentDiff(oldDoc, newDoc);
    expect(diff).not.toBeNull();
    const state = EditorState.create({ doc: oldDoc });
    const result = state.tr.replaceWith(diff!.from, diff!.to, diff!.slice.content).doc;
    expect(result.child(0).textContent).toBe("First stays.");
    expect(result.child(1).textContent).toBe("Second changed here.");
    expect(result.child(2).textContent).toBe("Third stays.");
  });

  it("handles append at the end", () => {
    const oldDoc = doc("Hello");
    const newDoc = doc("Hello world");
    const diff = computeContentDiff(oldDoc, newDoc);
    expect(diff).not.toBeNull();
    const state = EditorState.create({ doc: oldDoc });
    const result = state.tr.replaceWith(diff!.from, diff!.to, diff!.slice.content).doc;
    expect(result.textContent).toBe("Hello world");
  });
});