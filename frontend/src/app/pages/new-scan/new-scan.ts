import { Component, OnInit, inject, input, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { Router } from '@angular/router';

import { ApiService } from '../../service';
import { Patient } from '../../models';
import { Icon } from '../../shared/icon';

const MAX_MB = 10;
const MAX_SLICES = 10;

@Component({
  selector: 'app-new-scan',
  imports: [ReactiveFormsModule, Icon],
  templateUrl: './new-scan.html',
  styles: `
    .layout { grid-template-columns: 1fr 1.3fr; }
    .steps { display: flex; gap: 8px; margin-bottom: 18px; }
    .step { flex: 1; display: flex; align-items: center; gap: 6px; padding: 11px 14px; border-radius: 10px; background: #fff; border: 1px solid var(--line);
            font-size: 12.5px; font-weight: 500; color: var(--muted); box-shadow: var(--shadow-card); }
    .step.done { border-color: #b6dcc6; background: #f2faf6; color: var(--ok); }
    .step.now { border-color: #9dbbe8; background: var(--sky); color: var(--navy); font-weight: 600; box-shadow: 0 0 0 3px rgba(44, 103, 196, .1); }
    .dropzone { border: 2px dashed #b3c4de; border-radius: 14px; background: #f8fafe; padding: 34px 30px; text-align: center; color: var(--muted); flex: 1;
                display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 6px; cursor: pointer; transition: border-color .15s, background-color .15s; }
    .dropzone:hover { border-color: var(--blue); background: #f3f7fd; }
    .dropzone.over { border-color: var(--navy); background: var(--sky); }
    .dz-ico { width: 52px; height: 52px; border-radius: 50%; display: grid; place-items: center; background: var(--sky); color: var(--navy); margin-bottom: 6px; box-shadow: inset 0 0 0 1px var(--sky-2); }
    .preview { width: 210px; height: 210px; object-fit: cover; border-radius: 10px; background: #000; display: block; }
    .thumbs { display: grid; grid-template-columns: repeat(auto-fill, minmax(92px, 1fr)); gap: 10px; margin-top: 14px; }
    .thumb { position: relative; }
    .thumb img { width: 100%; aspect-ratio: 1; object-fit: cover; border-radius: 8px; background: #000; display: block; }
    .thumb button { position: absolute; top: 4px; right: 4px; border: 0; border-radius: 50%; width: 22px; height: 22px;
                    background: rgba(0, 0, 0, .65); color: #fff; cursor: pointer; line-height: 22px; padding: 0; }
    @media (max-width: 1000px) { .layout { grid-template-columns: 1fr; } }
  `,
})
export class NewScan implements OnInit {
  private readonly api = inject(ApiService);
  private readonly router = inject(Router);
  /** Optional ?patient= query parameter (from the patient detail page). */
  readonly patient = input<string>();

  protected readonly patients = signal<Patient[]>([]);
  /** One file = single-slice classification; 2–10 files = a multi-slice study of the same scan. */
  protected readonly files = signal<File[]>([]);
  protected readonly previews = signal<string[]>([]);
  protected readonly maxSlices = MAX_SLICES;
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
    return this.files().length ? 3 : this.form.controls.patient_id.value ? 2 : 1;
  }

  protected onFileInput(event: Event): void {
    const input = event.target as HTMLInputElement;
    this.addFiles(Array.from(input.files ?? []));
    input.value = '';                                   // allow choosing the same file again after removing it
  }

  protected onDrop(event: DragEvent): void {
    event.preventDefault();
    this.dragOver.set(false);
    this.addFiles(Array.from(event.dataTransfer?.files ?? []));
  }

  private addFiles(list: File[]): void {
    this.error.set('');
    for (const f of list) {
      if (!['image/jpeg', 'image/png'].includes(f.type)) {
        this.error.set(`${f.name}: please choose JPG or PNG images.`);
        continue;
      }
      if (f.size > MAX_MB * 1024 * 1024) {
        this.error.set(`${f.name} is larger than ${MAX_MB} MB.`);
        continue;
      }
      if (this.files().length >= MAX_SLICES) {
        this.error.set(`A study can have at most ${MAX_SLICES} slices.`);
        break;
      }
      this.files.update((fs) => [...fs, f]);
      this.previews.update((ps) => [...ps, '']);
      const index = this.files().length - 1;
      const reader = new FileReader();
      reader.onload = () => this.previews.update((ps) => ps.map((p, i) => (i === index ? (reader.result as string) : p)));
      reader.readAsDataURL(f);
    }
  }

  protected removeFile(index: number): void {
    this.files.update((fs) => fs.filter((_, i) => i !== index));
    this.previews.update((ps) => ps.filter((_, i) => i !== index));
  }

  protected run(): void {
    const files = this.files();
    if (this.form.invalid || files.length === 0) {
      this.form.markAllAsTouched();
      if (files.length === 0) this.error.set('Please upload an MRI image first.');
      return;
    }
    this.running.set(true);
    this.error.set('');
    const fail = (e: Error) => {
      this.error.set(e.message);
      this.running.set(false);
    };
    const details = this.form.getRawValue();
    if (files.length === 1) {
      this.api.classifyScan({ ...details, file: files[0] }).subscribe({
        next: (scan) => this.router.navigate(['/scans', scan.id]),
        error: fail,
      });
    } else {
      this.api.classifyStudy({ ...details, files }).subscribe({
        next: (study) => this.router.navigate(['/scans', study.slices[0].id]),
        error: fail,
      });
    }
  }
}
