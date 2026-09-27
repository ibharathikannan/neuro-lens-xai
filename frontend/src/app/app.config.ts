import { ApplicationConfig, provideBrowserGlobalErrorListeners } from '@angular/core';
import { provideHttpClient } from '@angular/common/http';
import { NavigationError, provideRouter, withComponentInputBinding, withNavigationErrorHandler } from '@angular/router';

import { routes } from './app.routes';

const RELOAD_KEY = 'neurolens_reloaded_for_update';

/**
 * After a new deployment, a page that was already open still asks for the previous build's files, which no
 * longer exist. Reload once so the browser picks up the new version (the flag prevents a reload loop).
 */
function reloadOnStaleBuild(event: NavigationError): void {
  const message = String((event.error as Error)?.message ?? event.error);
  if (!/dynamically imported module|Importing a module script failed|Loading chunk/i.test(message)) return;
  try {
    const last = Number(sessionStorage.getItem(RELOAD_KEY) ?? 0);
    if (Date.now() - last < 60_000) return;          // already reloaded a moment ago: don't loop
    sessionStorage.setItem(RELOAD_KEY, String(Date.now()));
  } catch {
    /* storage unavailable: still reload once */
  }
  window.location.assign(event.url);
}

export const appConfig: ApplicationConfig = {
  providers: [
    provideBrowserGlobalErrorListeners(),
    provideHttpClient(),
    provideRouter(routes, withComponentInputBinding(), withNavigationErrorHandler(reloadOnStaleBuild)),
  ],
};
