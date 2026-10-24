import { Component, OnInit, inject, input, signal } from '@angular/core';
import { Router } from '@angular/router';

import { ApiService } from '../../service';

/** A multi-slice study has no page of its own: its combined result is shown on the result page of every slice,
 *  so /studies/:id (old links, Word reports) opens the study's first slice. */
@Component({
  selector: 'app-study',
  template: `@if (error()) { <div class="alert alert-error">{{ error() }}</div> } @else { <div class="state"><span class="spinner"></span></div> }`,
})
export class StudyPage implements OnInit {
  private readonly api = inject(ApiService);
  private readonly router = inject(Router);
  readonly id = input.required<string>();
  protected readonly error = signal('');

  ngOnInit(): void {
    this.api.getStudy(this.id()).subscribe({
      next: (st) => this.router.navigate(['/scans', st.slices[0].id], { replaceUrl: true }),
      error: (e: Error) => this.error.set(e.message),
    });
  }
}
