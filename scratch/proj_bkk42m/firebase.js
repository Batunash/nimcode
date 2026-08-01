import firebase from 'firebase/app';
import 'firebase/auth';
import 'firebase/database';

const firebaseConfig = {
  apiKey: '<API_KEY>',
  authDomain: '<AUTH_DOMAIN>',
  databaseURL: '<DATABASE_URL>',
  projectId: '<PROJECT_ID>',
  storageBucket: '<STORAGE_BUCKET>',
  messagingSenderId: '<MESSAGING_SENDER_ID>',
  appId: '<APP_ID>',
};

firebase.initializeApp(firebaseConfig);

export default firebase;