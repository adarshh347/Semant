import React from 'react';
import { useParams } from 'react-router-dom';
import AletheiaHook from '../components/AletheiaHook';

/**
 * The audience surface (Darshan Track F): `/read/:postId`.
 *
 * Deliberately its own route rather than a mode of the creator's post page. The creator
 * studio and the feed hook are two skins on one engine; giving the audience its own
 * shell keeps Track D's deep pane free of consumer branching.
 */
export default function ReadDeeperPage() {
    const { postId } = useParams();
    return <AletheiaHook postId={postId} />;
}
