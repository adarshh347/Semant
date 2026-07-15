import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { API_URL } from '../config/api';
import { Dialog, DialogContent, useToast } from './ui';
import './ImageSelectorModal.css';

// Proof-of-kit swap: this non-Chiasm modal now rides on the themed Radix Dialog
// (focus-trap, Esc, scroll-lock, a11y from Radix; surface from plum v1.3 tokens)
// instead of a hand-rolled overlay. Behaviour and props are unchanged.
const ImageSelectorModal = ({ isOpen, onClose, epicId, blockId, onImageSelect }) => {
    const [suggestions, setSuggestions] = useState([]);
    const [loading, setLoading] = useState(false);
    const [selectedImage, setSelectedImage] = useState(null);
    const [editedSubtitle, setEditedSubtitle] = useState('');
    const { toast } = useToast();

    useEffect(() => {
        if (isOpen && epicId && blockId) {
            loadSuggestions();
        }
    }, [isOpen, epicId, blockId]);

    const loadSuggestions = async () => {
        setLoading(true);
        try {
            const response = await axios.get(
                `${API_URL}/api/v1/epics/${epicId}/blocks/${blockId}/suggest-images`
            );
            setSuggestions(response.data);
        } catch (error) {
            console.error('Error loading image suggestions:', error);
            toast({ variant: 'error', title: 'Couldn’t load image suggestions' });
        } finally {
            setLoading(false);
        }
    };

    const handleImageClick = (image) => {
        setSelectedImage(image);
        setEditedSubtitle(image.suggested_subtitle || '');
    };

    const handleSave = async () => {
        if (!selectedImage) return;

        try {
            // Save the image association with the subtitle
            await onImageSelect(selectedImage.id, editedSubtitle);
            onClose();
        } catch (error) {
            console.error('Error saving image:', error);
            toast({ variant: 'error', title: 'Couldn’t save the image' });
        }
    };

    return (
        <Dialog open={isOpen} onOpenChange={(open) => { if (!open) onClose(); }}>
            <DialogContent
                title="Select Image for Story Block"
                description="Pick an AI-suggested image and refine its subtitle."
                size="lg"
                className="image-selector-modal"
            >
                {loading ? (
                    <div className="loading-state">
                        <div className="spinner"></div>
                        <p>Loading suggestions and generating subtitles...</p>
                    </div>
                ) : (
                    <>
                        <div className="suggestions-grid">
                            {suggestions.map((image) => (
                                <div
                                    key={image.id}
                                    className={`suggestion-card ${selectedImage?.id === image.id ? 'selected' : ''}`}
                                    onClick={() => handleImageClick(image)}
                                >
                                    <div className="image-wrapper">
                                        <img src={image.photo_url} alt="Suggestion" />
                                        {selectedImage?.id === image.id && (
                                            <div className="selected-badge">✓ Selected</div>
                                        )}
                                    </div>
                                    <div className="subtitle-preview">
                                        <small>AI Suggested Subtitle:</small>
                                        <p>{image.suggested_subtitle || 'No subtitle generated'}</p>
                                    </div>
                                </div>
                            ))}
                        </div>

                        {selectedImage && (
                            <div className="subtitle-editor">
                                <h3>Edit Subtitle</h3>
                                <textarea
                                    value={editedSubtitle}
                                    onChange={(e) => setEditedSubtitle(e.target.value)}
                                    placeholder="Edit the subtitle for this image..."
                                    rows={3}
                                />
                                <div className="modal-actions">
                                    <button className="btn-secondary" onClick={onClose}>Cancel</button>
                                    <button className="btn-primary" onClick={handleSave}>
                                        Save Image & Subtitle
                                    </button>
                                </div>
                            </div>
                        )}
                    </>
                )}
            </DialogContent>
        </Dialog>
    );
};

export default ImageSelectorModal;
