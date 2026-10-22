import { Component, OnInit, computed, inject, input, signal } from '@angular/core';
import { PercentPipe } from '@angular/common';
import { RouterLink } from '@angular/router';

import { ApiService } from '../../service';
import { classColor, classLabel, Scan, TumorClass } from '../../models';
import { ClassChip, StatusChip } from '../../shared/chips';
import { MriImage } from '../../shared/mri-image';
import { Icon } from '../../shared/icon';

@Component({
  selector: 'app-result',
  imports: [RouterLink, PercentPipe, ClassChip, StatusChip, MriImage, Icon],
  templateUrl: './result.html',
  styles: `
    .layout { grid-template-columns: 1.35fr 1fr; align-items: start; }
    .big { font-size: 26px; font-weight: 700; }
    @media (max-width: 1100px) { .layout { grid-template-columns: 1fr; } }
  `,
})
export class Result implements OnInit {
  private readonly api = inject(ApiService);
  readonly id = input.required<string>();

  protected readonly scan = signal<Scan | null>(null);
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

  ngOnInit(): void {
    this.api.getScan(this.id()).subscribe({
      next: (s) => this.scan.set(s),
      error: (e: Error) => this.error.set(e.message),
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
