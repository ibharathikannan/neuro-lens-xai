import { Component, OnInit, inject, input, signal } from '@angular/core';
import { PercentPipe } from '@angular/common';
import { RouterLink } from '@angular/router';

import { ApiService } from '../../service';
import { PatientDetail } from '../../models';
import { ClassChip, StatusChip } from '../../shared/chips';
import { MriImage } from '../../shared/mri-image';

@Component({
  selector: 'app-patient-detail',
  imports: [RouterLink, PercentPipe, ClassChip, StatusChip, MriImage],
  templateUrl: './patient-detail.html',
  styles: `
    .layout { grid-template-columns: 320px 1fr; }
    .timeline { position: relative; padding-left: 22px; }
    .timeline:before { content: ""; position: absolute; left: 6px; top: 4px; bottom: 4px; width: 2px; background: var(--line); }
    .tl { position: relative; margin-bottom: 16px; }
    .tl:before { content: ""; position: absolute; left: -21px; top: 4px; width: 12px; height: 12px; border-radius: 50%; background: #fff; border: 3px solid var(--blue); }
    .avatar-lg { width: 52px; height: 52px; border-radius: 50%; background: var(--sky); color: var(--navy); display: grid; place-items: center; font-weight: 700; font-size: 18px; }
    @media (max-width: 1000px) { .layout { grid-template-columns: 1fr; } }
  `,
})
export class PatientDetailPage implements OnInit {
  private readonly api = inject(ApiService);
  /** Route parameter :id (bound by withComponentInputBinding). */
  readonly id = input.required<string>();

  protected readonly patient = signal<PatientDetail | null>(null);
  protected readonly error = signal('');

  ngOnInit(): void {
    this.api.getPatient(this.id()).subscribe({
      next: (p) => this.patient.set(p),
      error: (e: Error) => this.error.set(e.message),
    });
  }
}
