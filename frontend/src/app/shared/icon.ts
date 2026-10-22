import { Component, computed, input } from '@angular/core';

/** Path helpers: every icon is a list of SVG path strings on a 24x24 grid (stroke icons, drawn with currentColor). */
const circle = (cx: number, cy: number, r: number) => `M${cx - r} ${cy}a${r} ${r} 0 1 0 ${2 * r} 0a${r} ${r} 0 1 0 ${-2 * r} 0`;
const rect = (x: number, y: number, w: number, h: number, r: number) =>
  `M${x + r} ${y}H${x + w - r}a${r} ${r} 0 0 1 ${r} ${r}V${y + h - r}a${r} ${r} 0 0 1 ${-r} ${r}H${x + r}a${r} ${r} 0 0 1 ${-r} ${-r}V${y + r}a${r} ${r} 0 0 1 ${r} ${-r}z`;

const ICONS = {
  dashboard: [rect(3, 3, 7, 9, 1.5), rect(14, 3, 7, 5, 1.5), rect(14, 12, 7, 9, 1.5), rect(3, 16, 7, 5, 1.5)],
  patients: [circle(9, 8, 3.5), 'M2.5 20c0-3.6 2.9-6 6.5-6s6.5 2.4 6.5 6', circle(17.5, 9, 2.5), 'M17 14.2c2.6.3 4.5 2.2 4.5 5.3'],
  plus: ['M12 5v14M5 12h14'],
  scan: ['M4 8V6a2 2 0 0 1 2-2h2M16 4h2a2 2 0 0 1 2 2v2M20 16v2a2 2 0 0 1-2 2h-2M8 20H6a2 2 0 0 1-2-2v-2', 'M7 12h10'],
  similar: [rect(9, 9, 11, 11, 2), 'M5 15V6a2 2 0 0 1 2-2h9'],
  reports: ['M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z', 'M14 3v5h5M9 13h6M9 17h6'],
  system: ['M3 12h4l3-8 4 16 3-8h4'],
  admin: ['M12 3l7 3v6c0 4.5-3 7.5-7 9-4-1.5-7-4.5-7-9V6z', 'M9 12l2 2 4-4'],
  account: [circle(12, 8, 4), 'M4 21c0-4.4 3.6-7 8-7s8 2.6 8 7'],
  search: [circle(11, 11, 7), 'M20 20l-3.5-3.5'],
  upload: ['M12 16V4M7 9l5-5 5 5', 'M4 16v3a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-3'],
  download: ['M12 4v12M7 11l5 5 5-5', 'M4 20h16'],
  check: ['M5 12.5l4.5 4.5L19 7'],
  alert: ['M12 3.5l9.5 16.5h-19z', 'M12 10v4M12 17.2v.1'],
  info: [circle(12, 12, 9), 'M12 11v5M12 8v.1'],
  logout: ['M9 4H6a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h3', 'M16 8l4 4-4 4M20 12H9'],
  arrowRight: ['M5 12h14M13 6l6 6-6 6'],
  trendUp: ['M3 17l6-6 4 4 8-8', 'M15 7h6v6'],
  menu: ['M4 7h16M4 12h16M4 17h16'],
  close: ['M6 6l12 12M18 6L6 18'],
  image: [rect(3, 4, 18, 16, 2), circle(9, 10, 1.6), 'M21 16l-5-5-8 8'],
  chevronRight: ['M9 6l6 6-6 6'],
} as const;

export type IconName = keyof typeof ICONS;

/** Inline icon: `<app-icon name="patients" />`. Inherits the text colour; `size` is in px. */
@Component({
  selector: 'app-icon',
  template: `
    <svg [attr.width]="size()" [attr.height]="size()" viewBox="0 0 24 24" fill="none" stroke="currentColor"
         stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">
      @for (d of paths(); track $index) { <path [attr.d]="d" /> }
    </svg>
  `,
  styles: `:host { display: inline-flex; flex-shrink: 0; } svg { display: block; }`,
})
export class Icon {
  readonly name = input.required<IconName>();
  readonly size = input(18);
  protected readonly paths = computed<readonly string[]>(() => ICONS[this.name()]);
}
