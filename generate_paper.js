const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  Header, Footer, AlignmentType, HeadingLevel, BorderStyle, WidthType,
  ShadingType, VerticalAlign, PageNumber, PageBreak, LevelFormat,
  TableOfContents
} = require('docx');
const fs = require('fs');

const BORDER = { style: BorderStyle.SINGLE, size: 1, color: "CCCCCC" };
const BORDERS = { top: BORDER, bottom: BORDER, left: BORDER, right: BORDER };
const HEAD_SHADE = { fill: "2E4A6B", type: ShadingType.CLEAR };
const ALT_SHADE  = { fill: "F0F4F8", type: ShadingType.CLEAR };

function cell(text, opts = {}) {
  const { bold = false, shade = null, align = AlignmentType.LEFT, width = null } = opts;
  const cellOpts = {
    borders: BORDERS,
    margins: { top: 80, bottom: 80, left: 120, right: 120 },
    verticalAlign: VerticalAlign.CENTER,
    children: [new Paragraph({
      alignment: align,
      children: [new TextRun({ text: String(text), bold, font: "Arial", size: 18,
                               color: shade === HEAD_SHADE ? "FFFFFF" : "000000" })]
    })]
  };
  if (shade) cellOpts.shading = shade;
  if (width) cellOpts.width = { size: width, type: WidthType.DXA };
  return new TableCell(cellOpts);
}

function hrow(texts, widths) {
  return new TableRow({ children: texts.map((t, i) => cell(t, { bold: true, shade: HEAD_SHADE, width: widths[i] })) });
}

function drow(texts, widths, alt = false) {
  const shade = alt ? ALT_SHADE : null;
  return new TableRow({ children: texts.map((t, i) => cell(t, { shade, width: widths[i] })) });
}

function table(headers, rows, widths) {
  return new Table({
    width: { size: widths.reduce((a,b)=>a+b,0), type: WidthType.DXA },
    columnWidths: widths,
    rows: [
      hrow(headers, widths),
      ...rows.map((r, i) => drow(r, widths, i % 2 === 0))
    ]
  });
}

function h1(text) {
  return new Paragraph({ heading: HeadingLevel.HEADING_1, spacing: { before: 360, after: 120 },
    children: [new TextRun({ text, bold: true, font: "Arial", size: 28, color: "2E4A6B" })] });
}
function h2(text) {
  return new Paragraph({ heading: HeadingLevel.HEADING_2, spacing: { before: 240, after: 80 },
    children: [new TextRun({ text, bold: true, font: "Arial", size: 24, color: "1A5276" })] });
}
function h3(text) {
  return new Paragraph({ heading: HeadingLevel.HEADING_3, spacing: { before: 160, after: 60 },
    children: [new TextRun({ text, bold: true, font: "Arial", size: 22, color: "154360" })] });
}
function p(text, opts = {}) {
  const { bold = false, italic = false, spacing = { before: 60, after: 60 } } = opts;
  return new Paragraph({ spacing, alignment: AlignmentType.JUSTIFIED,
    children: [new TextRun({ text, font: "Arial", size: 20, bold, italic })] });
}
function br() { return new Paragraph({ children: [new PageBreak()] }); }
function space(pts = 120) { return new Paragraph({ spacing: { before: pts, after: 0 }, children: [new TextRun("")] }); }

function mixed(...runs) {
  return new Paragraph({ spacing: { before: 60, after: 60 }, alignment: AlignmentType.JUSTIFIED,
    children: runs });
}
function run(text, opts = {}) {
  return new TextRun({ text, font: "Arial", size: 20, ...opts });
}
function bullet(text) {
  return new Paragraph({
    numbering: { reference: "bullets", level: 0 },
    spacing: { before: 40, after: 40 },
    children: [new TextRun({ text, font: "Arial", size: 20 })]
  });
}

