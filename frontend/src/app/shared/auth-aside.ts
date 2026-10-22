import { Component, input } from '@angular/core';

import { Icon, IconName } from './icon';
import { MriImage } from './mri-image';

/**
 * The branded left-hand panel of the sign-in and create-account pages.
 * The headline and intro come from the page (content projection); the preview and feature list are shared.
 */
@Component({
  selector: 'app-auth-aside',
  imports: [Icon, MriImage],
  templateUrl: './auth-aside.html',
  styleUrl: './auth-aside.scss',
})
export class AuthAside {
  /** Small print at the bottom of the panel. */
  readonly fine = input('Research prototype — not a diagnostic device · NUS-ISS PRS Practice Module');

  protected readonly features: { icon: IconName; title: string; text: string }[] = [
    { icon: 'scan', title: 'Grad-CAM explanations', text: 'See which regions drove each prediction.' },
    { icon: 'similar', title: 'Similar-case retrieval', text: 'Compare with confirmed cases side by side.' },
    { icon: 'reports', title: 'Automated reports', text: 'A Word report for every result.' },
    { icon: 'patients', title: 'Patient records', text: 'Pseudonymised history in one place.' },
  ];

  /** Sample class probabilities for the illustration only. */
  protected readonly bars = [
    { label: 'Glioma', pct: 93, color: 'var(--glioma)' },
    { label: 'Meningioma', pct: 4, color: 'var(--meningioma)' },
    { label: 'Pituitary', pct: 2, color: 'var(--pituitary)' },
    { label: 'No tumor', pct: 1, color: 'var(--notumor)' },
  ];
}
