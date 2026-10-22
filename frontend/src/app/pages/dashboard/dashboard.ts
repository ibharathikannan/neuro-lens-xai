import { Component, computed, inject, signal } from '@angular/core';
import { PercentPipe } from '@angular/common';
import { RouterLink } from '@angular/router';

import { ApiService } from '../../service';
import { DashboardSummary, TumorClass, classColor, classLabel } from '../../models';
import { ClassChip } from '../../shared/chips';
import { Icon } from '../../shared/icon';

@Component({
  selector: 'app-dashboard',
  imports: [RouterLink, ClassChip, PercentPipe, Icon],
  templateUrl: './dashboard.html',
  styles: `
    .kpis { grid-template-columns: repeat(4, 1fr); }
    .charts { grid-template-columns: 1.25fr 1fr; }
    @media (max-width: 1100px) { .kpis { grid-template-columns: repeat(2, 1fr); } .charts { grid-template-columns: 1fr; } }
  `,
})
export class Dashboard {
  private readonly api = inject(ApiService);
  protected readonly data = signal<DashboardSummary | null>(null);
  protected readonly error = signal('');
  protected readonly label = classLabel;
  protected readonly color = (c: TumorClass) => classColor(c, this.order().indexOf(c));
  /** Classes in the order the backend reports them. */
  protected readonly order = computed<TumorClass[]>(() => Object.keys(this.data()?.distribution ?? {}));

  /** Stacked bars for the weekly chart (SVG coordinates). */
  protected readonly bars = computed(() => {
    const d = this.data();
    if (!d) return [];
    const order = this.order();
    const max = Math.max(...d.weekly.map((w) => order.reduce((s, c) => s + (w.counts[c] ?? 0), 0)), 1);
    return d.weekly.map((w, i) => {
      let y = 190;
      const segs = order.map((c) => {
        const h = ((w.counts[c] ?? 0) / max) * 160;
        y -= h;
        return { c, y, h };
      });
      return { x: 58 + i * 62, label: w.week, segs };
    });
  });

  /** Donut segments (stroke-dasharray on a circle with circumference 100). */
  protected readonly donut = computed(() => {
    const d = this.data();
    if (!d) return [];
    let offset = 25;
    return this.order().map((c) => {
      const seg = { c, dash: `${d.distribution[c]} ${100 - d.distribution[c]}`, offset };
      offset -= d.distribution[c];
      return seg;
    });
  });

  constructor() {
    this.api.getDashboardSummary().subscribe({
      next: (d) => this.data.set(d),
      error: (e: Error) => this.error.set(e.message),
    });
  }
}
