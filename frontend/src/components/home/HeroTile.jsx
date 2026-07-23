import { Link } from 'react-router-dom';
import { PerceptMark } from '../brand/glyphs';

// Hero strip (full width). Wordmark in the display serif, one wedge line, and a
// single ink-pill CTA into the work — plus one quiet text link to upload. One
// display + one body + one accent mark; nothing centred (left text column).
export default function HeroTile() {
  const openUpload = () =>
    window.dispatchEvent(new CustomEvent('semant:open-upload'));

  return (
    <section className="tile tile-hero">
      <span className="eyebrow tile-hero-eyebrow">See · Read · Write</span>
      <h1 className="tile-hero-mark">
        Semant<span className="tile-hero-glyph" aria-hidden><PerceptMark size="1em" /></span>
      </h1>
      <p className="tile-hero-wedge">
        Not another place to save images — an instrument for reading them,{' '}
        <em>part by part, in your own words.</em>
      </p>
      <div className="tile-hero-cta">
        <Link to="/gallery" className="btn btn-primary btn-lg" viewTransition>
          Enter the Archive <span aria-hidden>→</span>
        </Link>
        <button type="button" className="tile-hero-textlink" onClick={openUpload}>
          Upload an image <span aria-hidden>↑</span>
        </button>
      </div>
    </section>
  );
}
