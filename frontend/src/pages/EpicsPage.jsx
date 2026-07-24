import React, { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { epicService } from '../services/epicService';
import EmptyState from '../components/brand/EmptyState';
import { CardGridSkeleton } from '../components/brand/Skeleton';
import { SectionEyebrow } from '../components/brand/SectionEyebrow';
import './EpicsPage.css';

const EpicsPage = () => {
    const [epics, setEpics] = useState([]);
    const [loading, setLoading] = useState(true);
    const navigate = useNavigate();

    useEffect(() => {
        loadEpics();
    }, []);

    const loadEpics = async () => {
        try {
            const data = await epicService.listEpics();
            setEpics(data.epics);
        } catch (error) {
            console.error("Error loading epics:", error);
        } finally {
            setLoading(false);
        }
    };

    const handleCreateNew = () => {
        navigate('/epics/new');
    };

    return (
        <div className="epics-page">
            <div className="epics-header">
                <div className="header-content">
                    <SectionEyebrow className="eyebrow">Epics</SectionEyebrow>
                    <h1>Epic Stories</h1>
                    <p>Generate and curate long-form narratives from your visual journey.</p>
                </div>
                <button className="create-btn" onClick={handleCreateNew}>
                    <span className="icon">+</span> Create New Epic
                </button>
            </div>

            {loading ? (
                <CardGridSkeleton count={6} label="Loading your epics…" />
            ) : epics.length === 0 ? (
                <EmptyState
                    motif="collect"
                    title="No epics yet"
                    body="Weave the parts you've noticed into a long-form narrative — your visual journey, told at length."
                    action={{ onClick: handleCreateNew, label: 'Create your first epic' }}
                />
            ) : (
                <div className="epics-grid">
                    {epics.map(epic => (
                        <Link to={`/epics/${epic.id}`} key={epic.id} className="epic-card">
                            <div className="epic-card-content">
                                <div className="card-header">
                                    <h2>{epic.title}</h2>
                                    <span className={`status-badge ${epic.status}`}>{epic.status}</span>
                                </div>
                                <p className="epic-desc">{epic.description || "No description provided."}</p>

                                <div className="epic-meta">
                                    <div className="stat">
                                        <span className="stat-value">{epic.metadata.total_blocks}</span>
                                        <span className="stat-label">Blocks</span>
                                    </div>
                                    <div className="stat">
                                        <span className="stat-value">{epic.metadata.total_images}</span>
                                        <span className="stat-label">Images</span>
                                    </div>
                                    <div className="stat">
                                        <span className="stat-value">{new Date(epic.updated_at).toLocaleDateString()}</span>
                                        <span className="stat-label">Updated</span>
                                    </div>
                                </div>

                                <div className="tags-preview">
                                    {epic.source_tags.slice(0, 3).map(tag => (
                                        <span key={tag} className="tag-pill">#{tag}</span>
                                    ))}
                                    {epic.source_tags.length > 3 && <span className="tag-pill">+{epic.source_tags.length - 3}</span>}
                                </div>
                            </div>
                        </Link>
                    ))}
                </div>
            )}
        </div>
    );
};

export default EpicsPage;
