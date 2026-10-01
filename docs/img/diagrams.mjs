// Source for the SVG diagrams in this folder (light + .dark.svg pairs).
// Rendered with gen.js from the Edge of Context blog-visuals skill:
//
//   node docs/img/diagrams.mjs /path/to/blog-visuals/scripts/gen.js
//
// middleware-hooks.svg and tau3-handoff.svg are copied from the A1 article assets.

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const node = (type, x, y, w, name, note, kind, extra = {}) => ({
  t: "node",
  type,
  x,
  y,
  w,
  h: note ? 104 : 72,
  kind,
  name,
  ...(note ? { note } : {}),
  ...extra,
});
const edge = (d, label, labelAt, extra = {}) => ({
  t: "edge",
  d,
  ...(label ? { label, labelAt } : {}),
  ...extra,
});
const bare = { chip: false, anchor: "start" };

export const diagrams = [
  {
    file: "overview",
    spec: {
      id: "overview",
      w: 720,
      h: 824,
      title: "How the demo fits together",
      desc: "A YAML spec file lists the model, prompt, tools, middleware and checkpointer. build_harness in harness/agent.py validates it and calls LangChain create_agent, which returns one agent. Two environments run that agent: the custom support tasks, twelve tasks each on a fresh SQLite database, and the tau-cubed-bench retail subset, eight tasks with a simulated customer. Both check the final database and write results.jsonl, traces.jsonl and run.json under reports/article-a1, which scripts/report_a1.py turns into the report tables.",
      heading: {
        title: "How the demo fits together",
        note: "One YAML spec builds one LangChain agent. Two environments run it and record the results.",
      },
      items: [
        node(
          "store",
          32,
          112,
          296,
          "harness/spec/base.yaml",
          ["model, prompt, tools,", "middleware, checkpointer"],
          "SPEC FILE",
        ),
        edge("M328 164H392"),
        node(
          "process",
          392,
          112,
          296,
          "build_harness(spec)",
          ["validates the spec, then calls", "LangChain create_agent(...)"],
          "HARNESS/AGENT.PY",
        ),
        edge("M540 216V272"),
        node(
          "focus",
          32,
          272,
          656,
          "One LangChain agent",
          [
            "gpt-6-luna via OpenRouter · 5 account tools + a policy MCP server",
            "middleware: summarization, call limit, tool retry, Jev guard, SGR",
          ],
          "FOCUS · THE HARNESS",
        ),
        edge("M180 376V448", "make a1-custom", [192, 418], bare),
        edge("M540 376V448", "make a1-tau3", [552, 418], bare),
        node(
          "process",
          32,
          448,
          296,
          "Custom support tasks",
          ["12 tasks, fresh SQLite DB each", "check: final DB vs expected"],
          "ENVS/CUSTOM",
        ),
        node(
          "external",
          392,
          448,
          296,
          "τ³-bench retail",
          ["8 tasks, simulated customer", "check: replayed DB vs expected"],
          "ENVS/TAU3",
        ),
        edge("M180 552V608"),
        edge("M540 552V608"),
        node(
          "store",
          32,
          608,
          656,
          "results.jsonl · traces.jsonl · run.json",
          [
            "per task: pass/fail, tokens, dollars, latency, every message and call",
            "scripts/report_a1.py builds reports/article-a1/README.md from them",
          ],
          "REPORTS/ARTICLE-A1/<ENV>/<SPEC>/",
        ),
      ],
      captionY: 752,
      caption: [
        "make test runs offline with fake models and needs no API key.",
        "The two environment runs make paid model calls through OpenRouter.",
      ],
    },
  },
  {
    file: "one-task",
    spec: {
      id: "one-task",
      w: 720,
      h: 800,
      title: "How one custom task runs",
      desc: "A customer message starts the run. The model node picks the next step; with Schema-Guided Reasoning it returns one typed NextStep object, either a tool call or a reply. A tool call goes to the tools node, where the Jev guard checks the three write tools before the tool reads or writes the SQLite database or looks up policy through the MCP server. The result goes back to the model. When the model replies, the run ends and a state check compares the final database with the change the task expects. The check does not read the reply text.",
      heading: {
        title: "How one custom task runs",
        note: "The model picks each step. Code runs the tools and checks the final database.",
      },
      items: [
        node(
          "external",
          32,
          112,
          296,
          "Customer message",
          ["Refund order O-1001,", "it arrived broken."],
          "TASK",
        ),
        edge("M180 216V264"),
        node(
          "process",
          32,
          264,
          296,
          "Pick the next step",
          ["SGR: one typed NextStep,", "a tool call or a reply"],
          "MODEL NODE",
        ),
        edge("M328 304H440", "tool call", [384, 304]),
        edge("M440 344H328", "result", [384, 344]),
        node(
          "process",
          440,
          264,
          248,
          "Guard, then run tool",
          ["Jev guards the 3 write tools", "policy lookups go to MCP"],
          "TOOLS NODE",
        ),
        edge("M564 368V424"),
        node(
          "store",
          440,
          424,
          248,
          "SQLite database",
          ["accounts, orders, refunds,", "addresses, preferences"],
          "STORE",
        ),
        edge("M180 368V424", "reply", [192, 400], bare),
        node("outcome", 32, 424, 296, "Answer to customer", undefined, "REPLY"),
        edge("M180 496V584", "run ends", [192, 544], bare),
        edge("M564 528V584", "final state", [576, 560], bare),
        node(
          "focus",
          32,
          584,
          656,
          "Final database vs expected change",
          [
            "pass: the right write, or no write where the task needs a refusal or a question",
            "the check does not read the reply text",
          ],
          "FOCUS · STATE CHECK",
        ),
      ],
      captionY: 728,
      caption: [
        "plain.yaml drops SGR and Jev: the model uses native tool calls instead.",
        "Code: envs/custom/run.py, envs/custom/tasks.py, envs/custom/tools.py.",
      ],
    },
  },
  {
    file: "spec-family",
    spec: {
      id: "spec-family",
      w: 720,
      h: 504,
      title: "base.yaml and the specs that extend it",
      desc: "base.yaml defines the a1-base harness: gpt-6-luna, five account tools and a policy MCP server, and five middleware components. plain.yaml extends it and drops Schema-Guided Reasoning and the Jev guard. glm-5.3-flash.yaml and mimo-v2.6-flash.yaml extend it and change only the model.",
      heading: {
        title: "base.yaml and the specs that extend it",
        note: "Each variant starts with extends: base.yaml and changes one thing.",
      },
      items: [
        node(
          "focus",
          32,
          112,
          656,
          "a1-base",
          [
            "gpt-6-luna · 5 account tools + policy MCP server",
            "middleware: summarization, call limit, tool retry, Jev guard, SGR",
          ],
          "FOCUS · BASE.YAML",
        ),
        edge("M136 216V288"),
        edge("M360 216V288"),
        edge("M584 216V288"),
        node(
          "process",
          32,
          288,
          208,
          "a1-plain",
          ["drops SGR and Jev;", "native tool calls"],
          "PLAIN.YAML",
          { nameSize: 16 },
        ),
        node(
          "process",
          256,
          288,
          208,
          "glm-5.3-flash",
          ["other model,", "Friendli endpoint"],
          "GLM-5.3-FLASH.YAML",
          { nameSize: 16 },
        ),
        node(
          "process",
          480,
          288,
          208,
          "mimo-v2.6-flash",
          ["other model,", "Xiaomi endpoint"],
          "MIMO-V2.6-FLASH.YAML",
          { nameSize: 16 },
        ),
      ],
      captionY: 432,
      caption: [
        "extends: merges dicts and replaces lists, so plain.yaml restates its middleware.",
        "harness/spec.py validates every spec. An unknown key is an error.",
      ],
    },
  },
];

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const genPath = process.argv[2];
  if (!genPath) throw new Error("usage: node docs/img/diagrams.mjs /path/to/gen.js");
  const { render } = await import(pathToFileURL(path.resolve(genPath)).href);
  const out = path.dirname(fileURLToPath(import.meta.url));
  for (const { file, spec } of diagrams) {
    fs.writeFileSync(path.join(out, `${file}.svg`), render(spec, { theme: "light" }) + "\n");
    fs.writeFileSync(path.join(out, `${file}.dark.svg`), render(spec, { theme: "dark" }) + "\n");
    console.log(`  docs/img/${file}.svg (+ .dark.svg)`);
  }
}
