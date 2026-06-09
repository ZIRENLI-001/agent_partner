# GitHub README Design

## Goal

Turn the repository README into a polished, comprehensive GitHub landing page
for judges, product stakeholders, and developers without overstating the
current implementation.

## Audience And Positioning

The README uses Chinese as the primary language because the project materials,
business context, and target users are Chinese-speaking. English identifiers,
API names, commands, and established technical terms remain unchanged.

The page presents the project as:

> A multi-turn dialogue evaluation platform that compiles complex task
> instructions into executable scenarios, dynamic rubrics, evidence-backed
> scores, and actionable reports.

It emphasizes fulfillment outbound-call scenarios while making clear that the
architecture can support other instruction-driven customer-service tasks.

## Page Structure

1. Centered product title, one-sentence positioning, badges, and navigation.
2. Public demo link plus a warning not to upload sensitive production data.
3. Problem statement and project value.
4. Core capabilities in a compact feature table.
5. Quick evaluation and staged evaluation workflows.
6. Mermaid diagram showing the complete evaluation chain.
7. Explainability and artifact outputs.
8. Explicit dialogue termination and eight-round safety budget.
9. Technology stack and repository architecture.
10. Local quick start with mock mode as the default.
11. Real model configuration and backend-owned evaluation model routing.
12. API overview.
13. Testing, production deployment, and public-beta security boundaries.
14. Repository layout and detailed documentation links.

## Visual Style

- Use a centered HTML header that renders reliably on GitHub.
- Use shields.io badges for Python, FastAPI, React, TypeScript, Vite, and
  license/status-neutral project metadata.
- Use flat tables and short sections rather than deeply nested lists.
- Use one Mermaid flowchart for architecture; avoid external generated images.
- Reuse repository content only when it is genuinely product-facing. The
  existing root `image.png` and `background/image.png` are source/background
  materials rather than UI screenshots, so they will not be presented as
  product screenshots.
- Avoid emojis in headings to keep the tone professional and consistent with
  repository documentation.

## Accuracy Boundaries

The README must not claim:

- full production multi-tenant authentication;
- a database-backed ownership model;
- that every environment uses a specific commercial model;
- benchmark results not represented by current tests or artifacts;
- a fully open anonymous demo without noting shared-history and sensitive-data
  risks.

The README may state:

- both end-to-end and staged evaluation are implemented;
- confirmed staged artifacts are reused by the final run;
- the runner supports up to eight complete interaction rounds and explicit
  termination signals;
- rule and semantic evaluation are combined;
- run artifacts and evidence chains are persisted;
- the current public beta is available at `https://agentpartner.top`;
- the repository has automated backend tests and a production frontend build.

## Verification

After rewriting:

- validate every relative documentation link exists;
- validate every documented Make target exists;
- run the backend test suite and frontend production build;
- inspect README headings, fenced blocks, tables, and Mermaid delimiters;
- ensure no API key, access token, server secret, or private key appears in the
  document.
