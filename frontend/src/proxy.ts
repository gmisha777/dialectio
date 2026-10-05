import createMiddleware from "next-intl/middleware";

import { routing } from "./i18n/routing";

// Redirects "/" to the visitor's locale ("/uk" or "/en") and keeps the locale prefix on all routes.
export default createMiddleware(routing);

export const config = {
  // Skip API routes, Next.js internals and files with an extension (favicon.ico, images, ...).
  matcher: "/((?!api|_next|_vercel|.*\\..*).*)",
};
