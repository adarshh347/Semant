import React from 'react';
import './MotivePage.css';

function MotivePage() {
  return (
    <article className="motive-page">
      <header className="motive-hero">
        <span className="eyebrow">The Motive</span>
        <h1 className="motive-title">
          A manifesto for <em>seeing</em>.
        </h1>
        <p className="motive-motto">Unconcealment as context engineering.</p>
      </header>

      <div className="motive-body">
        <p className="motive-lead">
          That single line is the whole of it: to build, deliberately, the
          conditions under which an image can come out of hiding. Everything else
          here is an attempt to earn that sentence.
        </p>

        <p>
          The word borrowed from Heidegger is <em>aletheia</em>. The Greeks did
          not first mean by truth a statement that matched the world; they meant{' '}
          <em>unconcealment</em> — a thing stepping forward out of darkness into
          the light where it can be regarded. Truth, on this older account, is an
          event rather than a verdict. A face turning toward you across a room is
          true in this sense before any word is said about it. What is hidden
          becomes, for a moment, present. And because presence is something that
          happens, it can also fail to happen. A thing can stay covered even while
          it sits in plain sight.
        </p>

        <blockquote className="motive-quote">
          The scroll disenchants. Images flood past — felt, never known.
        </blockquote>

        <p>
          This is the quiet injury of the feed. We see thousands of pictures and
          meet almost none of them. They arrive and depart at the speed of a thumb,
          registering as mood, never as encounter. Captioning systems, for all
          their cleverness, deepen the loss rather than repair it. They announce{' '}
          <em>what</em> is in the frame — a dog, a beach, two people laughing — and
          in naming it so confidently they close the question before it can be
          asked. An answer arrives where wonder should have been. The image is
          identified, filed, and forgotten, still concealed behind its own label.
        </p>

        <p>
          Semant takes the opposite vow. We treat interpretation not as
          classification but as <em>context engineering</em>: the patient layering
          of lenses, memory, and grounded knowledge until an image is slowly
          unconcealed instead of merely tagged. You choose how to look. A{' '}
          <em>Phenomenological</em> lens asks what it is like to stand before the
          thing; a <em>Semiotic</em> lens reads its signs and what they point
          beyond themselves toward; an <em>Atmospheric</em> lens dwells in its
          mood, its weather, its temperature of feeling. Each is a different light
          cast from a different angle, and each reveals what the others leave dark.
        </p>

        <p>
          Then there is the <em>punctum</em> — Barthes' word for the one piercing
          detail that snags you, the crease, the gesture, the stray light at the
          edge. We take that detail and, instead of explaining it away, turn it into
          a question put back to you. The point is not to settle the image but to
          keep it open. And every encounter accretes: a semantic memory that
          thickens over time, so each new picture is read against the company of
          everything you have already attended to. The looking compounds.
        </p>

        <p>
          What is at stake is not better metadata. It is re-enchantment — the
          recovery of attention as a thing worth spending, and the slow making of a
          record: one person's encounters with images, held long enough to become
          genuinely seen. We are not building a machine that tells you what is there.
          We are building a place where things are given time to emerge.
        </p>

        <blockquote className="motive-quote motive-quote--close">
          Unconcealment as context engineering.
        </blockquote>
      </div>
    </article>
  );
}

export default MotivePage;
