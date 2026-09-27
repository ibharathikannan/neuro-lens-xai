import { Component, computed, input } from '@angular/core';

import { CLASS_LABELS, ReviewStatus, TumorClass, classLabel } from '../models';

/** Coloured chip for a tumor class, e.g. "Glioma". */
@Component({
  selector: 'app-class-chip',
  template: `<span [class]="'chip ' + (known() ? 'c-' + value() : 'c-info')">{{ label() }}</span>`,
})
export class ClassChip {
  readonly value = input.required<TumorClass>();
  protected readonly label = computed(() => classLabel(this.value()));
  protected readonly known = computed(() => this.value() in CLASS_LABELS);
}

/** Chip for a review status. */
@Component({
  selector: 'app-status-chip',
  template: `<span [class]="'chip ' + css()">{{ value() }}</span>`,
})
export class StatusChip {
  readonly value = input.required<ReviewStatus | string>();
  protected readonly css = computed(() =>
    ({ Reviewed: 'c-ok', Flagged: 'c-danger', 'Awaiting review': 'c-warn' } as Record<string, string>)[this.value()] ?? 'c-info');
}
