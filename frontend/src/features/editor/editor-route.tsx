"use client";

import { useParams } from "next/navigation";

import { WritingEditor } from "@/features/editor/writing-editor";

/** Reads the dynamic route param; must render inside <Suspense> (Next 16). */
export function EditorRoute() {
  const params = useParams<{ id: string }>();
  return <WritingEditor key={params.id} essayId={params.id} />;
}
