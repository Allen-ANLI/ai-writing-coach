/**
 * Generates src/types/generated.ts from contracts/openapi.yaml (the single
 * source of truth). The YAML package resolves anchors/aliases natively, which
 * is the prerequisite noted in the development plan (tracked issue 3).
 *
 * Only the contract's named component schemas are generated; response bodies
 * the contract leaves open stay hand-mirrored in src/types/api.ts.
 *
 * Run: npm run generate:api
 */

import { readFileSync, writeFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { parse } from "yaml";

const here = path.dirname(fileURLToPath(import.meta.url));
const contractPath = path.resolve(here, "../../contracts/openapi.yaml");
const outPath = path.resolve(here, "../src/types/generated.ts");

const spec = parse(readFileSync(contractPath, "utf8"));
const schemas = spec.components?.schemas ?? {};

function refName(ref) {
  return ref.split("/").pop();
}

function tsType(schema, depth = 0) {
  if (!schema || typeof schema !== "object") {
    return "unknown";
  }
  if (schema.$ref) {
    return refName(schema.$ref);
  }
  if (schema.const !== undefined) {
    return JSON.stringify(schema.const);
  }
  if (Array.isArray(schema.enum)) {
    return schema.enum.map((value) => JSON.stringify(value)).join(" | ");
  }
  if (Array.isArray(schema.anyOf)) {
    const nonNull = schema.anyOf.filter((branch) => branch.type !== "null");
    const hasNull = nonNull.length !== schema.anyOf.length;
    const inner = nonNull.map((branch) => tsType(branch, depth)).join(" | ") || "unknown";
    return hasNull ? `${inner} | null` : inner;
  }
  if (Array.isArray(schema.type)) {
    return schema.type.map((t) => (t === "null" ? "null" : tsType({ ...schema, type: t }, depth))).join(" | ");
  }
  switch (schema.type) {
    case "string":
      return "string";
    case "integer":
    case "number":
      return "number";
    case "boolean":
      return "boolean";
    case "array":
      return `${tsType(schema.items, depth)}[]`;
    case "object":
      return objectType(schema, depth);
    default:
      return "unknown";
  }
}

function objectType(schema, depth) {
  const properties = schema.properties ?? {};
  const names = Object.keys(properties);
  if (names.length === 0) {
    return "Record<string, unknown>";
  }
  const required = new Set(schema.required ?? []);
  const pad = "  ".repeat(depth + 1);
  const closePad = "  ".repeat(depth);
  const lines = names.map((name) => {
    const optional = required.has(name) ? "" : "?";
    return `${pad}${JSON.stringify(name)}${optional}: ${tsType(properties[name], depth + 1)};`;
  });
  return `{\n${lines.join("\n")}\n${closePad}}`;
}

const blocks = Object.entries(schemas).map(([name, schema]) => {
  if (schema.type === "object" && schema.properties && Object.keys(schema.properties).length > 0) {
    const required = new Set(schema.required ?? []);
    const lines = Object.entries(schema.properties).map(([prop, sub]) => {
      const optional = required.has(prop) ? "" : "?";
      return `  ${JSON.stringify(prop)}${optional}: ${tsType(sub, 1)};`;
    });
    return `export interface ${name} {\n${lines.join("\n")}\n}`;
  }
  return `export type ${name} = ${tsType(schema)};`;
});

const header = `// AUTO-GENERATED from contracts/openapi.yaml (info.version ${spec.info.version}).
// Do not edit by hand: run \`npm run generate:api\` after contract changes.
// Open response bodies the contract does not define are mirrored in ./api.ts.

`;

writeFileSync(outPath, header + blocks.join("\n\n") + "\n", "utf8");
console.log(`generated ${blocks.length} types -> ${path.relative(process.cwd(), outPath)}`);
