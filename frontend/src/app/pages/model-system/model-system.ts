import { Component, computed, inject, signal } from '@angular/core';
import { DecimalPipe } from '@angular/common';

import { ApiService } from '../../service';
import { ServiceStatus, SystemInfo } from '../../models';
import { Icon } from '../../shared/icon';

@Component({
  selector: 'app-model-system',
  imports: [DecimalPipe, Icon],
  templateUrl: './model-system.html',
  styles: `
    .layout { grid-template-columns: 1.2fr 1fr; }
    .svc { padding: 9px 0; border-bottom: 1px solid var(--line); }
    .svc:last-child { border-bottom: 0; }
    tr.selected td { background: #f1f6fd; }
    @media (max-width: 1000px) { .layout { grid-template-columns: 1fr; } }
  `,
})
export class ModelSystem {
  private readonly api = inject(ApiService);
  protected readonly info = signal<SystemInfo | null>(null);
  protected readonly error = signal('');
  /** Live result of GET /api/health — this part always talks to the real backend. */
  protected readonly health = signal<{ status: string; database: string } | null>(null);
  protected readonly healthError = signal('');

  protected readonly services = computed<ServiceStatus[]>(() => {
    const h = this.health();
    const live: ServiceStatus[] = [
      { name: 'NeuroLens API', detail: 'live check · /api/health', status: h ? 'Healthy' : this.healthError() ? 'Unreachable' : 'Checking…', healthy: !!h },
      { name: 'Database', detail: 'live check · MongoDB', status: h ? (h.database === 'connected' ? 'Connected' : 'Unavailable') : '—', healthy: h?.database === 'connected' },
    ];
    const rest = (this.info()?.services ?? []).filter((s) => !['FastAPI backend', 'NeuroLens API', 'Database'].includes(s.name));
    return [...live, ...rest];
  });

  constructor() {
    this.api.getHealth().subscribe({
      next: (h) => this.health.set(h),
      error: (e: Error) => this.healthError.set(e.message),
    });
    this.api.getSystemInfo().subscribe({
      next: (i) => this.info.set(i),
      error: (e: Error) => this.error.set(e.message),
    });
  }
}
