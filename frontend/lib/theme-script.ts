// Plain (server-safe) module: app/layout.tsx inlines THEME_SCRIPT in <head>.
// Importing it from lib/theme.ts ("use client") would give the server layout a
// client reference instead of the string.

export const THEME_KEY = "oppradar-theme";

/** Runs before first paint so a dark-theme page never flashes light. Mirrors apply() in lib/theme.ts. */
export const THEME_SCRIPT = `(function(){try{var t=localStorage.getItem("${THEME_KEY}");var d=t==="dark"||(t!=="light"&&matchMedia("(prefers-color-scheme: dark)").matches);document.documentElement.classList.toggle("dark",d)}catch(e){}})()`;
