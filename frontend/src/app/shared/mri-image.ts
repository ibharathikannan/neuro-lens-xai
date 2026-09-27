import { Component, computed, input } from '@angular/core';

import { Lesion } from '../models';

/**
 * Shows a scan image. With a real `src` (e.g. an Azure Blob SAS URL from the backend) it renders that image;
 * without one (demo data) it draws a stylised placeholder MRI slice with an optional Grad-CAM-style overlay.
 */
@Component({
  selector: 'app-mri-image',
  template: `
    @if (src()) {
      <img [src]="src()" [width]="size()" [height]="size()" [alt]="alt()" class="img" />
    } @else {
      <svg [attr.width]="size()" [attr.height]="size()" viewBox="0 0 100 100" class="img" role="img" [attr.aria-label]="alt()">
        <defs>
          <radialGradient [attr.id]="id + 'b'" cx="50%" cy="48%" r="60%">
            <stop offset="0" stop-color="#9a9a9a" /><stop offset=".7" stop-color="#6d6d6d" /><stop offset="1" stop-color="#2a2a2a" />
          </radialGradient>
          <radialGradient [attr.id]="id + 'l'" cx="50%" cy="50%" r="50%">
            <stop offset="0" stop-color="#e9e9e9" /><stop offset=".6" stop-color="#cfcfcf" /><stop offset="1" stop-color="#8a8a8a" stop-opacity="0" />
          </radialGradient>
          <radialGradient [attr.id]="id + 'h'" cx="50%" cy="50%" r="50%">
            <stop offset="0" stop-color="#ff1a00" stop-opacity=".85" /><stop offset=".35" stop-color="#ffb000" stop-opacity=".7" />
            <stop offset=".65" stop-color="#28c7ff" stop-opacity=".35" /><stop offset="1" stop-color="#0030ff" stop-opacity="0" />
          </radialGradient>
        </defs>
        <rect width="100" height="100" fill="#050505" />
        <ellipse cx="50" cy="50" rx="38.9" ry="45.6" fill="#2c2c2c" />
        <ellipse cx="50" cy="50" rx="36" ry="43" [attr.fill]="'url(#' + id + 'b)'" />
        @for (g of gyri; track $index) {
          <path [attr.d]="g" stroke="#3b3b3b" stroke-width="1.2" fill="none" opacity=".75" />
        }
        <line x1="50" y1="9" x2="50" y2="91" stroke="#2e2e2e" stroke-width="1.2" />
        <ellipse cx="43.5" cy="50" rx="3.6" ry="8.6" fill="#1c1c1c" />
        <ellipse cx="56.5" cy="50" rx="3.6" ry="8.6" fill="#1c1c1c" />
        @if (lesionVisible()) {
          <circle [attr.cx]="l().x * 100" [attr.cy]="l().y * 100" [attr.r]="l().r * 100" [attr.fill]="'url(#' + id + 'l)'" />
        }
        @if (heatmap() && lesionVisible()) {
          <ellipse [attr.cx]="l().x * 100" [attr.cy]="l().y * 100" [attr.rx]="l().r * 210" [attr.ry]="l().r * 180" [attr.fill]="'url(#' + id + 'h)'" />
        }
      </svg>
    }
  `,
  styles: `.img { display: block; border-radius: 10px; background: #000; }`,
})
export class MriImage {
  readonly src = input<string | undefined>();
  readonly lesion = input<Lesion | undefined>();
  readonly heatmap = input(false);
  readonly size = input(220);
  readonly alt = input('MRI scan');

  protected readonly id = 'mri' + Math.random().toString(36).slice(2, 8);
  protected readonly l = computed(() => this.lesion() ?? { x: 0.64, y: 0.36, r: 0.11 });
  protected readonly lesionVisible = computed(() => this.l().r > 0);
  protected readonly gyri = Array.from({ length: 18 }, (_, i) => {
    const a = (i / 18) * Math.PI * 2 + 0.3;
    const p = (ang: number, k: number) => `${50 + Math.cos(ang) * 36 * k},${50 + Math.sin(ang) * 43 * k}`;
    return `M${p(a, 0.55)} Q${p(a + 0.35, 0.8)} ${p(a + 0.18, 0.92)}`;
  });
}
