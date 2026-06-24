import { ProfileState } from './Profile.interface';

const initialState: ProfileState = {
  data: null,
  isLoading: false,
  error: null,
};

export const profileReducer = (state = initialState, action: any): ProfileState => {
  switch (action.type) {
    case 'FETCH_PROFILE_REQUEST':
      return { ...state, isLoading: true, error: null };
    case 'FETCH_PROFILE_SUCCESS':
      return { ...state, isLoading: false, data: action.payload };
    case 'FETCH_PROFILE_FAILURE':
      return { ...state, isLoading: false, error: action.payload };
    default:
      return state;
  }
};