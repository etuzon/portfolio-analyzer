# Portfolio Analyzer: active formula

The implemented model is `report-outlook-v5`. Its maintained formula, financial
input rules, missing-data behavior, frozen evaluation contract, validation gate
and regression entry points are in the repository skill:

[Company outlook model](/etuzon/projects/ai/portfolio-analyzer/.agents/skills/company-outlook-model/SKILL.md)

Read that source before a recheck or model change and keep it aligned with code.
It is versioned with the implementation. Industry and related-company reports
are context; financial evidence alone supplies the new score. Incomplete or
unsupported evidence remains unscored instead of becoming a directional forecast.

[Archived v4 formula and audit](portfolio-analyzer-formula-v4.md) describes the
previous model and the counterexamples that led to this correction. Old saved
predictions retain their values and earlier evaluation algorithm. The prior
40/100 methodology assessment is an audit judgment about v4; it is not v5
forecast accuracy. No real-company prospective accuracy is claimed for v5.
