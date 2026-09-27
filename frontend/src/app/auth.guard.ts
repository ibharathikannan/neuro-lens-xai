import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';

import { ApiService } from './service';

/** Protects dashboard pages: only logged-in users with a valid (unexpired) token may enter. */
export const authGuard: CanActivateFn = (_route, state) => {
  const api = inject(ApiService);
  if (api.isLoggedIn()) return true;
  return inject(Router).createUrlTree(['/login'], { queryParams: { returnUrl: state.url } });
};

/** Keeps logged-in users away from the login and registration pages. */
export const guestGuard: CanActivateFn = () => {
  const api = inject(ApiService);
  return api.isLoggedIn() ? inject(Router).createUrlTree(['/dashboard']) : true;
};
