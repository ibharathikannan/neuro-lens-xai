import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { ActivatedRoute, NavigationEnd, Router, RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { filter } from 'rxjs';

import { ApiService } from '../service';
import { Icon, IconName } from '../shared/icon';
import { environment } from '../../environments/environment';

interface NavItem { path: string; icon: IconName; label: string; }

@Component({
  selector: 'app-shell',
  imports: [RouterOutlet, RouterLink, RouterLinkActive, Icon],
  templateUrl: './shell.html',
  styleUrl: './shell.scss',
})
export class Shell implements OnInit {
  protected readonly api = inject(ApiService);
  private readonly router = inject(Router);
  private readonly route = inject(ActivatedRoute);

  protected readonly title = signal('');
  protected readonly crumb = signal('');
  protected readonly menuOpen = signal(false);
  protected readonly mockMode = environment.useMockData;
  protected readonly initials = computed(() =>
    (this.api.currentUser()?.full_name ?? '?').split(/\s+/).filter(Boolean).slice(0, 2).map((w) => w[0].toUpperCase()).join(''));

  /** Sidebar sections; the Administration section is only shown to administrators. */
  protected readonly groups = computed<{ label: string; items: NavItem[] }[]>(() => [
    {
      label: 'Workspace',
      items: [
        { path: '/dashboard', icon: 'dashboard', label: 'Dashboard' },
        { path: '/patients', icon: 'patients', label: 'Patients' },
        { path: '/new-scan', icon: 'scan', label: 'New Classification' },
      ],
    },
    {
      label: 'Analysis',
      items: [
        { path: '/similar', icon: 'similar', label: 'Similar Cases' },
        { path: '/reports', icon: 'reports', label: 'Reports' },
      ],
    },
    { label: 'System', items: [{ path: '/system', icon: 'system', label: 'Model & System' }] },
    ...(this.api.isAdmin() ? [{ label: 'Administration', items: [{ path: '/users', icon: 'admin' as IconName, label: 'Users' }] }] : []),
  ]);

  ngOnInit(): void {
    this.updateTitle();
    this.router.events.pipe(filter((e) => e instanceof NavigationEnd)).subscribe(() => {
      this.updateTitle();
      this.menuOpen.set(false);
    });
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
