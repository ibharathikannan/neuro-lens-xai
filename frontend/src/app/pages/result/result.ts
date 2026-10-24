import { Component, computed, effect, inject, input, signal, untracked } from '@angular/core';
import { PercentPipe } from '@angular/common';
import { RouterLink } from '@angular/router';

import { ApiService } from '../../service';
import { classColor, classLabel, Scan, Study, TumorClass } from '../../models';
import { ClassChip, StatusChip, TypeChip } from '../../shared/chips';
import { MriImage } from '../../shared/mri-image';
import { Icon } from '../../shared/icon';

const sorted = (p: Record<TumorClass, number>) => (Object.entries(p) as [TumorClass, number][]).sort((a, b) => b[1] - a[1]);

/** Result of one scan. For a slice of a multi-slice study the page has two rows: (1) the overall result, averaged over
 *  every slice, with all slices shown together; (2) the selected slice with its own heatmap, explanation and prediction. */
@Component({
  selector: 'app-result',
  imports: [RouterLink, PercentPipe, ClassChip, StatusChip, MriImage, Icon, TypeChip],
  templateUrl: './result.html',
  styles: `
    .layout { grid-template-columns: 1.35fr 1fr; align-items: start; }
    .big { font-size: 26px; font-weight: 700; }
    .section { display: flex; align-items: center; flex-wrap: wrap; gap: 10px; margin: 6px 0 12px; font-size: 17px; font-weight: 700; }
    .section .step { display: inline-grid; place-items: center; width: 26px; height: 26px; border-radius: 50%;
                     background: var(--navy); color: #fff; font-size: 13px; }
    .section .sub { font-weight: 400; font-size: 13px; color: var(--muted); }
    .overall { grid-template-columns: 1.7fr 1fr; gap: 28px; align-items: start; }
    .gallery { display: grid; grid-template-columns: repeat(auto-fill, minmax(104px, 1fr)); gap: 10px; margin-top: 12px; }
    .col { display: block; color: inherit; text-decoration: none; border-radius: 10px; padding: 6px;
           box-shadow: inset 0 0 0 1px var(--line); text-align: center; }
    .col:hover { box-shadow: inset 0 0 0 1px var(--navy); }
    .col.current { box-shadow: 0 0 0 2px var(--navy); }
    .col.off { background: #fffaf3; }
    .col img { display: block; width: 100%; aspect-ratio: 1; object-fit: cover; border-radius: 6px; background: #000; margin-top: 6px; }
    .col .small { line-height: 1.35; }
    .dot { display: inline-block; width: 7px; height: 7px; border-radius: 50%; margin-right: 4px; }
    .tabs { display: flex; gap: 6px; flex-wrap: wrap; margin-left: auto; }
    .tabs a { padding: 5px 12px; border-radius: 999px; font-size: 13px; font-weight: 600; text-decoration: none;
              color: var(--navy); box-shadow: inset 0 0 0 1px var(--line-strong); background: #fff; }
    .tabs a.current { background: var(--navy); color: #fff; box-shadow: none; }
    @media (max-width: 1100px) { .layout, .overall { grid-template-columns: 1fr; } }
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

  /** Each slice's score for the overall class: the overall score is their average. */
  protected readonly sliceScores = computed(() => {
    const st = this.study();
    return st ? st.slices.map((x) => x.probabilities[st.prediction] ?? 0) : [];
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
