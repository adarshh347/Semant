import { useState } from 'react';
import axios from 'axios';

import { API_URL } from '../config/api';

// This component will receive a function 'onUploadSuccess' from its parent
function UploadForm({ onUploadSuccess }) {
  const [files, setFiles] = useState([]);
  const [description, setDescription] = useState('');
  const [generalTagsStr, setGeneralTagsStr] = useState('');

  const handleSubmit = async (event) => {
    event.preventDefault(); // Prevent the default form submission

    if (files.length === 0) {
      alert('Please select a file to upload.');
      return;
    }

    const formData = new FormData();

    // Check if it's a single or bulk upload
    if (files.length === 1) {
      formData.append('file', files[0]);
      formData.append('description', description);
      formData.append('general_tags_str', generalTagsStr);
      // You can add bounding_box_tags_str here as well if needed

      try {
        await axios.post(`${API_URL}/api/v1/posts/`, formData);
        alert('Upload successful!');
      } catch (error) {
        console.error('Error uploading single file:', error);
        alert('Upload failed.');
      }

    } else { // Bulk upload
      for (let i = 0; i < files.length; i++) {
        formData.append('files', files[i]);
      }

      try {
        await axios.post(`${API_URL}/api/v1/posts/bulk-upload`, formData);
        alert('Bulk upload successful!');
      } catch (error) {
        console.error('Error during bulk upload:', error);
        alert('Bulk upload failed.');
      }
    }

    // Reset the form and trigger a refresh of the post list in the parent component
    setFiles([]);
    setDescription('');
    setGeneralTagsStr('');
    if (onUploadSuccess) {
      onUploadSuccess();
    }
  };

  return (
    <div className="upload-form-container">
      {/* Heading omitted: the dialog already titles this ("Add to the archive"). */}
      <form onSubmit={handleSubmit}>
        <div>
          <label>Select Image(s):</label>
          <input
            type="file"
            multiple // Allows selecting multiple files
            onChange={(e) => setFiles(e.target.files)}
            required
          />
        </div>
        <div>
          <label>Description (for single upload only):</label>
          <input
            type="text"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
          />
        </div>
        <div>
          <label>General Tags (comma-separated, for single upload only):</label>
          <input
            type="text"
            value={generalTagsStr}
            onChange={(e) => setGeneralTagsStr(e.target.value)}
            placeholder="e.g., nature,sky,mountain"
          />
        </div>
        <button type="submit">Upload</button>
      </form>
    </div>
  );
}

export default UploadForm;