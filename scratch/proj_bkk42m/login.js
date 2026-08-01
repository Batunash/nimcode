import React from 'react';
import ReactDOM from 'react-dom';
import firebase from './firebase';

const Login = () => {
  const handleLogin = () => {
    const email = document.getElementById('email').value;
    const password = document.getElementById('password').value;
    firebase.auth().signInWithEmailAndPassword(email, password)
      .then((user) => {
        console.log('Logged in:', user);
      })
      .catch((error) => {
        console.error('Error logging in:', error);
      });
  };

  return (
    <div>
      <input type='email' id='email' placeholder='Email' />
      <input type='password' id='password' placeholder='Password' />
      <button onClick={handleLogin}>Login</button>
    </div>
  );
};

ReactDOM.render(<Login />, document.getElementById('root'));