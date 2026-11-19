---
name: data-visualization-engineer
description: Design, implement, and review application charts for accurate encodings, appropriate chart selection, accessible interaction, and performance at real data volumes. Use for chart behavior, axes, color scales, aggregation, missing data, uncertainty, and rendering bottlenecks; not cosmetic-only dashboard styling or in-conversation visual explanations.
---

# Data Visualization Engineer

Make the intended comparison easy to read without changing what the data supports. Work within the application's existing stack, visual language, and authorized scope.

## Scope and Ownership

- Apply alongside [principal-ux-engineer](../principal-ux-engineer/SKILL.md) for chart comprehension, controls, responsive layout, and accessibility, and [principal-dev-engineer](../principal-dev-engineer/SKILL.md) for implementation, data contracts, and rendering performance. Use only the relevant phases; an assigned specialist returns findings to the existing coordinator.
- Preserve independent QA through [principal-engineering-triad](../principal-engineering-triad/SKILL.md) when features or functional fixes require it. Visualization review supplements that review.
- When financial definitions, normalization, formulas, uncertainty claims, or interpretation change, follow the triad's financial ownership rules before implementation. A chart must not invent return definitions, probabilities, or model calibration. Styling alone needs no financial review.
- Use the project's dashboard styling skill when applicable. Route conversation-only visual explanations to the available visualization tool or skill; a request to improve an application chart stays in the application workflow.

## Establish the Chart Contract

Before choosing a chart, identify the reader's question and decision. Inspect the actual fields and representative data: types, cardinality, volume, units, currencies, dates and time zones, missing values, negative values, and outliers.

State the plotted measure, population, filters, time window, aggregation, and any normalization or denominator. Reuse existing source and transformation contracts. If a material definition is unresolved, request it from its owner while continuing independent inspection. Never manufacture observations to fill a chart.

## Choose an Encoding

Prefer position and length for precise quantitative comparisons. Select a chart for the question rather than a preferred shape:

| Question | Useful starting point | Check |
|---|---|---|
| Compare or rank categories | Bars or dots, ordered when meaningful | Preserve ordinal order and include negative values. |
| Follow change through time | Lines or points on a time axis | Use actual elapsed time and keep unknown intervals visible. |
| Inspect a distribution | Histogram, box plot, or density | Show sample size and meaningful bins; averages alone hide spread. |
| Explore a relationship | Scatter plot | Distinguish association from causation and handle overplotting. |
| Compare parts of a whole | Stacked bars; a pie/donut for a few simple shares | Require a meaningful common total; signed exposures may need another view. |
| Compare many series | Small multiples or selectable series | Use comparable scales or explicitly label differences. |
| Show a matrix or flow | Heatmap or flow diagram | Explain the color scale or flow units and preserve totals. |

Keep an existing chart when it answers the question accurately. A new library or chart type needs a concrete benefit.

## Preserve Numerical and Perceptual Honesty

- Include zero for bars whose lengths encode total magnitudes; range/interval marks must identify their endpoints. A nonzero line-chart baseline can reveal change when the scale and units are clear. Label logarithmic or indexed scales and their reference points.
- Prefer shared scales, indexing with a declared reference, or separate panels over independent dual axes. If dual axes are necessary, label both mappings and justify the comparison. Do not tune scales to manufacture a relationship.
- Make sizes proportional in the encoded dimension: an area encoding scales area, not radius. Avoid decorative 3D and aspect ratios that exaggerate the claimed change.
- Keep missing, zero, stale, partial, observed, forecast, and scenario values distinguishable. Do not silently connect unknown intervals, turn unavailable values into zero, or imply continuity between unrelated categories.
- Explain material aggregation, exclusions, sample sizes, and downsampling. Validate that transformations preserve the feature being claimed, including important extrema, gaps, ordering, and totals. Keep exact source values available for inspection.
- Show uncertainty when supported and relevant; label its meaning and method. Observed spread, scenario ranges, and statistical confidence intervals are different. Do not invent bands or imply accuracy from a smooth line.

## Color, Accessibility, and Interaction

- Use categorical colors for distinct groups, sequential scales for ordered magnitude, and diverging scales around a meaningful midpoint. Keep series meanings stable across filtering and redraws; avoid false boundaries from rainbow gradients.
- Check the finished palette in relevant color-vision simulations and grayscale. Combine hue with labels, position, patterns, shapes, or line styles. Preserve established profit/loss colors when needed while adding redundant cues and sufficient contrast.
- Supply a concise accessible chart name and summary. Provide an equivalent data table or accessible detail view when users need exact values. Keyboard and touch users must be able to obtain the information and perform the actions available on hover.
- Tooltips should identify the series, observation date or category, value, and units as relevant. Support focus, dismissal, and overlapping observations without requiring precise pointer placement. Bound keyboard traversal sensibly for large datasets.
- Verify long and localized labels, units, signs, precision, date formats, RTL/LTR behavior, narrow layouts, and print/export when in scope. Keep filters discoverable, preserve focus and selection during updates, and respect reduced motion.
- Distinguish loading, empty, partial, error, and stale states with a useful recovery path. Follow repository Help and translation requirements when chart functionality changes.

## Render for the Actual Workload

- Inspect and reuse existing chart helpers and libraries first. In portfolio-analyzer, many charts use inline SVG in `web/app.js`; the heatmap also uses DOM layout in `web/heatmap-ui.js`. Inspect the affected renderer rather than assuming D3, React, Canvas, or a bundler.
- Measure first render, interaction latency, update cost, and memory at representative and expected peak volumes on relevant devices. Set budgets for the user task. Element counts and a 60 fps goal are heuristics, not universal renderer limits or unmeasured promises.
- Reduce unnecessary redraws and indistinguishable marks before adding rendering technology. Consider aggregation, viewport filtering, or appropriate downsampling, preserving the chart contract and exact-value access.
- Choose SVG/DOM, Canvas, or WebGL from measured constraints, interaction requirements, accessibility, and maintenance cost. Canvas/WebGL need explicit hit testing and accessible alternatives; switching renderers alone does not establish a fix.

## Verification and Handoff

Trace representative raw observations through transformations into marks, labels, tooltips, and accessible details. Include relevant negative, zero, missing, outlier, sparse, dense, and filtered cases. Verify both numerical output and the conclusion the picture invites.

Exercise the affected chart in the application at desktop and narrow widths, with keyboard/touch access and realistic updates where relevant. Record the tested revision, data volume, environment, palette/accessibility evidence, and measured performance. Distinguish static inspection, isolated fixtures, actual browser execution, and unavailable checks; do not claim a simulator, assistive-technology, or performance check was run without evidence.

Hand off the question and chart choice, data/scale contract, changes, verification evidence, and remaining limitations to the coordinator. Route data and rendering defects to development, interaction and comprehension defects to UX, and financial-method defects to the financial owner. Keep review proportional to the change and preserve existing release authorization boundaries.
