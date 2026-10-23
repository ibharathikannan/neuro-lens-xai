import { Component, OnInit, computed, inject, input, signal } from '@angular/core';
import { PercentPipe } from '@angular/common';

import { ApiService } from '../../service';
import { classColor, classLabel, Comparison, TumorClass } from '../../models';
import { ClassChip, TypeChip } from '../../shared/chips';
import { MriImage } from '../../shared/mri-image';

@Component({
  selector: 'app-compare',
  imports: [PercentPipe, ClassChip, MriImage, TypeChip],
  templateUrl: './compare.html',
  styles: `
    .top3 { grid-template-columns: 1fr 250px 1fr; }
    .bottom { grid-template-columns: 1.4fr 1fr; }
    .pair { justify-content: center; gap: 10px; }
    .score { font-size: 40px; font-weight: 800; color: var(--navy); }
    .center { text-align: center; }
    ul { margin: 0; padding-left: 18px; line-height: 1.9; }
    @media (max-width: 1200px) { .top3, .bottom { grid-template-columns: 1fr; } }
  `,
})
export class Compare implements OnInit {
  private readonly api = inject(ApiService);
  readonly id = input.required<string>();
  readonly caseId = input.required<string>();

  protected readonly data = signal<Comparison | null>(null);
  protected readonly error = signal('');
  protected readonly label = classLabel;
  protected readonly color = classColor;

  protected readonly probRows = computed(() => {
    const d = this.data();
    if (!d) return [];
    return (Object.keys(d.query.probabilities) as TumorClass[]).map((c) => ({
      c, query: d.query.probabilities[c], ref: d.reference.probabilities[c],
    }));
  });

  ngOnInit(): void {
    this.api.compareCases(this.id(), this.caseId()).subscribe({
      next: (d) => this.data.set(d),
      error: (e: Error) => this.error.set(e.message),
    });
  }
}
