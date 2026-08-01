import React, { useState, useEffect } from 'react';
import firebase from './firebase';

const Notes = () => {
  const [notes, setNotes] = useState([]);
  const [note, setNote] = useState('');

  useEffect(() => {
    firebase.firestore().collection('notes').onSnapshot((snapshot) => {
      const notes = snapshot.docs.map((doc) => doc.data());
      setNotes(notes);
    });
  }, []);

  const handleAddNote = () => {
    firebase.firestore().collection('notes').add({ note: note });
    setNote('');
  };

  return (
    <div>
      <input type='text' value={note} onChange={(e) => setNote(e.target.value)} />
      <button onClick={handleAddNote}>Add Note</button>
      <ul>
        {notes.map((note) => (
          <li key={note.id}>{note.note}</li>
        ))}
      </ul>
    </div>
  );
};

export default Notes;