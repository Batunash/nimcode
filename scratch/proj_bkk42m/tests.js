import React from 'react';
import ReactDOM from 'react-dom';
import { render, fireEvent, waitFor } from '@testing-library/react';
import { createStore, combineReducers } from 'redux';
import { Provider } from 'react-redux';
import firebase from './firebase';
import App from './App';

const store = createStore(
  combineReducers({
    firebase: (state = {}) => state
  })
);

describe('MindPal App', () => {
  it('renders the app', () => {
    const { getByText } = render(
      <Provider store={store}>
        <App />
      </Provider>
    );
    expect(getByText('MindPal')).toBeInTheDocument();
  });

  it('adds a new note', () => {
    const { getByPlaceholderText, getByText } = render(
      <Provider store={store}>
        <App />
      </Provider>
    );
    const noteInput = getByPlaceholderText('Type a note...');
    const addNoteButton = getByText('Add Note');
    fireEvent.change(noteInput, { target: { value: 'New note' } });
    fireEvent.click(addNoteButton);
    waitFor(() => expect(getByText('New note')).toBeInTheDocument());
  });
});