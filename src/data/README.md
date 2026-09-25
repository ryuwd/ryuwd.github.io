# Chart data

Drop a JSON file here and reference it from a page with
`<ProjectChart name="<filename-without-extension>" />`. The chart renders at
build time to plain SVG; while the file is absent the component renders
nothing, so pages can be wired up before the data exists.

Format:

```json
{
  "title": "Analysis Productions input processed",
  "caption": "Cumulative input processed by Analysis Productions.",
  "yLabel": "Input processed (EB)",
  "unit": "EB",
  "series": [
    { "date": "2024-11-01", "value": 0.9 },
    { "date": "2026-05-18", "value": 1.57 }
  ]
}
```

- `date` — ISO date string (`YYYY-MM-DD`).
- `value` — number, in the unit named by `unit` / `yLabel`.
- `caption` is optional and appears under the figure.

Expected first export: `ap-growth.json` (Analysis Productions growth from
monitoring / the CHEP 2026 material).
