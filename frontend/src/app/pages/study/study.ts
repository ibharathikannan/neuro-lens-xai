import { Component, OnInit, computed, inject, input, signal } from '@angular/core';
import { PercentPipe } from '@angular/common';
import { RouterLink } from '@angular/router';

import { ApiService } from '../../service';
import { classColor, classLabel, Study, TumorClass } from '../../models';
import { ClassChip, StatusChip } from '../../shared/chips';
import { MriImage } from '../../shared/mri-image';
import { Icon } from '../../shared/icon';

/** Result of a multi-slice study: the combined prediction plus every slice with its own heatmap. */
@Component({
  selector: 'app-study',
  imports: [RouterLink, PercentPipe, ClassChip, StatusChip, MriImage, Icon],
  templateUrl: './study.html',
  styles: `
    .layout { grid-template-columns: 1fr 1.6fr; align-items: start; }
    .big { font-size: 26px; font-weight: 700; }
    .slices { grid-template-columns: repeat(auto-fill, minmax(250px, 1fr)); gap: 14px; }
    .slice { border: 1px solid var(--line); border-radius: 10px; padding: 12px; }
    .slice.off { border-color: #f0c9a0; background: #fffaf3; }
    .pair { display: flex; gap: 8px; margin: 8px 0; }
    @media (max-width: 1100px) { .layout { grid-template-columns: 1fr; } }
  `,
})
export class StudyPage implements OnInit {
  private readonly api = inject(ApiService);
  readonly id = input.required<string>();

  protected readonly study = signal<Study | null>(null);
  protected readonly error = signal('');
  protected readonly info = signal('');
  protected readonly busy = signal(false);
  protected readonly label = classLabel;
  protected readonly color = classColor;

  protected readonly probabilities = computed(() => {
    const s = this.study();
    if (!s) return [];
    return (Object.entries(s.probabilities) as [TumorClass, number][]).sort((a, b) => b[1] - a[1]);
  });

  /** True when every slice predicts the combined class. */
  protected readonly allAgree = computed(() => {
    const s = this.study();
    return !!s && s.slices.every((x) => x.prediction === s.prediction);
  });

  ngOnInit(): void {
    this.api.getStudy(this.id()).subscribe({
      next: (s) => this.study.set(s),
      error: (e: Error) => this.error.set(e.message),
    });
  }

  protected download(): void {
    this.api.downloadStudyReport(this.id()).subscribe({
      next: (done) => { if (!done) this.info.set('Demo data mode: reports can be downloaded when connected to the backend.'); },
      error: (e: Error) => this.error.set(e.message),
    });
  }

  protected markReviewed(): void {
    this.busy.set(true);
    this.api.markStudyReviewed(this.id()).subscribe({
      next: (s) => { this.study.set(s); this.busy.set(false); },
      error: (e: Error) => { this.error.set(e.message); this.busy.set(false); },
    });
  }
}
