import { Component, inject, signal } from '@angular/core';
import { DatePipe } from '@angular/common';
import { AbstractControl, FormBuilder, ReactiveFormsModule, ValidationErrors, Validators } from '@angular/forms';

import { ApiService } from '../../service';

/** Same rule as the backend: at least 8 characters with a letter and a number. */
function strongPassword(c: AbstractControl): ValidationErrors | null {
  const v = String(c.value ?? '');
  return /[A-Za-z]/.test(v) && /\d/.test(v) ? null : { weak: true };
}

function passwordsMatch(group: AbstractControl): ValidationErrors | null {
  return group.get('new_password')?.value === group.get('confirm')?.value ? null : { mismatch: true };
}

@Component({
  selector: 'app-account',
  imports: [ReactiveFormsModule, DatePipe],
  templateUrl: './account.html',
  styles: `
    .layout { grid-template-columns: 1fr 1.2fr; align-items: start; }
    form { max-width: 440px; }
    @media (max-width: 1000px) { .layout { grid-template-columns: 1fr; } }
  `,
})
export class Account {
  protected readonly api = inject(ApiService);

  protected readonly form = inject(FormBuilder).nonNullable.group({
    current_password: ['', [Validators.required]],
    new_password: ['', [Validators.required, Validators.minLength(8), Validators.maxLength(128), strongPassword]],
    confirm: ['', [Validators.required]],
  }, { validators: passwordsMatch });

  protected readonly saving = signal(false);
  protected readonly error = signal('');
  protected readonly done = signal(false);

  protected invalid(name: 'current_password' | 'new_password' | 'confirm'): boolean {
    const c = this.form.controls[name];
    const mismatch = name === 'confirm' && this.form.hasError('mismatch');
    return (c.invalid || mismatch) && (c.touched || c.dirty);
  }

  protected submit(): void {
    if (this.form.invalid) {
      this.form.markAllAsTouched();
      return;
    }
    const { current_password, new_password } = this.form.getRawValue();
    this.saving.set(true);
    this.error.set('');
    this.done.set(false);
    this.api.changePassword({ current_password, new_password }).subscribe({
      next: () => {
        this.saving.set(false);
        this.done.set(true);
        this.form.reset();
      },
      error: (e: Error) => {
        this.error.set(e.message);
        this.saving.set(false);
      },
    });
  }
}
