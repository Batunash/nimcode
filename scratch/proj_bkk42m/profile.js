import React, { useState, useEffect } from 'react';
import firebase from './firebase';

const Profile = () => {
  const [user, setUser] = useState({});
  const [profilePicture, setProfilePicture] = useState('');
  const [bio, setBio] = useState('');

  useEffect(() => {
    firebase.auth().onAuthStateChanged((user) => {
      if (user) {
        setUser(user);
      }
    });
  }, []);

  const handleProfilePictureChange = (e) => {
    setProfilePicture(e.target.files[0]);
  };

  const handleBioChange = (e) => {
    setBio(e.target.value);
  };

  const handleSaveProfile = () => {
    firebase.storage().ref('profilePictures/' + user.uid).put(profilePicture);
    firebase.firestore().collection('users').doc(user.uid).update({ bio: bio });
  };

  return (
    <div>
      <input type='file' onChange={handleProfilePictureChange} />
      <input type='text' value={bio} onChange={handleBioChange} />
      <button onClick={handleSaveProfile}>Save Profile</button>
    </div>
  );
};

export default Profile;