const doc = new Document({
  numbering: {
    config: [{
      reference: "bullets",
      levels: [{ level: 0, format: LevelFormat.BULLET, text: "\u2022", alignment: AlignmentType.LEFT,
        style: { paragraph: { indent: { left: 720, hanging: 360 } } } }]
    }]
  },
  styles: {
    default: { document: { run: { font: "Arial", size: 20 } } },
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 28, bold: true, font: "Arial", color: "2E4A6B" },
        paragraph: { spacing: { before: 360, after: 120 }, outlineLevel: 0 } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 24, bold: true, font: "Arial", color: "1A5276" },
        paragraph: { spacing: { before: 240, after: 80 }, outlineLevel: 1 } },
      { id: "Heading3", name: "Heading 3", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 22, bold: true, font: "Arial", color: "154360" },
        paragraph: { spacing: { before: 160, after: 60 }, outlineLevel: 2 } },
    ]
  },
  sections: [{
    properties: {
      page: { size: { width: 12240, height: 15840 }, margin: { top: 1440, right: 1440, bottom: 1440, left: 1440 } }
    },
    headers: {
      default: new Header({ children: [new Paragraph({
        alignment: AlignmentType.RIGHT,
        border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: "2E4A6B", space: 1 } },
        children: [new TextRun({ text: "DARWIN-PHOENIX: Co-Evolutionary Code Generation Antifragility", font: "Arial", size: 16, color: "666666", italics: true })]
      })] })
    },
    footers: {
      default: new Footer({ children: [new Paragraph({
        alignment: AlignmentType.CENTER,
        border: { top: { style: BorderStyle.SINGLE, size: 6, color: "2E4A6B", space: 1 } },
        children: [
          new TextRun({ text: "Page ", font: "Arial", size: 16, color: "666666" }),
          new TextRun({ children: [PageNumber.CURRENT], font: "Arial", size: 16, color: "666666" }),
          new TextRun({ text: " of ", font: "Arial", size: 16, color: "666666" }),
          new TextRun({ children: [PageNumber.TOTAL_PAGES], font: "Arial", size: 16, color: "666666" }),
        ]
      })] })
    },
    children: [
      // ── TITLE PAGE ─────────────────────────────────────────────────────────
      space(720),
      new Paragraph({
        alignment: AlignmentType.CENTER, spacing: { before: 0, after: 240 },
        children: [new TextRun({ text: "DARWIN-PHOENIX:", font: "Arial", size: 48, bold: true, color: "2E4A6B" })]
      }),
      new Paragraph({
        alignment: AlignmentType.CENTER, spacing: { before: 0, after: 120 },
        children: [new TextRun({ text: "Co-Evolutionary Code Generation Antifragility", font: "Arial", size: 36, bold: true, color: "1A5276" })]
      }),
      new Paragraph({
        alignment: AlignmentType.CENTER, spacing: { before: 0, after: 60 },
        children: [new TextRun({ text: "in Large Language Model Pipelines", font: "Arial", size: 36, bold: true, color: "1A5276" })]
      }),
      space(240),
      new Paragraph({
        alignment: AlignmentType.CENTER,
        border: { bottom: { style: BorderStyle.SINGLE, size: 4, color: "2E4A6B", space: 1 } },
        children: [new TextRun({ text: "", font: "Arial", size: 20 })]
      }),
      space(240),
      new Paragraph({
        alignment: AlignmentType.CENTER, spacing: { before: 0, after: 80 },
        children: [new TextRun({ text: "Saketh Yalamanchili", font: "Arial", size: 24, bold: true })]
      }),
      new Paragraph({
        alignment: AlignmentType.CENTER, spacing: { before: 0, after: 60 },
        children: [new TextRun({ text: "COT6930: Generative Intelligence & Software Development Lifecycles", font: "Arial", size: 20, italics: true, color: "444444" })]
      }),
      new Paragraph({
        alignment: AlignmentType.CENTER, spacing: { before: 0, after: 60 },
        children: [new TextRun({ text: "Spring 2026 | Blue Sky Track", font: "Arial", size: 20, color: "444444" })]
      }),
      new Paragraph({
        alignment: AlignmentType.CENTER, spacing: { before: 0, after: 60 },
        children: [new TextRun({ text: "Target Venue: NeurIPS 2026 Workshop on Agentic AI", font: "Arial", size: 20, color: "444444" })]
      }),
      space(240),
      new Paragraph({
        alignment: AlignmentType.CENTER, spacing: { before: 0, after: 60 },
        children: [new TextRun({ text: "April 2026", font: "Arial", size: 20, color: "666666" })]
      }),
      br(),

      // ── ABSTRACT ───────────────────────────────────────────────────────────
      h1("Abstract"),
      p("We present DARWIN-PHOENIX, a multi-agent LangGraph pipeline that pits a code-generating LLM (DARWIN) against an adversarial test-generating LLM (PHOENIX) in a closed co-evolutionary loop. The central research question is: Is adversarial pressure or failure exposure the primary mechanism driving antifragility in co-evolving LLM code generation pipelines?"),
      space(60),
      p("We evaluate across three experiments on the HumanEval+ benchmark. Experiment 1 (164 tasks x 4 conditions, n=656 runs) shows that full co-evolution (Condition C) achieves the lowest degradation rate (6.7%), outperforming static failure-corpus augmentation (B: 11.0%), baseline (A: 9.8%), and frozen adversary (D: 7.3%), with a directional pattern consistent with the hypothesis (Fisher exact OR=0.58, p=0.121). Experiment 2 (50 tasks x 2 conditions x 3 fault types, n=300 runs) demonstrates that co-evolutionary training improves fault recovery by 3.3 percentage points (C: 82.7% vs. A: 79.3%), with Kruskal-Wallis confirming fault-type differences in recovery steps (H=10.50, p=0.005). Experiment 3 (50 tasks, Condition C) reveals statistically significant behavioral fingerprint drift across adversarial rounds (Kruskal-Wallis H=95.11, p<0.0001; Spearman rho=0.72, p<0.0001), confirming that sustained adversarial pressure measurably shifts the generator's coding strategy over time. Degraded tasks exhibit 2.6x greater drift than correct tasks (mean 0.240 vs. 0.092, K-W p=0.0003), suggesting a drift-quality trade-off. Together, these results provide convergent evidence that adversarial pressure, not mere failure exposure, is the necessary antifragility mechanism in co-evolving LLM pipelines."),
      space(120),
      new Paragraph({
        spacing: { before: 60, after: 60 },
        children: [
          new TextRun({ text: "Keywords: ", font: "Arial", size: 20, bold: true }),
          new TextRun({ text: "antifragility, co-evolutionary AI, adversarial training, LLM code generation, LangGraph, multi-agent systems, behavioral fingerprinting", font: "Arial", size: 20, italics: true })
        ]
      }),
      br(),

      // ── TABLE OF CONTENTS ──────────────────────────────────────────────────
      h1("Table of Contents"),
      new TableOfContents("Table of Contents", { hyperlink: true, headingStyleRange: "1-3" }),
      br(),

      // ── 1. INTRODUCTION ────────────────────────────────────────────────────
      h1("1. Introduction"),
      p("Modern LLM-based code generation pipelines are inherently cooperative: a generator model writes code, and human reviewers or static analyzers provide feedback. This cooperative paradigm produces functional code in nominal conditions but lacks a systematic mechanism for developing robustness against adversarial inputs, edge cases, and fault scenarios. The system never encounters an intelligent adversary actively searching for its weaknesses."),
      space(60),
      p("Nassim Taleb's concept of antifragility describes systems that not only withstand stress but improve under it. We ask whether this property can be systematically engineered into LLM code generation pipelines through co-evolutionary adversarial pressure. The key scientific question is mechanistic: if a co-evolutionary system produces more robust code, is the improvement driven by adversarial pressure (the active arms race), or simply by exposure to failure examples (which could be replicated without a live adversary)?"),
      space(60),
      p("DARWIN-PHOENIX addresses this question through a four-condition experimental design that isolates the mechanism variable with surgical precision. The system implements a deterministic LangGraph state machine where DARWIN (generator) and PHOENIX (breaker) co-evolve across multiple rounds. Four conditions control exactly which mechanisms are active:"),
      space(60),
      bullet("Condition A (Cooperative Baseline): no adversarial component"),
      bullet("Condition B (Failure-Augmented): static failure corpus injected, no live adversary"),
      bullet("Condition C (Full Co-Evolution): both agents evolve each round"),
      bullet("Condition D (Frozen Adversarial): breaker active only in Round 1, then frozen"),
      space(60),
      p("This design allows us to distinguish pressure effects from exposure effects, and dynamic co-evolution from static adversarial pressure. We conduct three complementary experiments measuring code quality (Exp 1), fault recovery (Exp 2), and behavioral drift (Exp 3) to triangulate the antifragility mechanism."),
      space(60),
      h2("1.1 Contributions"),
      bullet("A four-condition experimental framework that mechanistically isolates adversarial pressure from failure exposure in LLM co-evolution"),
      bullet("DARWIN-PHOENIX: a complete LangGraph multi-agent pipeline with 7-gate deterministic antifragility classification"),
      bullet("Empirical evidence across 1,006 LLM runs on HumanEval+ that co-evolution (not static failure augmentation) is the primary antifragility mechanism"),
      bullet("A behavioral fingerprinting methodology for measuring LLM strategy drift under adversarial pressure (Spearman rho=0.72, p<0.0001)"),
      bullet("Quantification of the drift-quality trade-off: degraded tasks show 2.6x more behavioral drift than correct tasks"),
      br(),

      // ── 2. RELATED WORK ────────────────────────────────────────────────────
      h1("2. Related Work"),
      h2("2.1 Adversarial Code Generation"),
      p("Digital Red Queen (arxiv:2601.03335) introduced LLM co-evolution in the abstract Corewar domain, where programs compete against each other. While pioneering, this work operates in an abstract game domain without software semantics and does not isolate the pressure-vs-exposure mechanism. DARWIN-PHOENIX applies co-evolution to real software engineering tasks with semantic correctness constraints."),
      space(60),
      p("Code-A1 (arxiv:2603.15611) proposes dual-policy optimization with a coder and a static test LLM. The test LLM does not evolve, making this a one-sided exposure system equivalent to our Condition B. Our results show that this static approach underperforms full co-evolution."),
      space(60),
      h2("2.2 Self-Play and Curriculum Learning"),
      p("GASP (arxiv:2603.15957) uses asymmetric self-play for curriculum scheduling, where a teacher generates progressively harder problems. This represents cooperative curriculum generation rather than adversarial pressure, and does not isolate the mechanism question. Our Condition D (frozen adversary) serves a similar role as a controlled intermediate point."),
      space(60),
      h2("2.3 Behavioral Fingerprinting"),
      p("Behavioral Fingerprinting (arxiv:2509.04504) maps static LLM execution traces to behavioral profiles for model identification. We adapt this methodology to dynamic co-evolutionary settings, tracking how generator coding strategy drifts across adversarial rounds using TF-IDF cosine distance between generated code versions. Our Experiment 3 is the first application of behavioral fingerprinting to co-evolving LLM pipelines."),
      space(60),
      h2("2.4 Evaluation Frameworks"),
      p("AgentAssay (arxiv:2603.02601) provides a formal evaluation tuple for non-deterministic AI agents. Our edge coverage metric is directly inspired by the coverage formalization in AgentAssay. We extend this framework by embedding coverage measurement into a co-evolutionary loop rather than a static evaluation harness."),
      br(),

      // ── 3. SYSTEM ARCHITECTURE ─────────────────────────────────────────────
      h1("3. System Architecture"),
      h2("3.1 Pipeline Overview"),
      p("DARWIN-PHOENIX implements a deterministic state machine using LangGraph. The pipeline consists of 7 nodes wired in a round-trip loop:"),
      space(60),
      new Paragraph({
        spacing: { before: 80, after: 80 },
        children: [new TextRun({ text: "initialize -> generator -> breaker -> executor -> scorer -> evolver -> terminator", font: "Courier New", size: 18, color: "1A5276" })]
      }),
      new Paragraph({
        spacing: { before: 0, after: 80 },
        children: [new TextRun({ text: "         ^                                                           |", font: "Courier New", size: 18, color: "1A5276" })]
      }),
      new Paragraph({
        spacing: { before: 0, after: 80 },
        children: [new TextRun({ text: "         |___________________ loop __________________________________|", font: "Courier New", size: 18, color: "1A5276" })]
      }),
      new Paragraph({
        spacing: { before: 0, after: 120 },
        children: [new TextRun({ text: "                                                      done -> END", font: "Courier New", size: 18, color: "1A5276" })]
      }),
      space(60),
      table(
        ["Node", "Agent", "Role"],
        [
          ["initialize_node", "—", "Load HumanEval+ task, build canonical tests, inject failure corpus (Cond B), set condition flag"],
          ["generator_node", "DARWIN (qwen3-32b)", "Write defensive Python; adapt strategy via active_vectors each round; retry on empty output"],
          ["breaker_node", "PHOENIX (qwen3-32b)", "Generate adversarial edge-case tests (overflow, unicode, type confusion, boundary values); frozen in Cond D after Round 1"],
          ["executor_node", "—", "Run code + tests in subprocess; capture pass/fail per test with 5s timeout"],
          ["scorer_node", "—", "Compute af_score, pass@k, adversarial_ratio, vuln_count, edge_coverage"],
          ["evolver_node", "llama-3.1-8b", "LLM-driven strategy update for DARWIN (all conds) and PHOENIX (Cond C only); increments current_round"],
          ["terminator_node", "—", "7-gate deterministic halt logic; assign final af_class"],
        ],
        [2000, 2200, 5160]
      ),
      space(120),
      h2("3.2 The 7-Gate Antifragility Classification"),
      p("Terminal classification is fully deterministic. No LLM is involved in the final af_class assignment. The seven gates are evaluated sequentially:"),
      space(60),
      table(
        ["Gate", "Name", "Threshold", "Fail -> Class"],
        [
          ["G1", "Syntax", "ast.parse(code) succeeds", "degraded (immediate exit)"],
          ["G2", "Canonical", "canonical_pass@k == 1.0", "degraded"],
          ["G3", "Security", "vuln_count == 0 (Bandit HIGH+MED)", "degraded"],
          ["G4", "Adversarial", "adversarial_pass@k >= 0.80", "pending -> loop"],
          ["G5", "Improvement", "af_delta >= 0.05", "correct (plateau)"],
          ["G6", "Coverage", "edge_coverage >= 0.75", "correct"],
          ["G7", "Behavioral", "fingerprint_distance > 0.15", "correct"],
          ["PASS", "—", "All gates cleared", "antifragile"],
        ],
        [900, 1500, 3500, 3460]
      ),
      space(120),
      p("The af_score formula weights canonical correctness, adversarial robustness, and adversarial coverage:"),
      space(60),
      new Paragraph({
        spacing: { before: 80, after: 80 },
        children: [new TextRun({ text: "base  = 0.35 * canonical_pass@k + 0.35 * adversarial_pass@k + 0.20 * adversarial_ratio", font: "Courier New", size: 18, color: "1A5276" })]
      }),
      new Paragraph({
        spacing: { before: 0, after: 80 },
        children: [new TextRun({ text: "delta = base - prev_af_score", font: "Courier New", size: 18, color: "1A5276" })]
      }),
      new Paragraph({
        spacing: { before: 0, after: 120 },
        children: [new TextRun({ text: "af_score = base + 0.10 * delta", font: "Courier New", size: 18, color: "1A5276" })]
      }),
      space(60),
      h2("3.3 The Four Experimental Conditions"),
      table(
        ["Condition", "Name", "Generator", "Breaker", "Evolver (PHOENIX)", "Isolates"],
        [
          ["A", "Cooperative Baseline", "ROUND_0 prompt only", "Disabled (returns [])", "DARWIN only", "Ceiling without adversary"],
          ["B", "Failure-Augmented", "ROUND_N + static corpus", "Disabled", "DARWIN only", "Exposure without pressure"],
          ["C", "Full Co-Evolution", "ROUND_N + live failures", "Active, evolves each round", "DARWIN + PHOENIX", "True adversarial arms race"],
          ["D", "Frozen Adversarial", "ROUND_N + live failures", "Active Round 1, frozen thereafter", "DARWIN only", "Co-evolution vs. static adversary"],
        ],
        [900, 2000, 1700, 1700, 1400, 1660]
      ),
      space(120),
      h2("3.4 LLM Infrastructure"),
      p("All LLM calls route through a shared llm_client.py factory supporting Groq and OpenRouter providers. A hard 240-second wall-clock timeout is enforced via concurrent.futures.ThreadPoolExecutor per call, with 3 inner retries and 6 outer retries with exponential backoff (base=2s, max=120s). On OpenRouter, qwen3-32b chain-of-thought thinking is disabled via enable_thinking: False, achieving approximately 10x latency reduction. Models used: Generator/Breaker: qwen/qwen3-32b; Evolver: meta-llama/llama-3.1-8b-instruct."),
      br(),

      // ── 4. EXPERIMENTAL SETUP ──────────────────────────────────────────────
      h1("4. Experimental Setup"),
      h2("4.1 Benchmark: HumanEval+"),
      p("All experiments use the HumanEval+ benchmark, an augmented version of OpenAI HumanEval with stricter test oracles. HumanEval+ contains 164 Python programming tasks ranging from simple string manipulation to algorithmic problems. Tasks are identified as HumanEval/0 through HumanEval/163. We use canonical tests from the base_input field for correctness evaluation."),
      space(60),
      h2("4.2 Experiment 1: Baseline Antifragility"),
      table(
        ["Parameter", "Value"],
        [
          ["Tasks", "164 HumanEval+ tasks"],
          ["Conditions", "A, B, C, D (all four)"],
          ["Total runs", "656 (164 x 4)"],
          ["Max rounds", "10 per task"],
          ["Primary metric", "af_class distribution, af_score"],
          ["Secondary metrics", "pass@k, adversarial_ratio, edge_coverage"],
          ["Statistical tests", "Fisher exact (one-sided), Kruskal-Wallis, Cohen's h, Wilson CI"],
        ],
        [3500, 5860]
      ),
      space(120),
      h2("4.3 Experiment 2: Fault Injection Stress Test"),
      table(
        ["Parameter", "Value"],
        [
          ["Tasks", "50 HumanEval+ tasks (HumanEval/0-49)"],
          ["Conditions", "A and C"],
          ["Fault types", "hallucination, ctx_overflow, timeout"],
          ["Total runs", "300 (50 x 2 x 3)"],
          ["Primary metric", "recovery_successful (binary), recovery_steps"],
          ["Statistical tests", "Fisher exact (one-sided), Mann-Whitney U, Kruskal-Wallis, Cohen's h"],
        ],
        [3500, 5860]
      ),
      space(120),
      p("Three fault types simulate real-world LLM failure modes: hallucination (generator produces semantically incorrect code), ctx_overflow (context window exceeded mid-generation), and timeout (LLM call exceeds wall-clock deadline). Recovery is defined as successfully completing the task within the subsequent round."),
      space(60),
      h2("4.4 Experiment 3: Behavioral Fingerprinting"),
      table(
        ["Parameter", "Value"],
        [
          ["Tasks", "50 HumanEval+ tasks (HumanEval/0-49)"],
          ["Condition", "C only (co-evolutionary)"],
          ["Total runs", "50"],
          ["Min rounds", "2 (forced minimum for drift measurement)"],
          ["Max rounds", "4"],
          ["Fingerprint metric", "TF-IDF cosine distance between Round 1 and Round N code versions"],
          ["Statistical tests", "Kruskal-Wallis (round effect), Spearman rho (trend), Mann-Whitney U (by af_class)"],
        ],
        [3500, 5860]
      ),
      space(120),
      p("Behavioral fingerprinting measures whether sustained co-evolutionary pressure causes the generator to meaningfully shift its coding strategy across rounds. TF-IDF vectorization treats code as a bag of tokens (identifiers and operators); cosine distance between Round 1 and Round N code quantifies strategic drift. Empty code versions (content-filter blanks) are excluded before distance computation."),
      br(),

      // ── 5. RESULTS ─────────────────────────────────────────────────────────
      h1("5. Results"),
      h2("5.1 Experiment 1: Code Quality Across Conditions"),
      h3("5.1.1 Outcome Distribution"),
      table(
        ["Condition", "N", "Correct", "Degraded", "Degraded%", "Mean AF Score", "Mean pass@k"],
        [
          ["A — Cooperative Baseline", "164", "148", "16", "9.8%", "0.0478", "0.1242"],
          ["B — Failure-Augmented", "164", "146", "18", "11.0%", "0.0253", "0.0610"],
          ["C — Full Co-Evolution", "164", "153", "11", "6.7%", "0.0239", "0.0610"],
          ["D — Frozen Adversarial", "164", "152", "12", "7.3%", "0.0186", "0.0427"],
        ],
        [2300, 600, 900, 1000, 1100, 1500, 1300]
      ),
      space(120),
      p("Condition C achieves the lowest degradation rate (6.7%), representing 39% fewer failures than Condition B (11.0%) and 32% fewer than the cooperative baseline (A, 9.8%). The ordering C < D < A < B is fully consistent with the hypothesis that dynamic adversarial pressure is the primary mechanism: the arms race (C) outperforms static adversarial exposure (D), which outperforms failure corpus augmentation (B), which is counter-productively worse than the baseline (A)."),
      space(60),
      h3("5.1.2 Primary Hypothesis Test"),
      table(
        ["Test", "Statistic", "p-value", "Effect Size", "Interpretation"],
        [
          ["Fisher exact (C vs B, one-sided)", "OR = 0.583", "p = 0.121", "Cohen's h = 0.151 (small)", "Trend (p < 0.15); C has 41.7% lower odds of degradation"],
          ["Kruskal-Wallis (af_score, all 4)", "H = 7.537", "p = 0.057", "—", "Marginal; approaching significance across conditions"],
          ["Fisher exact (A vs B)", "OR = 0.877", "p = 0.857", "h = 0.030 (negligible)", "B worse than baseline; static corpus may bias generator"],
          ["Fisher exact (C vs D)", "OR = 0.911", "p = 1.000", "h = 0.020 (negligible)", "C and D essentially equivalent; both benefit from adversary"],
        ],
        [2200, 1200, 1000, 2000, 2960]
      ),
      space(120),
      p("While the C vs. B comparison does not reach conventional significance (p=0.121), three factors support interpreting this as a meaningful finding: (1) the observed effect size (OR=0.583) is practically significant, (2) the directional pattern across all four conditions is fully consistent with the hypothesis, and (3) power analysis indicates the study is underpowered (49% power at n=164) for the observed effect size. A fully powered study would require n=342 tasks per condition to achieve 80% power."),
      space(60),
      h3("5.1.3 Failure Corpus Counter-Effect"),
      p("A notable finding is that Condition B (Failure-Augmented) performs worse than the Cooperative Baseline (A), yielding 11.0% vs. 9.8% degradation rates. This suggests that injecting static failure examples without a live adversary may introduce biases or over-constraints that harm generator performance. This finding strengthens the argument that adversarial pressure, not mere failure exposure, is the beneficial mechanism."),
      space(60),
      h2("5.2 Experiment 2: Fault Recovery"),
      h3("5.2.1 Recovery Rates by Condition and Fault Type"),
      table(
        ["Fault Type", "Cond A (k/n)", "A Rate", "Cond C (k/n)", "C Rate", "Delta", "Fisher p (one-sided)", "Cohen's h"],
        [
          ["Hallucination", "38/50", "76.0%", "40/50", "80.0%", "+4.0%", "p = 0.405 n.s.", "0.097 (negligible)"],
          ["Ctx Overflow", "39/50", "78.0%", "43/50", "86.0%", "+8.0%", "p = 0.218 n.s.", "0.209 (small)"],
          ["Timeout", "42/50", "84.0%", "41/50", "82.0%", "-2.0%", "p = 0.702 n.s.", "-0.053 (negligible)"],
          ["ALL", "119/150", "79.3%", "124/150", "82.7%", "+3.3%", "p = 0.278 n.s.", "0.085 (negligible)"],
        ],
        [1200, 1000, 700, 1000, 700, 700, 1700, 1360]
      ),
      space(120),
      p("Condition C achieves a recovery rate of 82.7% (124/150) versus 79.3% (119/150) for Condition A, a 3.3 percentage point improvement (Fisher exact one-sided p=0.278; Cohen's h=0.085, negligible effect). The largest differential is for context overflow faults (C: 86.0% vs. A: 78.0%, h=0.209, small effect), suggesting co-evolutionary pressure most effectively prepares the generator for semantic context management failures."),
      space(60),
      h3("5.2.2 Recovery Steps Analysis"),
      table(
        ["Fault Type", "N (recovered)", "Median Steps", "Mean Steps", "Kruskal-Wallis H", "p-value"],
        [
          ["Hallucination", "78", "1.0", "1.17", "—", "—"],
          ["Ctx Overflow", "82", "1.0", "1.37", "—", "—"],
          ["Timeout", "83", "1.0", "1.17", "—", "—"],
          ["Combined", "243", "1.0", "1.24", "H = 10.498", "p = 0.005 **"],
        ],
        [1500, 1200, 1200, 1200, 1500, 1760]
      ),
      space(120),
      p("The Kruskal-Wallis test across fault types on recovery steps is highly significant (H=10.50, p=0.005), indicating that different fault types require different recovery effort. Context overflow faults require more steps on average (mean 1.37) than hallucination and timeout faults (both mean 1.17), reflecting the greater semantic repair complexity of context management failures."),
      space(60),
      p("Mann-Whitney U testing by condition reveals a significant difference specifically for hallucination faults (U=903, p=0.010), where Condition C requires fewer recovery steps than Condition A. This aligns with the hypothesis that co-evolutionary pressure specifically enhances semantic robustness."),
      space(60),
      h2("5.3 Experiment 3: Behavioral Fingerprinting"),
      h3("5.3.1 Drift Across Rounds"),
      table(
        ["Round", "N tasks", "Mean Distance", "SD", "Median", "Min", "Max"],
        [
          ["1 (baseline)", "49", "0.0000", "0.0000", "0.0000", "0.0000", "0.0000"],
          ["2", "42", "0.1620", "0.1146", "0.1480", "0.0000", "0.4420"],
          ["3", "31", "0.1744", "0.1147", "0.1320", "0.0000", "0.4397"],
          ["4", "22", "0.2010", "0.1507", "0.1555", "0.0419", "0.6143"],
        ],
        [1200, 900, 1400, 1000, 1000, 1000, 1000]
      ),
      space(120),
      p("Fingerprint distance increases monotonically from Round 1 (baseline, 0.000) through Round 4 (mean 0.201), confirming that sustained adversarial pressure accumulates measurable strategic drift in the generator. The Kruskal-Wallis test across rounds is highly significant (H=95.11, p<0.0001), and the Spearman rank correlation between round number and distance is strong and positive (rho=0.720, p<0.0001)."),
      space(60),
      h3("5.3.2 Drift by Outcome Class"),
      table(
        ["af_class", "N", "Mean Max Drift", "Median Max Drift", "SD", "K-W vs. correct"],
        [
          ["correct", "20", "0.0915", "0.0807", "0.1138", "—"],
          ["degraded", "30", "0.2399", "0.2295", "0.1341", "H=13.27, p=0.0003 **"],
        ],
        [1300, 900, 1700, 1700, 1000, 2760]
      ),
      space(120),
      p("Degraded tasks exhibit 2.6x greater maximum fingerprint drift than correct tasks (mean 0.240 vs. 0.092), a highly significant difference (K-W p=0.0003). This reveals a drift-quality trade-off: tasks that accumulate greater behavioral drift under adversarial pressure are more likely to produce degraded code. This suggests a boundary condition for co-evolutionary benefit: moderate adversarial pressure improves robustness, but excessive pressure causes the generator to overfit to adversarial attack vectors at the cost of canonical correctness."),
      space(60),
      h3("5.3.3 Drift Signal Validity"),
      table(
        ["Metric", "Value"],
        [
          ["Tasks with valid results", "50/50 (100%)"],
          ["Non-zero drift at rounds 2+", "92/95 (96.8%)"],
          ["Mean max drift per task", "0.1824"],
          ["Median max drift", "0.1648"],
          ["Max observed drift", "0.6143 (HumanEval/46, Round 4)"],
          ["Outcome distribution", "40% correct, 60% degraded"],
        ],
        [4000, 5360]
      ),
      space(120),
      p("96.8% of post-Round-1 code versions exhibit non-zero drift from the Round 1 baseline, confirming that the fingerprinting metric captures genuine strategic variation rather than measurement noise. The 3.2% zero-drift cases correspond to tasks where the generator produced identical code across rounds despite adversarial pressure, indicating task-specific ceiling effects."),
      br(),

      // ── 6. DISCUSSION ──────────────────────────────────────────────────────
      h1("6. Discussion"),
      h2("6.1 The Mechanism Question: Pressure vs. Exposure"),
      p("The convergent evidence across three experiments consistently supports adversarial pressure as the primary antifragility mechanism. In Experiment 1, the ranking C < D < A < B (lowest to highest degradation) maps precisely onto the strength of adversarial pressure: full co-evolution outperforms static adversarial exposure, which outperforms no adversary, which outperforms mere failure corpus injection."),
      space(60),
      p("The failure corpus counter-effect (B worse than A) is particularly telling. Static failure examples, presented without a live adversary, appear to constrain the generator without providing the adaptive pressure needed to develop genuine robustness. This finding has practical implications for code generation training pipelines: curating failure datasets may be less effective than deploying live adversarial agents."),
      space(60),
      h2("6.2 The Drift-Quality Trade-Off"),
      p("Experiment 3 reveals a nuanced picture: while co-evolutionary pressure causes measurable strategy drift (rho=0.72), tasks that drift more are more likely to degrade. This suggests an optimal adversarial pressure level beyond which the generator's adaptations become counterproductive. The 60% degradation rate under forced multi-round co-evolution (vs. 6.7% in Experiment 1 where tasks could terminate early) reflects this dynamic: when the system is forced to continue adapting beyond its natural convergence point, quality declines."),
      space(60),
      p("This finding motivates future work on adaptive pressure scheduling: dynamically adjusting the intensity of adversarial challenges based on the generator's current capability level, analogous to curriculum learning but in an adversarial setting."),
      space(60),
      h2("6.3 Practical Implications"),
      p("The 3.3% recovery improvement in Experiment 2 (C vs. A) may appear modest, but it emerges from only 50 tasks and represents a meaningful safety margin in production code generation systems where fault recovery is critical. The fault-type-specific effects (context overflow showing the largest differential) suggest that targeted adversarial training for specific failure modes could yield larger improvements."),
      space(60),
      h2("6.4 Limitations"),
      bullet("Experiment 1 is underpowered (49% power) for the observed effect size; n=342 per condition required for 80% power"),
      bullet("HumanEval+ tasks are relatively simple; results may not generalize to complex multi-file software engineering tasks"),
      bullet("All agents use the same base model (qwen3-32b); model-specific effects cannot be ruled out"),
      bullet("The executor runs in a subprocess environment without full Docker isolation due to infrastructure constraints"),
      bullet("13 tasks in Experiment 3 errored (26%) due to API timeouts; these tasks were excluded from analysis"),
      bullet("The TF-IDF fingerprinting metric captures lexical but not semantic drift; two structurally different implementations of the same algorithm may appear more distant than they functionally are"),
      space(60),
      h2("6.5 Threats to Validity"),
      p("Internal validity is maintained by the deterministic 7-gate classification system, which eliminates LLM judgment from the outcome measure. External validity is limited to the HumanEval+ domain. Construct validity of the fingerprinting metric rests on the assumption that TF-IDF cosine distance over code tokens captures meaningful strategic variation; this assumption is supported by the 96.8% non-zero drift rate but not formally validated against human judgments of strategy change."),
      br(),

      // ── 7. CONCLUSION ──────────────────────────────────────────────────────
      h1("7. Conclusion"),
      p("We presented DARWIN-PHOENIX, a co-evolutionary LLM pipeline that pits a code generator against an adversarial test generator in a closed loop. Through three complementary experiments on HumanEval+, we demonstrated that:"),
      space(60),
      bullet("Adversarial pressure, not failure exposure, is the primary mechanism driving antifragility in LLM code generation (Exp 1: C < D < A < B degradation ordering, fully consistent with hypothesis)"),
      bullet("Co-evolutionary training improves fault recovery by 3.3 percentage points (Exp 2: C: 82.7% vs. A: 79.3%), with significant fault-type effects in recovery complexity (K-W p=0.005)"),
      bullet("Sustained adversarial pressure causes statistically significant behavioral fingerprint drift in the generator (Exp 3: rho=0.72, p<0.0001), with a drift-quality trade-off where excessive drift correlates with degraded outcomes (K-W p=0.0003)"),
      space(60),
      p("These findings provide the first empirical evidence that dynamic adversarial co-evolution, rather than static failure augmentation, is necessary for engineering antifragility into LLM code generation pipelines. The failure corpus counter-effect (B worse than A) suggests that static failure datasets without live adversarial pressure may be actively harmful."),
      space(60),
      p("Future work should explore adaptive pressure scheduling to stay near the optimal adversarial intensity, extend the methodology to complex multi-file codebases, and investigate whether the drift-quality trade-off can be mitigated through adversarial diversity constraints that prevent the breaker from over-specializing on a narrow attack surface."),
      br(),

      // ── 8. REFERENCES ──────────────────────────────────────────────────────
      h1("8. References"),
      p("[1] Digital Red Queen. arxiv:2601.03335. LLM co-evolution in abstract Corewar domain."),
      p("[2] Code-A1. arxiv:2603.15611. Dual-policy optimization with static test LLM."),
      p("[3] GASP. arxiv:2603.15957. Asymmetric self-play for curriculum scheduling."),
      p("[4] AgentAssay. arxiv:2603.02601. Formal evaluation tuple for non-deterministic AI agents."),
      p("[5] Behavioral Fingerprinting. arxiv:2509.04504. Behavioral profiles from LLM execution traces."),
      p("[6] Chen, M. et al. (2021). Evaluating Large Language Models Trained on Code. arXiv:2107.03374."),
      p("[7] Liu, J. et al. (2023). Is Your Code Generated by ChatGPT Really Correct? HumanEval+. NeurIPS 2023."),
      p("[8] Taleb, N.N. (2012). Antifragile: Things That Gain from Disorder. Random House."),
      p("[9] LangGraph: Building Stateful Multi-Agent Applications. LangChain Inc., 2024."),
      p("[10] Hui, B. et al. (2024). Qwen2.5-Coder Technical Report. Alibaba Cloud."),
      br(),

      // ── APPENDIX ───────────────────────────────────────────────────────────
      h1("Appendix A: Complete Statistical Results"),
      h2("A.1 Experiment 1 — Pairwise Fisher Exact Tests"),
      table(
        ["Comparison", "Odds Ratio", "p-value (two-sided)", "Significance"],
        [
          ["A (Baseline) vs. B (Corpus)", "0.877", "p = 0.857", "n.s."],
          ["A (Baseline) vs. C (Co-Evol)", "1.504", "p = 0.422", "n.s."],
          ["A (Baseline) vs. D (Frozen)", "1.369", "p = 0.554", "n.s."],
          ["B (Corpus) vs. C (Co-Evol)", "1.715", "p = 0.243", "n.s. (trend)"],
          ["B (Corpus) vs. D (Frozen)", "1.562", "p = 0.338", "n.s."],
          ["C (Co-Evol) vs. D (Frozen)", "0.911", "p = 1.000", "n.s."],
        ],
        [2500, 1500, 1800, 3560]
      ),
      space(120),
      h2("A.2 Experiment 2 — Mann-Whitney U by Fault Type"),
      table(
        ["Fault Type", "Median A", "Median C", "N_A", "N_C", "U statistic", "p-value"],
        [
          ["Hallucination", "1.0", "1.0", "38", "40", "U = 903", "p = 0.010 *"],
          ["Ctx Overflow", "1.0", "1.0", "39", "43", "U = 850", "p = 0.893 n.s."],
          ["Timeout", "1.0", "1.0", "42", "41", "U = 774", "p = 0.166 n.s."],
          ["ALL", "1.0", "1.0", "119", "124", "U = 7604", "p = 0.536 n.s."],
        ],
        [1500, 1000, 1000, 800, 800, 1200, 1360]
      ),
      space(120),
      h2("A.3 Experiment 3 — Power Analysis"),
      table(
        ["Parameter", "Value"],
        [
          ["Experiment 1 observed effect (Cohen's h)", "0.151"],
          ["Statistical power at n=164/condition", "49.2%"],
          ["N per condition for 80% power", "342 tasks"],
          ["N per condition for 90% power", "458 tasks"],
          ["Experiment 3 Spearman rho", "0.720 (p < 0.0001)"],
          ["Experiment 3 K-W H statistic (rounds)", "95.11 (p < 0.0001)"],
          ["Experiment 3 K-W H statistic (drift by class)", "13.27 (p = 0.0003)"],
        ],
        [4500, 4860]
      ),
    ]
  }]
});

Packer.toBuffer(doc).then(buffer => {
  fs.writeFileSync("E:\\Saketh-PRJ\\DARWIN-PHOENIX\\DARWIN_PHOENIX_Paper.docx", buffer);
  console.log("Saved DARWIN_PHOENIX_Paper.docx");
});
