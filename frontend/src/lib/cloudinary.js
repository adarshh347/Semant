// Cloudinary URL transforms — no SDK, no backend pipeline. We already store the
// delivery URL (…/image/upload/v123/posts/xxx.jpg); we just inject a transform
// segment right after /image/upload/ to ask Cloudinary for a resized / blurred
// variant. Non-Cloudinary URLs pass through untouched.

const UPLOAD = '/image/upload/';

function inject(url, transform) {
  if (!url) return url;
  const i = url.indexOf(UPLOAD);
  if (i === -1) return url; // not a Cloudinary upload URL — leave as-is
  const head = url.slice(0, i + UPLOAD.length);
  const tail = url.slice(i + UPLOAD.length);
  return `${head}${transform}/${tail}`;
}

// Tiny, heavily-blurred placeholder (~1KB). Doubles as the aspect-ratio probe:
// Cloudinary preserves the source aspect at w_32, so a loaded LQIP's
// naturalWidth/Height gives the true ratio the justified layout needs.
export function cldLqip(url) {
  return inject(url, 'e_blur:1400,q_1,f_auto,w_32');
}

// Display variant at a target CSS width. c_limit never upscales; q_auto/f_auto
// let Cloudinary pick the best quality + format (AVIF/WebP) per browser.
export function cldAt(url, w) {
  return inject(url, `c_limit,w_${w},q_auto,f_auto`);
}

// Responsive srcSet across the widths a justified row realistically renders at.
// react-photo-album wants an array of { src, width, height }; height comes from
// the image's aspect ratio (height / width), resolved client-side.
const SRCSET_WIDTHS = [240, 360, 480, 640, 800, 1080];
export function cldSrcSet(url, aspect) {
  return SRCSET_WIDTHS.map((w) => ({
    src: cldAt(url, w),
    width: w,
    height: Math.round(w * aspect),
  }));
}
