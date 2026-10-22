import { Component, OnInit, inject, signal } from '@angular/core';
import { DatePipe } from '@angular/common';
import { AbstractControl, FormBuilder, ReactiveFormsModule, ValidationErrors, Validators } from '@angular/forms';

import { ApiService } from '../../service';
import { User, UserUpdate } from '../../models';
import { Icon } from '../../shared/icon';

/** Same rule as the backend: at least 8 characters with a letter and a number. */
function strongPassword(c: AbstractControl): ValidationErrors | null {
  const v = String(c.value ?? '');
  return /[A-Za-z]/.test(v) && /\d/.test(v) ? null : { weak: true };
}

/** Administrators add team members and disable accounts (works while self-registration is switched off). */
@Component({
  selector: 'app-users',
  imports: [ReactiveFormsModule, DatePipe, Icon],
  templateUrl: './users.html',
  styles: `
    .add { grid-template-columns: 1.2fr 1.4fr 1fr 150px; align-items: start; }
    .actions { display: flex; gap: 8px; justify-content: flex-end; }
    .actions .btn { padding: 6px 10px; font-size: 12px; }
    @media (max-width: 1000px) { .add { grid-template-columns: 1fr; } }
  `,
})
export class Users implements OnInit {
  protected readonly api = inject(ApiService);

  protected readonly users = signal<User[] | null>(null);
  protected readonly error = signal('');
  protected readonly adding = signal(false);
  protected readonly saving = signal(false);
  protected readonly addError = signal('');
  protected readonly registrationOpen = signal<boolean | null>(null);

  protected readonly form = inject(FormBuilder).nonNullable.group({
    full_name: ['', [Validators.required, Validators.minLength(2), Validators.maxLength(100)]],
    email: ['', [Validators.required, Validators.email]],
    password: ['', [Validators.required, Validators.minLength(8), Validators.maxLength(128), strongPassword]],
    role: ['clinician' as 'admin' | 'clinician'],
  });

  ngOnInit(): void {
    this.load();
    this.api.getAuthSettings().subscribe({ next: (s) => this.registrationOpen.set(s.allow_registration), error: () => undefined });
  }

  protected invalid(name: 'full_name' | 'email' | 'password'): boolean {
    const c = this.form.controls[name];
    return c.invalid && (c.touched || c.dirty);
  }

  protected isMe(u: User): boolean {
    return u.id === this.api.currentUser()?.id;
  }

  protected add(): void {
    if (this.form.invalid) {
      this.form.markAllAsTouched();
      return;
    }
    const v = this.form.getRawValue();
    this.saving.set(true);
    this.addError.set('');
    this.api.createUser({ ...v, full_name: v.full_name.trim() }).subscribe({
      next: (u) => {
        this.users.update((list) => [...(list ?? []), u]);
        this.form.reset();
        this.adding.set(false);
        this.saving.set(false);
      },
      error: (e: Error) => {
        this.addError.set(e.message);
        this.saving.set(false);
      },
    });
  }

  protected update(u: User, change: UserUpdate): void {
    this.error.set('');
    this.api.updateUser(u.id, change).subscribe({
      next: (updated) => this.users.update((list) => (list ?? []).map((x) => (x.id === updated.id ? updated : x))),
      error: (e: Error) => this.error.set(e.message),
    });
  }

  private load(): void {
    this.api.getUsers().subscribe({
      next: (list) => this.users.set(list),
      error: (e: Error) => this.error.set(e.message),
    });
  }
}
