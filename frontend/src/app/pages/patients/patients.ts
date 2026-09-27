import { Component, inject, signal } from '@angular/core';
import { FormBuilder, FormsModule, ReactiveFormsModule, Validators } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';

import { ApiService } from '../../service';
import { Patient } from '../../models';
import { ClassChip, StatusChip } from '../../shared/chips';

@Component({
  selector: 'app-patients',
  imports: [RouterLink, FormsModule, ReactiveFormsModule, ClassChip, StatusChip],
  templateUrl: './patients.html',
})
export class Patients {
  private readonly api = inject(ApiService);
  protected readonly router = inject(Router);

  protected readonly patients = signal<Patient[] | null>(null);
  protected readonly error = signal('');
  protected search = '';
  private searchTimer?: ReturnType<typeof setTimeout>;

  protected readonly adding = signal(false);
  protected readonly saving = signal(false);
  protected readonly addError = signal('');
  protected readonly addForm = inject(FormBuilder).nonNullable.group({
    age: [50, [Validators.required, Validators.min(0), Validators.max(120)]],
    sex: ['F' as 'F' | 'M', Validators.required],
    referring_unit: [''],
    notes: [''],
  });

  constructor() {
    this.load();
  }

  protected onSearch(): void {
    clearTimeout(this.searchTimer);
    this.searchTimer = setTimeout(() => this.load(), 300);
  }

  protected addPatient(): void {
    if (this.addForm.invalid) {
      this.addForm.markAllAsTouched();
      return;
    }
    this.saving.set(true);
    this.addError.set('');
    this.api.createPatient(this.addForm.getRawValue()).subscribe({
      next: (p) => {
        this.patients.update((list) => [p, ...(list ?? [])]);
        this.adding.set(false);
        this.saving.set(false);
        this.addForm.reset();
      },
      error: (e: Error) => {
        this.addError.set(e.message);
        this.saving.set(false);
      },
    });
  }

  private load(): void {
    this.error.set('');
    this.api.getPatients(this.search).subscribe({
      next: (p) => this.patients.set(p),
      error: (e: Error) => this.error.set(e.message),
    });
  }
}
