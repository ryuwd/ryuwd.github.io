import { JSDOM } from 'jsdom';
import * as Plot from '@observablehq/plot';

// Build-time only: Plot needs a DOM to render, jsdom provides one during
// `astro build`. No JavaScript ships to the browser; pages embed plain SVG.
const { document } = new JSDOM().window;

export interface ChartSeries {
  title: string;
  caption?: string;
  yLabel: string;
  unit?: string;
  series: { date: string; value: number }[];
}

export function renderLineChart(data: ChartSeries): string {
  const points = data.series.map((d) => ({
    date: new Date(d.date),
    value: d.value,
  }));
  const last = points[points.length - 1];
  const sparse = points.length <= 24;

  const plot = Plot.plot({
    document,
    style: { fontSize: '13px', background: 'transparent' },
    width: 720,
    height: 340,
    marginLeft: 48,
    marginRight: 24,
    x: { label: null },
    y: { label: data.yLabel, grid: true, nice: true },
    marks: [
      Plot.ruleY([0], { stroke: 'currentColor', strokeOpacity: 0.3 }),
      Plot.lineY(points, {
        x: 'date',
        y: 'value',
        stroke: 'var(--color-chart)',
        strokeWidth: 2,
        curve: 'monotone-x',
      }),
      // Invisible oversized targets carry native tooltips on every point;
      // visible markers only when the series is sparse enough to read them.
      Plot.dot(points, {
        x: 'date',
        y: 'value',
        r: 8,
        fill: 'transparent',
        stroke: 'none',
        title: (d: { date: Date; value: number }) =>
          `${d.date.toISOString().slice(0, 10)}: ${d.value.toLocaleString('en-GB')}${data.unit ? ` ${data.unit}` : ''}`,
      }),
      ...(sparse
        ? [
            Plot.dot(points, {
              x: 'date',
              y: 'value',
              r: 4,
              fill: 'var(--color-chart)',
              stroke: 'var(--color-bg)',
              strokeWidth: 2,
            }),
          ]
        : []),
      ...(last && sparse
        ? [
            Plot.text([last], {
              x: 'date',
              y: 'value',
              text: (d: { value: number }) =>
                `${d.value.toLocaleString('en-GB')}${data.unit ? ` ${data.unit}` : ''}`,
              dy: -12,
              dx: 4,
              textAnchor: 'end',
              fill: 'currentColor',
              fontWeight: 600,
            }),
          ]
        : []),
    ],
  });

  return plot.outerHTML;
}
