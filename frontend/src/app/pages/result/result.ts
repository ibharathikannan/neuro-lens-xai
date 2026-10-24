import { Component, computed, effect, inject, input, signal, untracked } from '@angular/core';
import { PercentPipe } from '@angular/common';
import { RouterLink } from '@angular/router';

import { ApiService } from '../../service';
import { classColor, classLabel, Scan, Study, TumorClass } from '../../models';
import { ClassChip, StatusChip, TypeChip } from '../../shared/chips';
import { MriImage } from '../../shared/mri-image';
import { Icon } from '../../shared/icon';

const sorted = (p: Record<TumorClass, number>) => (Object.entries(p) as [TumorClass, number][]).sort((a, b) => b[1] - a[1]);

/** Result of one scan. For a slice of a multi-slice study the same page also shows the combined result and a strip of
 *  every slice; picking a slice swaps the heatmap and prediction below it. */
@Component({
  selector: 'app-result',
  imports: [RouterLink, PercentPipe, ClassChip, StatusChip, MriImage, Icon, TypeChip],
  templateUrl: './result.html',
  styles: `
    .layout { grid-template-columns: 1.35fr 1fr; align-items: start; }
    .combo { grid-template-columns: minmax(280px, 1fr) 1.6fr; gap: 28px; align-items: start; margin-top: 14px; }
    .big { font-size: 26px; font-weight: 700; }
    .strip { display: flex; gap: 10px; flex-wrap: wrap; padding: 2px; }
    .thumb { flex: none; display: block; text-align: center; color: inherit; text-decoration: none; border-radius: 10px;
             padding: 5px; box-shadow: inset 0 0 0 1px var(--line-strong); }
    .thumb:hover { box-shadow: inset 0 0 0 1px var(--navy); }
    .thumb.current { box-shadow: 0 0 0 2px var(--navy); }
    .thumb.off { background: #fffaf3; box-shadow: inset 0 0 0 1px #f0c9a0; }
    .thumb.off.current { box-shadow: 0 0 0 2px var(--navy); }
    .thumb img { display: block; width: 96px; height: 96px; object-fit: cover; border-radius: 7px; background: #000; }
    .thumb .small { margin-top: 4px; line-height: 1.3; }
    .dot { display: inline-block; width: 7px; height: 7px; border-radius: 50%; margin-right: 4px; }
    @media (max-width: 1100px) { .layout, .combo { grid-template-columns: 1fr; } }
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
    return s ? sorted(s.probabilities) : [];
  });

  protected readonly studyProbabilities = computed(() => {
    const st = this.study();
    return st ? sorted(st.probabilities) : [];
  });

  /** True when every slice predicts the combined class. */
  protected readonly allAgree = computed(() => {
    const st = this.study();
    return !!st && st.slices.every((x) => x.prediction === st.prediction);
  });

  constructor() {
    // Runs again when the route moves to another slice (Angular reuses this component).
    effect(() => {
      const id = this.id();
      this.error.set('');
      const known = untracked(this.study)?.slices.find((x) => x.id === id);   // only `id` re-runs this
      if (known) { this.scan.set(known); return; }                     // switching slices: already loaded with the study
      this.scan.set(null);
      this.api.getScan(id).subscribe({
        next: (s) => {
          if (!s.study_id) { this.study.set(null); this.scan.set(s); return; }
          this.api.getStudy(s.study_id).subscribe({
            next: (st) => { this.study.set(st); this.scan.set(s); },
            error: (e: Error) => this.error.set(e.message),
          });
        },
        error: (e: Error) => this.error.set(e.message),
      });
    });
  }

  protected download(): void {
    const s = this.scan();
    if (!s) return;
    this.report(this.api.downloadReport(s.id));
  }

  protected downloadStudy(): void {
    const st = this.study();
    if (st) this.report(this.api.downloadStudyReport(st.id));
  }

  private report(download: ReturnType<ApiService['downloadReport']>): void {
    download.subscribe({
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

  /** Reviewing a study confirms the combined class for all its slices. */
  protected markStudyReviewed(): void {
    const st = this.study();
    if (!st) return;
    this.busy.set(true);
    this.api.markStudyReviewed(st.id).subscribe({
      next: (updated) => {
        this.study.set(updated);
        this.scan.set(updated.slices.find((x) => x.id === this.id()) ?? this.scan());
        this.busy.set(false);
      },
      error: (e: Error) => { this.error.set(e.message); this.busy.set(false); },
    });
  }
}
