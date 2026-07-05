// Self-contained editorial "photographs" for preview cards — inline SVG data
// URIs so cards render with no network (CSP-safe in the design product).
// Warm paper/terracotta palette to match the Drishtikone "Editorial Gallery".
export const photo = (w: number, h: number, from: string, to: string, motif = ''): string =>
  'data:image/svg+xml,' +
  encodeURIComponent(
    `<svg xmlns='http://www.w3.org/2000/svg' width='${w}' height='${h}' viewBox='0 0 ${w} ${h}'>` +
      `<defs><linearGradient id='g' x1='0' y1='0' x2='1' y2='1'>` +
      `<stop offset='0' stop-color='${from}'/><stop offset='1' stop-color='${to}'/></linearGradient></defs>` +
      `<rect width='${w}' height='${h}' fill='url(#g)'/>${motif}</svg>`,
  );

const ring = (cx: number, cy: number, r: number, o = 0.18) =>
  `<circle cx='${cx}' cy='${cy}' r='${r}' fill='none' stroke='#FBF9F5' stroke-width='2' opacity='${o}'/>`;

// A small library of on-brand images.
export const IMAGES = {
  terracotta: photo(600, 800, '#D2654A', '#7A2E1E', ring(300, 360, 150) + ring(300, 360, 210, 0.1)),
  paper: photo(600, 800, '#F4F1EA', '#D6CFC0', `<circle cx='300' cy='400' r='120' fill='#C4533A' opacity='0.5'/>`),
  ink: photo(600, 800, '#3A3630', '#14120E', ring(300, 300, 120) + `<rect x='210' y='470' width='180' height='6' fill='#D2654A' opacity='0.7'/>`),
  dusk: photo(600, 800, '#4A4A6A', '#1C1A2E', `<circle cx='420' cy='200' r='70' fill='#F7E8E2' opacity='0.6'/>`),
};
