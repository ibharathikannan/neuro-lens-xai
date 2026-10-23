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

/** Tells single-slice scans apart from multi-slice studies: "Single slice", "Multi-slice · slice 2" (one slice of a
 *  study) or, with `count`, "Multi-slice · 5 slices" (the study itself). */
@Component({
  selector: 'app-type-chip',
  template: `<span [class]="'chip ' + (multi() ? 'c-multi' : 'c-single')" [title]="title()">{{ label() }}</span>`,
})
export class TypeChip {
  readonly studyId = input<string | null | undefined>(null);
  readonly slice = input<number | null | undefined>(null);
  readonly count = input<number | null | undefined>(null);
  protected readonly multi = computed(() => !!this.studyId() || !!this.count());
  protected readonly label = computed(() =>
    this.count() ? `Multi-slice · ${this.count()} slices`
      : this.studyId() ? `Multi-slice · slice ${this.slice() ?? '?'}` : 'Single slice');
  protected readonly title = computed(() =>
    this.count() ? `Multi-slice study of ${this.count()} slices from one scan`
      : this.studyId() ? `Slice ${this.slice() ?? '?'} of multi-slice study ${this.studyId()}` : 'Single-slice scan');
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
