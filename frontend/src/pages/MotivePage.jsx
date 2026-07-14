import React from 'react';
import { useParams, Link } from 'react-router-dom';
import './MotivePage.css';

/**
 * The Motive — an editorial essay section. One article per screen (announcement
 * register), navigable via a "Next article" footer. Articles are ordered; the
 * default /motive route shows the first, /motive/:slug shows a named one.
 *
 * Product word in copy = Semant (the source essays use the concept word
 * "Darshan"; per the design language the app name is Semant, Sanskrit terms name
 * concepts only — e.g. Aletheia).
 */

function ManifestoBody() {
  return (
    <>
      <p className="motive-lead">
        That single line is the whole of it: to build, deliberately, the
        conditions under which an image can come out of hiding. Everything else
        here is an attempt to earn that sentence.
      </p>
      <p>
        The word borrowed from Heidegger is <em>aletheia</em>. The Greeks did not
        first mean by truth a statement that matched the world; they meant{' '}
        <em>unconcealment</em> — a thing stepping forward out of darkness into the
        light where it can be regarded. Truth, on this older account, is an event
        rather than a verdict. A face turning toward you across a room is true in
        this sense before any word is said about it. What is hidden becomes, for a
        moment, present. And because presence is something that happens, it can
        also fail to happen. A thing can stay covered even while it sits in plain
        sight.
      </p>
      <blockquote className="motive-quote">
        The scroll disenchants. Images flood past — felt, never known.
      </blockquote>
      <p>
        This is the quiet injury of the feed. We see thousands of pictures and
        meet almost none of them. They arrive and depart at the speed of a thumb,
        registering as mood, never as encounter. Captioning systems, for all their
        cleverness, deepen the loss rather than repair it. They announce{' '}
        <em>what</em> is in the frame — a dog, a beach, two people laughing — and
        in naming it so confidently they close the question before it can be asked.
        An answer arrives where wonder should have been. The image is identified,
        filed, and forgotten, still concealed behind its own label.
      </p>
      <p>
        Semant takes the opposite vow. We treat interpretation not as
        classification but as <em>context engineering</em>: the patient layering
        of lenses, memory, and grounded knowledge until an image is slowly
        unconcealed instead of merely tagged. You choose how to look. A{' '}
        <em>Phenomenological</em> lens asks what it is like to stand before the
        thing; a <em>Semiotic</em> lens reads its signs and what they point beyond
        themselves toward; an <em>Atmospheric</em> lens dwells in its mood, its
        weather, its temperature of feeling. Each is a different light cast from a
        different angle, and each reveals what the others leave dark.
      </p>
      <p>
        Then there is the <em>punctum</em> — Barthes' word for the one piercing
        detail that snags you, the crease, the gesture, the stray light at the
        edge. We take that detail and, instead of explaining it away, turn it into
        a question put back to you. The point is not to settle the image but to
        keep it open. And every encounter accretes: a semantic memory that thickens
        over time, so each new picture is read against the company of everything you
        have already attended to. The looking compounds.
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
    </>
  );
}

