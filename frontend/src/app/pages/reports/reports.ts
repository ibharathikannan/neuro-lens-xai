import { Component, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';

import { ApiService } from '../../service';
import { Report, TumorClass, classLabel } from '../../models';
import { ClassChip, TypeChip } from '../../shared/chips';
import { Icon } from '../../shared/icon';

@Component({
  selector: 'app-reports',
  imports: [FormsModule, RouterLink, ClassChip, Icon, TypeChip],
  templateUrl: './reports.html',
  styles: `.kpis { grid-template-columns: repeat(3, 1fr); } @media (max-width: 900px) { .kpis { grid-template-columns: 1fr; } }`,
})
export class Reports {
  private readonly api = inject(ApiService);
  protected readonly reports = signal<Report[] | null>(null);
  protected readonly error = signal('');
  protected readonly info = signal('');
  protected readonly search = signal('');
  protected readonly classFilter = signal<TumorClass | ''>('');
  /** Classes present in the reports, for the filter. */
  protected readonly classes = computed(() => [...new Set((this.reports() ?? []).map((r) => r.result))].map((c) => [c, classLabel(c)] as [TumorClass, string]));

  protected readonly filtered = computed(() => {
    const term = this.search().trim().toLowerCase();
    const cls = this.classFilter();
    return (this.reports() ?? []).filter((r) =>
      (!cls || r.result === cls) &&
      (!term || [r.id, r.patient_id, r.scan_id, r.study_id ?? ''].some((v) => v.toLowerCase().includes(term))));
  });

  constructor() {
    this.api.getReports().subscribe({
      next: (r) => this.reports.set(r),
      error: (e: Error) => this.error.set(e.message),
    });
  }

  protected download(report: Report): void {
    const download = report.study_id ? this.api.downloadStudyReport(report.study_id) : this.api.downloadReport(report.scan_id);
    download.subscribe({
      next: (done) => { if (!done) this.info.set('Demo data mode: reports can be downloaded when connected to the backend.'); },
      error: (e: Error) => this.error.set(e.message),
    });
  }

  protected exportCsv(): void {
    const header = 'report,patient,scan,study,slices,result,created,blob_path,size';
    const rows = this.filtered().map((r) => [r.id, r.patient_id, r.scan_id, r.study_id ?? '', r.slice_count ?? 1, r.result, r.created, r.blob_path, r.size].join(','));
    const url = URL.createObjectURL(new Blob([[header, ...rows].join('\n')], { type: 'text/csv' }));
    const a = Object.assign(document.createElement('a'), { href: url, download: 'neurolens_reports.csv' });
    a.click();
    URL.revokeObjectURL(url);
  }
}
