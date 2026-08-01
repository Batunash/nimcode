import React, { useState, useEffect } from 'react';
import firebase from './firebase';

const Tags = () => {
  const [tags, setTags] = useState([]);
  const [tag, setTag] = useState('');

  useEffect(() => {
    firebase.firestore().collection('tags').onSnapshot((snapshot) => {
      const tags = snapshot.docs.map((doc) => doc.data());
      setTags(tags);
    });
  }, []);

  const handleAddTag = () => {
    firebase.firestore().collection('tags').add({ tag: tag });
    setTag('');
  };

  return (
    <div>
      <input type='text' value={tag} onChange={(e) => setTag(e.target.value)} />
      <button onClick={handleAddTag}>Add Tag</button>
      <ul>
        {tags.map((tag) => (
          <li key={tag.id}>{tag.tag}</li>
        ))}
      </ul>
    </div>
  );
};

export default Tags;