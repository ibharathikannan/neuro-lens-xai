import { Component, OnInit, inject, input, signal } from '@angular/core';
import { PercentPipe } from '@angular/common';
import { RouterLink } from '@angular/router';

import { ApiService } from '../../service';
import { Scan, SimilarResult } from '../../models';
import { ClassChip } from '../../shared/chips';
import { MriImage } from '../../shared/mri-image';

@Component({
  selector: 'app-similar',
  imports: [RouterLink, PercentPipe, ClassChip, MriImage],
  templateUrl: './similar.html',
  styles: `
    .layout { grid-template-columns: 300px 1fr; }
    .cases { grid-template-columns: repeat(5, 1fr); gap: 12px; margin-top: 16px; }
    .case { border: 1px solid var(--line); border-radius: 10px; padding: 10px; }
    .sim { font-size: 22px; font-weight: 700; color: var(--navy); }
    @media (max-width: 1200px) { .cases { grid-template-columns: repeat(3, 1fr); } }
    @media (max-width: 1000px) { .layout { grid-template-columns: 1fr; } }
  `,
})
export class Similar implements OnInit {
  private readonly api = inject(ApiService);
  /** Scan id from /scans/:id/similar — empty on the /similar menu page. */
  readonly id = input<string>();

  protected readonly result = signal<SimilarResult | null>(null);
  protected readonly recent = signal<Scan[]>([]);
  protected readonly error = signal('');

  ngOnInit(): void {
    const id = this.id();
    if (id) {
      this.api.getSimilarCases(id).subscribe({
        next: (r) => this.result.set(r),
        error: (e: Error) => this.error.set(e.message),
      });
    } else {
      // Opened from the menu: let the user pick a recent scan first
      this.api.getDashboardSummary().subscribe({
        next: (d) => this.recent.set(d.recent),
        error: (e: Error) => this.error.set(e.message),
      });
    }
  }
}
