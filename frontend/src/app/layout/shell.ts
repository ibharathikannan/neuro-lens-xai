import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { ActivatedRoute, NavigationEnd, Router, RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { filter } from 'rxjs';

import { ApiService } from '../service';
import { environment } from '../../environments/environment';

@Component({
  selector: 'app-shell',
  imports: [RouterOutlet, RouterLink, RouterLinkActive],
  templateUrl: './shell.html',
  styleUrl: './shell.scss',
})
export class Shell implements OnInit {
  protected readonly api = inject(ApiService);
  private readonly router = inject(Router);
  private readonly route = inject(ActivatedRoute);

  protected readonly title = signal('');
  protected readonly crumb = signal('');
  protected readonly mockMode = environment.useMockData;
  protected readonly initials = computed(() =>
    (this.api.currentUser()?.full_name ?? '?').split(/\s+/).filter(Boolean).slice(0, 2).map((w) => w[0].toUpperCase()).join(''));

  protected readonly nav = [
    { path: '/dashboard', icon: '▦', label: 'Dashboard' },
    { path: '/patients', icon: '👥', label: 'Patients' },
    { path: '/new-scan', icon: '＋', label: 'New Classification' },
    { path: '/similar', icon: '⧉', label: 'Similar Cases' },
    { path: '/reports', icon: '🗎', label: 'Reports' },
    { path: '/system', icon: '⚙', label: 'Model & System' },
  ];
  protected readonly adminNav = [{ path: '/users', icon: '🔑', label: 'Users' }];

  ngOnInit(): void {
    this.updateTitle();
    this.router.events.pipe(filter((e) => e instanceof NavigationEnd)).subscribe(() => this.updateTitle());
    // Confirm the stored token is still accepted by the backend (logs out on 401)
    this.api.loadCurrentUser().subscribe({ error: () => undefined });
  }

  private updateTitle(): void {
    let r = this.route;
    while (r.firstChild) r = r.firstChild;
    const data = r.snapshot.data;
    const id = r.snapshot.paramMap.get('id');
    this.title.set(id && data['title'] ? `${data['title']} — ${id}` : data['title'] ?? '');
    this.crumb.set(data['crumb'] ?? '');
  }
}
