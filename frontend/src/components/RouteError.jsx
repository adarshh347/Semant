import React from 'react';
import { Link, isRouteErrorResponse, useRouteError } from 'react-router-dom';
import { SemantMark } from './brand/SemantMark';
import NotFoundPage from './NotFoundPage';
import './PlaceholderPage.css';

/**
 * Root error boundary (the router `errorElement`). A genuine 404 (a route that
 * threw a 404 Response) renders the branded NotFoundPage; anything else gets a
 * calm, on-taste error surface led by the mark rather than the browser's raw
 * stack. Presentational only.
 */
export default function RouteError() {
  const error = useRouteError();

  if (isRouteErrorResponse(error) && error.status === 404) {
    return <NotFoundPage />;
  }

  const detail =
    (isRouteErrorResponse(error) && `${error.status} ${error.statusText}`) ||
    error?.message ||
    'Something came loose while loading this view.';

  return (
    <div className="placeholder">
      <div className="placeholder-inner">
        <SemantMark size={52} color="var(--accent)" title="" aria-hidden="true" style={{ marginBottom: '1.25rem' }} />
        <span className="placeholder-eyebrow">Something broke</span>
        <h1 className="placeholder-title">We lost the thread</h1>
        <p className="placeholder-lede">{detail}</p>
        <Link to="/" className="placeholder-pill">
          Return home <span aria-hidden>→</span>
        </Link>
      </div>
    </div>
  );
}