function ContextEngineeringBody() {
  return (
    <>
      <p className="motive-lead">
        There is a certain kind of intelligence that modern AI culture has started
        to respect: not just the intelligence of the model, but the intelligence of
        the <em>context around the model</em>. That is what people mean by context
        engineering — the art of deciding what the machine should see, remember,
        retrieve, ignore, compress, prioritise, and carry forward. Intelligence
        does not emerge only from raw generation. It emerges from{' '}
        <em>arrangement</em>: from choosing the right evidence, preserving the right
        memory, giving the model a meaningful world to think inside.
      </p>
      <p>
        In software and enterprise AI this has become almost obvious. A company has
        documents, chats, codebases, policies, tickets, customers, histories. The
        model cannot be thrown naked into that chaos and expected to produce wisdom.
        It needs context, retrieval, structure — the right pieces of the world
        placed before it at the right time. But art and entertainment have not yet
        had their version of this revolution. They still live too much in the feed.
      </p>
      <p>
        A picture appears. A caption appears. A few comments gather. People react —
        like, save, share, move on. The image burns for a moment and disappears into
        the river. But what was actually <em>seen</em>? What part of the image held
        the eye? The posture, the shoulder line, the drape, the architecture of the
        fabric, the background silence, the light, the way one object quietly
        dominated the frame?
      </p>
      <blockquote className="motive-quote">
        Social media is good at distribution, not perception. It makes images
        travel; it does not make them unfold.
      </blockquote>
      <p>
        This project begins from that dissatisfaction. The motive is not to build
        another posting app, another editor, another AI caption tool. It is sharper
        than that: to build a context engineering layer for art, fashion,
        entertainment, and taste — a place where images are not consumed as flat
        rectangles, but entered as structured worlds. A place where the machine does
        not simply say "beautiful outfit," "nice composition," "cinematic vibe," and
        collapse into generic praise, but learns to ask: where is the force? Which
        region matters? Which part is carrying the meaning? Which detail is
        accidental, and which is secretly the whole image?
      </p>
      <p>
        This is where Semant begins. Semant is not "image analysis" in the ordinary
        sense. It is seeing as an act of attention, a disciplined encounter, the slow
        ignition of meaning from visual parts. The current internet treats the image
        as one unit. Semant treats the image as an <em>organism</em> — with organs,
        regions, textures, gestures, planes, tensions, concealments.
      </p>
      <p>
        A garment is not just "clothing." It has collar, cuff, sleeve, hem, fold,
        seam, fall, pressure, looseness, shine, weight. A building is not just
        "architecture." It has planes, thresholds, shadows, openings, stone, rhythm,
        compression, release. A portrait is not just "a person." It has gaze, jaw,
        hairline, hand, neck, shoulder, distance, refusal, invitation. The purpose is
        to make those parts <em>addressable</em>. Not just visible. Addressable.
      </p>
      <p>
        That means a user should be able to point to the exact region that moved
        them, and the system should remember it. A writer should be able to build a
        paragraph around it. An audience should be able to tap it. A retrieval system
        should be able to say: you have liked this kind of fabric fall before, this
        shadow, this posture, this controlled exposure, this visual dominance.
      </p>
      <blockquote className="motive-quote">
        A gallery stores images. A taste engine stores the reasons images matter.
      </blockquote>
      <p>
        And those reasons are rarely whole-image reasons. They are regional. A tiny
        detail detonates the frame. A sleeve changes the mood. A shadow introduces
        secrecy. A fold creates softness. A posture creates power. A background
        emptiness makes the subject feel abandoned or sacred. That is why the
        architecture is not separate from the philosophy — it is the motive becoming
        executable. A region model is a claim about perception: the image is not only
        a file, it is a field of meaningful parts. Segmentation is the first act of
        spatial grounding — before we interpret, we must locate. A vision model is an
        interpretive companion — after we locate, we must read. An embedding store is
        memory for taste — what moved you once can be found again in another form.
      </p>
      <p>
        That is the real parallel with context engineering. In enterprise AI the
        question is: what does the model need to know to answer well? Here it becomes:
        what does the model need to see, remember, and retrieve to help a human feel
        an image more deeply? The AI world made people take context seriously for
        work — documents, code, tasks, memory. This project takes context seriously
        for aesthetic life: images, regions, gestures, fabric, light, mood, persona,
        story, audience, taste history.
      </p>
      <p>
        Because entertainment is not shallow by nature. It has been made shallow by
        the interfaces that carry it. Fashion is not shallow. Cinema is not shallow.
        Photography is not shallow. Beauty is not shallow. These things become shallow
        only when the platform gives us no instruments except scrolling and reacting.
        The feed made culture fast; now we need tools that make culture perceivable
        again — not slow in a boring academic way, but sharper weapons of attention.
      </p>
      <p>
        A creator should be able to upload an image and ask more than "what caption
        should I write?" — What is the strongest region here? What is the image
        withholding? What part of the styling is doing the real work? Where does the
        eye enter, and where does it get trapped? What is the atmosphere? What should
        the writing orbit around, and what should be left unsaid? And the audience
        should not be passive either. The viewer participates in the unconcealment:
        they tap the region that pulled them, choose the reading that feels truest,
        reveal their own perceptual fork. The system learns not just that they liked
        an image, but <em>how they saw it</em>.
      </p>
      <blockquote className="motive-quote">
        A like is weak. A comment is noisy. A region tap is intimate — here, this,
        this is where the image entered me.
      </blockquote>
      <p>
        That is the beginning of a taste graph. Not taste as category preference —
        "likes sarees," "likes architecture." That is too crude. Taste as
        pattern-recognition across details: drape tension, muted light, ceremonial
        posture, asymmetry, softness against severity, ornamental restraint, exposed
        structure, theatrical stillness. This cannot be captured by hashtags. It needs
        regions, embeddings, memory, language — an interface that lets the user look,
        mark, read, write, and react.
      </p>
      <blockquote className="motive-quote">
        See → Mark → Read → Write → React → Remember.
      </blockquote>
      <p>
        This is where the project becomes more than a product — a new literacy layer.
        Most people have visual taste but no language for it. They know something feels
        expensive, sacred, vulgar, intimate, cinematic, dangerous, graceful; their
        perception is ahead of their vocabulary. A good system should not replace that
        perception — it should escort it into language. That is what Aletheia is for.
        It should not merely caption the image; it should reveal what is already
        half-felt, offering lenses — Phenomenological, how the image meets the body;
        Semiotic, what it culturally signals; Atmospheric, what emotional weather it
        releases.
      </p>
      <p>
        But the sacred rule is this: the reading must stay evidence-bound. No floating
        poetry without visual anchor. No fake profundity. No generic art-jargon fog.
        The system must point back to the image — to the region, the fold, the light,
        the posture, the boundary. That is how the project avoids becoming another AI
        slop machine. The danger of AI in art is not that it becomes too intelligent —
        it is that it becomes too smooth. Too ready to praise. Too eager to produce
        language that sounds aesthetic while seeing nothing. This project must go the
        opposite way: less smooth and more perceptive, less generic and more situated,
        less caption machine and more close-reading instrument.
      </p>
      <p>
        The interface must obey the same motive. It cannot feel like random cards
        stacked inside cards, or drown the image in product chrome. It must be
        editorial, split-pane, calm, intentional: the Visual pane is the altar of
        seeing; the Content pane is the chamber where perception becomes language; the
        region layer is the bridge between looking and writing. This is why the project
        cares about architecture, not just features. If the data model separates manual
        boxes from auto segments from audience taps, the system fragments; but if all of
        them become one region model, the image has a single visual truth surface. That
        is context engineering applied to the visual world: not "throw the whole image
        into an LLM," but locate the parts, classify the domain, extract the regions,
        store the geometry, attach provenance, embed the taste, retrieve the echoes,
        generate the reading, and let the human refine.
      </p>
      <p>
        And the entertainment angle matters. Most serious AI projects hide behind
        productivity — saving time, automating work, summarising documents. That world
        is important, but it is not the whole human world. Humans do not live only by
        productivity. They live by fascination — by images, songs, outfits, faces,
        scenes, stories, longing, display, beauty, myth, drama, memory, status, style,
        and the strange private reasons something stays in the mind. A serious AI
        project can be built there too — not as cheap entertainment automation, but as
        infrastructure for fascination.
      </p>
      <p>
        The spine has to be built correctly. First fashion — body, garment, material,
        surface, desire, social code, pose, ornament, concealment, exposure, persona;
        symbolic armour, one of the richest domains for region-based interpretation.
        Then architecture — structure, light, plane, mass, threshold, shadow, rhythm.
        Then photography and entertainment broadly. The project does not need to begin
        universal. It needs to begin sharp.
      </p>
      <blockquote className="motive-quote">
        The wedge is not "AI for images." It is a level up from social media: a
        taste-and-story layer for images.
      </blockquote>
      <p>
        A level up means we keep the energy of the feed — speed, image, attraction,
        public display, reaction — but add the missing depth: region, memory,
        interpretation, authorship, taste. The user is not merely posting; they are
        discovering the story of why an image works, building a corpus of their own
        perception, slowly becoming more articulate about what they love. It does not
        fight entertainment — it deepens it from inside. It does not say stop scrolling,
        become serious. It says: your fascination already contains intelligence; let us
        build tools worthy of it.
      </p>
      <p>
        That is the soul of the project. Not moral improvement. Not academic
        respectability. Not productivity cosplay. Aesthetic intelligence — the courage
        to treat looking as knowledge, taste as data, entertainment as a serious domain
        of human meaning; to build infrastructure for the part of life that is visual,
        emotional, symbolic, sensual, and difficult to explain. Context engineering for
        work asks: what does the model need to know? Our version asks: what does the
        image need to reveal?
      </p>
      <blockquote className="motive-quote motive-quote--close">
        What has the human been seeing all along, without yet having the language to
        say it?
      </blockquote>
    </>
  );
}

