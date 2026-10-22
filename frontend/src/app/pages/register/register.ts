import { Component, inject, signal } from '@angular/core';
import { AbstractControl, FormBuilder, ReactiveFormsModule, ValidationErrors, Validators } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';

import { ApiService } from '../../service';
import { AuthAside } from '../../shared/auth-aside';
import { Icon } from '../../shared/icon';

/** Same rule as the backend: at least 8 characters with a letter and a number. */
function strongPassword(c: AbstractControl): ValidationErrors | null {
  const v = String(c.value ?? '');
  return /[A-Za-z]/.test(v) && /\d/.test(v) ? null : { weak: true };
}

function passwordsMatch(group: AbstractControl): ValidationErrors | null {
  return group.get('password')?.value === group.get('confirm')?.value ? null : { mismatch: true };
}

@Component({
  selector: 'app-register',
  imports: [ReactiveFormsModule, RouterLink, AuthAside, Icon],
  templateUrl: './register.html',
  styleUrl: '../auth-layout.scss',
})
export class Register {
  private readonly api = inject(ApiService);
  private readonly router = inject(Router);

  protected readonly form = inject(FormBuilder).nonNullable.group({
    full_name: ['', [Validators.required, Validators.minLength(2), Validators.maxLength(100)]],
    email: ['', [Validators.required, Validators.email]],
    password: ['', [Validators.required, Validators.minLength(8), Validators.maxLength(128), strongPassword]],
    confirm: ['', [Validators.required]],
  }, { validators: passwordsMatch });

  protected readonly loading = signal(false);
  protected readonly error = signal('');
  protected readonly showPassword = signal(false);

  protected invalid(name: 'full_name' | 'email' | 'password' | 'confirm'): boolean {
    const c = this.form.controls[name];
    const mismatch = name === 'confirm' && this.form.hasError('mismatch');
    return (c.invalid || mismatch) && (c.touched || c.dirty);
  }

  protected submit(): void {
    if (this.form.invalid) {
      this.form.markAllAsTouched();
      return;
    }
    const { full_name, email, password } = this.form.getRawValue();
    this.loading.set(true);
    this.error.set('');
    this.api.register({ full_name: full_name.trim(), email, password }).subscribe({
      next: () => this.router.navigateByUrl('/dashboard'),
      error: (e: Error) => {
        this.error.set(e.message);
        this.loading.set(false);
      },
    });
  }
}
