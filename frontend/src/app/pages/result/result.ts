import { Component, computed, effect, inject, input, signal, untracked } from '@angular/core';
import { PercentPipe } from '@angular/common';
import { Router, RouterLink } from '@angular/router';

import { ApiService } from '../../service';
import { classColor, classLabel, Scan, Study, TumorClass } from '../../models';
import { ClassChip, StatusChip, TypeChip } from '../../shared/chips';
import { MriImage } from '../../shared/mri-image';
import { Icon } from '../../shared/icon';

const sorted = (p: Record<TumorClass, number>) => (Object.entries(p) as [TumorClass, number][]).sort((a, b) => b[1] - a[1]);

/** Result of one scan. For a slice of a multi-slice study the page has two rows: (1) a static overview of the overall
 *  result, averaged over every slice, with all slices shown together; (2) one slice at a time, with a slider, showing
 *  its own heatmap, explanation and prediction. */
@Component({
  selector: 'app-result',
  imports: [RouterLink, PercentPipe, ClassChip, StatusChip, MriImage, Icon, TypeChip],
  templateUrl: './result.html',
  host: { '(document:keydown)': 'onKey($event)' },
  styles: `
    .layout { grid-template-columns: 1.35fr 1fr; align-items: start; }
    .big { font-size: 26px; font-weight: 700; }
    .section { display: flex; align-items: center; flex-wrap: wrap; gap: 10px; margin: 6px 0 12px; font-size: 17px; font-weight: 700; }
    .section .step { display: inline-grid; place-items: center; width: 26px; height: 26px; border-radius: 50%;
                     background: var(--navy); color: #fff; font-size: 13px; }
    .section .sub { font-weight: 400; font-size: 13px; color: var(--muted); }
    .overall { grid-template-columns: 1.7fr 1fr; gap: 28px; align-items: start; }
    .gallery { display: flex; flex-wrap: wrap; justify-content: space-between; gap: 10px; margin-top: 12px; }
    .col { flex: 1 1 90px; max-width: 120px; border-radius: 10px; padding: 6px; box-shadow: inset 0 0 0 1px var(--line); text-align: center; }
    .col.off { background: #fffaf3; box-shadow: inset 0 0 0 1px #f0c9a0; }
    .col img { display: block; width: 100%; aspect-ratio: 1; object-fit: cover; border-radius: 6px; background: #000; margin-top: 6px; }
    .col .small { line-height: 1.35; }
    .slider { display: flex; align-items: center; justify-content: center; gap: 12px; margin-top: 14px; }
    .nav { flex: none; width: 38px; height: 38px; border-radius: 50%; border: 0; background: var(--navy); color: #fff;
           font-size: 24px; line-height: 1; cursor: pointer; }
    .nav:disabled { background: var(--line); color: var(--muted); cursor: default; }
    .film { display: flex; justify-content: center; flex-wrap: wrap; gap: 8px; margin-top: 14px; }
    .film a { position: relative; display: block; border-radius: 8px; padding: 3px; box-shadow: inset 0 0 0 1px var(--line-strong); }
    .film a.current { box-shadow: 0 0 0 2px var(--navy); }
    .film img { display: block; width: 54px; height: 54px; object-fit: cover; border-radius: 5px; background: #000; }
    .film span { position: absolute; left: 6px; bottom: 5px; font-size: 11px; font-weight: 700; color: #fff; text-shadow: 0 0 3px #000; }
    .dot { display: inline-block; width: 7px; height: 7px; border-radius: 50%; margin-right: 4px; }
    @media (max-width: 1100px) { .layout, .overall { grid-template-columns: 1fr; } }
  `,
})
export class Result {
  private readonly api = inject(ApiService);
  private readonly router = inject(Router);
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

  /** Neighbouring slices for the slider in row 2 (null at either end). */
  private readonly position = computed(() => this.study()?.slices.findIndex((x) => x.id === this.scan()?.id) ?? -1);
  protected readonly prevId = computed(() => this.study()?.slices[this.position() - 1]?.id ?? null);
  protected readonly nextId = computed(() => this.study()?.slices[this.position() + 1]?.id ?? null);

  protected go(id: string | null): void {
    if (id) this.router.navigate(['/scans', id]);
  }

  protected onKey(e: KeyboardEvent): void {
    const target = e.target as HTMLElement | null;
    if (!this.study() || target?.closest('input, textarea, select')) return;
    if (e.key === 'ArrowLeft') this.go(this.prevId());
    if (e.key === 'ArrowRight') this.go(this.nextId());
  }

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