const ARTICLES = [
  {
    slug: 'manifesto',
    eyebrow: 'The Motive',
    titleText: 'A manifesto for seeing',
    title: (
      <>
        A manifesto for <em>seeing</em>.
      </>
    ),
    motto: 'Unconcealment as context engineering.',
    Body: ManifestoBody,
  },
  {
    slug: 'context-engineering',
    eyebrow: 'The Motive · Essay',
    titleText: 'Context engineering for the image age',
    title: (
      <>
        Context engineering for the <em>image age</em>.
      </>
    ),
    motto: 'A level up from social media: a taste-and-story layer for images.',
    Body: ContextEngineeringBody,
  },
];

export default function MotivePage() {
  const { slug } = useParams();
  const index = Math.max(0, ARTICLES.findIndex((a) => a.slug === slug));
  const article = ARTICLES[index] ?? ARTICLES[0];
  const next = ARTICLES[index + 1] ?? null;
  const first = ARTICLES[0];
  const isLast = index === ARTICLES.length - 1;

  return (
    <article className="motive-page">
      <header className="motive-hero">
        <span className="eyebrow">{article.eyebrow}</span>
        <h1 className="motive-title">{article.title}</h1>
        <p className="motive-motto">{article.motto}</p>
      </header>

      <div className="motive-body">
        <article.Body />
      </div>

      <nav className="motive-next" aria-label="More from The Motive">
        {next ? (
          <Link to={`/motive/${next.slug}`} className="motive-next-link">
            <span className="motive-next-label">Next article</span>
            <span className="motive-next-title">{next.titleText} →</span>
          </Link>
        ) : (
          isLast &&
          index > 0 && (
            <Link to="/motive" className="motive-next-link motive-next-link--back">
              <span className="motive-next-label">Back to the start</span>
              <span className="motive-next-title">← {first.titleText}</span>
            </Link>
          )
        )}
      </nav>
    </article>
  );
}
