import { Component, computed, effect, inject, input, signal } from '@angular/core';
import { PercentPipe } from '@angular/common';
import { RouterLink } from '@angular/router';

import { ApiService } from '../../service';
import { classColor, classLabel, Scan, Study, TumorClass } from '../../models';
import { ClassChip, StatusChip, TypeChip } from '../../shared/chips';
import { MriImage } from '../../shared/mri-image';
import { Icon } from '../../shared/icon';

@Component({
  selector: 'app-result',
  imports: [RouterLink, PercentPipe, ClassChip, StatusChip, MriImage, Icon, TypeChip],
  templateUrl: './result.html',
  styles: `
    .layout { grid-template-columns: 1.35fr 1fr; align-items: start; }
    .big { font-size: 26px; font-weight: 700; }
    .strip { display: flex; gap: 10px; overflow-x: auto; padding: 2px; margin-top: 12px; }
    .thumb { flex: none; display: block; text-align: center; color: inherit; text-decoration: none; border-radius: 10px;
             padding: 4px; box-shadow: inset 0 0 0 1px var(--line-strong); opacity: .75; }
    .thumb:hover { opacity: 1; }
    .thumb.current { box-shadow: 0 0 0 2px var(--navy); opacity: 1; }
    .thumb img { display: block; width: 72px; height: 72px; object-fit: cover; border-radius: 7px; background: #000; }
    @media (max-width: 1100px) { .layout { grid-template-columns: 1fr; } }
  `,
})
export class Result {
  private readonly api = inject(ApiService);
  readonly id = input.required<string>();

  protected readonly scan = signal<Scan | null>(null);
  protected readonly study = signal<Study | null>(null);   // the multi-slice study this scan belongs to, if any
  protected readonly error = signal('');
  protected readonly info = signal('');
  protected readonly busy = signal(false);
  protected readonly label = classLabel;
  protected readonly color = classColor;

  protected readonly probabilities = computed(() => {
    const s = this.scan();
    if (!s) return [];
    return (Object.entries(s.probabilities) as [TumorClass, number][]).sort((a, b) => b[1] - a[1]);
  });

  constructor() {
    // Runs again when the route moves to another slice of the same study (Angular reuses this component).
    effect(() => {
      const id = this.id();
      this.scan.set(null);
      this.error.set('');
      this.api.getScan(id).subscribe({
        next: (s) => {
          this.scan.set(s);
          if (!s.study_id) this.study.set(null);
          else if (this.study()?.id !== s.study_id) this.api.getStudy(s.study_id).subscribe({ next: (st) => this.study.set(st) });
        },
        error: (e: Error) => this.error.set(e.message),
      });
    });
  }

  protected download(): void {
    const s = this.scan();
    if (!s) return;
    this.api.downloadReport(s.id).subscribe({
      next: (done) => { if (!done) this.info.set('Demo data mode: reports can be downloaded when connected to the backend.'); },
      error: (e: Error) => this.error.set(e.message),
    });
  }

  protected markReviewed(): void {
    this.busy.set(true);
    this.api.markReviewed(this.id()).subscribe({
      next: (s) => { this.scan.set(s); this.busy.set(false); },
      error: (e: Error) => { this.error.set(e.message); this.busy.set(false); },
    });
  }
}
