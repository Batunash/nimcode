import express from 'express';
import firebase from './firebase';
const app = express();

app.get('/notes', (req, res) => {
  firebase.firestore().collection('notes').get().then((snapshot) => {
    const notes = snapshot.docs.map((doc) => doc.data());
    res.json(notes);
  });
});

app.post('/notes', (req, res) => {
  const note = req.body.note;
  firebase.firestore().collection('notes').add({ note: note }).then(() => {
    res.json({ message: 'Note added successfully' });
  });
});

app.put('/notes/:id', (req, res) => {
  const id = req.params.id;
  const note = req.body.note;
  firebase.firestore().collection('notes').doc(id).update({ note: note }).then(() => {
    res.json({ message: 'Note updated successfully' });
  });
});

app.delete('/notes/:id', (req, res) => {
  const id = req.params.id;
  firebase.firestore().collection('notes').doc(id).delete().then(() => {
    res.json({ message: 'Note deleted successfully' });
  });
});

export default app;