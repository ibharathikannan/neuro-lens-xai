import { Component, OnInit, inject, input, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { Router } from '@angular/router';

import { ApiService } from '../../service';
import { Patient } from '../../models';

const MAX_MB = 10;

@Component({
  selector: 'app-new-scan',
  imports: [ReactiveFormsModule],
  templateUrl: './new-scan.html',
  styles: `
    .layout { grid-template-columns: 1fr 1.3fr; }
    .steps { display: flex; gap: 8px; margin-bottom: 18px; }
    .step { flex: 1; padding: 10px 12px; border-radius: 8px; background: #fff; border: 1px solid var(--line); font-size: 12px; color: var(--muted); }
    .step.done { border-color: #bfe0cc; background: #f1faf5; color: var(--ok); }
    .step.now { border-color: #9fb9e2; background: var(--sky); color: var(--navy); font-weight: 600; }
    .dropzone { border: 2px dashed #b9c7df; border-radius: 12px; background: #f8fafe; padding: 30px; text-align: center; color: var(--muted); flex: 1;
                display: flex; flex-direction: column; justify-content: center; gap: 6px; cursor: pointer; }
    .dropzone.over { border-color: var(--navy); background: var(--sky); }
    .preview { width: 210px; height: 210px; object-fit: cover; border-radius: 10px; background: #000; display: block; }
    @media (max-width: 1000px) { .layout { grid-template-columns: 1fr; } }
  `,
})
export class NewScan implements OnInit {
  private readonly api = inject(ApiService);
  private readonly router = inject(Router);
  /** Optional ?patient= query parameter (from the patient detail page). */
  readonly patient = input<string>();

  protected readonly patients = signal<Patient[]>([]);
  protected readonly file = signal<File | null>(null);
  protected readonly preview = signal<string | null>(null);
  protected readonly dragOver = signal(false);
  protected readonly running = signal(false);
  protected readonly error = signal('');

  protected readonly form = inject(FormBuilder).nonNullable.group({
    patient_id: ['', Validators.required],
    scan_date: [new Date().toISOString().slice(0, 10), Validators.required],
    sequence: ['T1-weighted, contrast-enhanced', Validators.required],
    notes: [''],
  });

  ngOnInit(): void {
    this.api.getPatients().subscribe({
      next: (list) => {
        this.patients.set(list);
        const wanted = this.patient();
        this.form.controls.patient_id.setValue(wanted && list.some((p) => p.id === wanted) ? wanted : list[0]?.id ?? '');
      },
      error: (e: Error) => this.error.set(e.message),
    });
  }

  protected step(): number {
    if (this.running()) return 3;
    return this.file() ? 3 : this.form.controls.patient_id.value ? 2 : 1;
  }

  protected onFileInput(event: Event): void {
    const f = (event.target as HTMLInputElement).files?.[0];
    if (f) this.setFile(f);
  }

  protected onDrop(event: DragEvent): void {
    event.preventDefault();
    this.dragOver.set(false);
    const f = event.dataTransfer?.files?.[0];
    if (f) this.setFile(f);
  }

  private setFile(f: File): void {
    this.error.set('');
    if (!['image/jpeg', 'image/png'].includes(f.type)) {
      this.error.set('Please choose a JPG or PNG image.');
      return;
    }
    if (f.size > MAX_MB * 1024 * 1024) {
      this.error.set(`The image is larger than ${MAX_MB} MB.`);
      return;
    }
    this.file.set(f);
    const reader = new FileReader();
    reader.onload = () => this.preview.set(reader.result as string);
    reader.readAsDataURL(f);
  }

  protected run(): void {
    const f = this.file();
    if (this.form.invalid || !f) {
      this.form.markAllAsTouched();
      if (!f) this.error.set('Please upload an MRI image first.');
      return;
    }
    this.running.set(true);
    this.error.set('');
    this.api.classifyScan({ ...this.form.getRawValue(), file: f }).subscribe({
      next: (scan) => this.router.navigate(['/scans', scan.id]),
      error: (e: Error) => {
        this.error.set(e.message);
        this.running.set(false);
      },
    });
  }
}
