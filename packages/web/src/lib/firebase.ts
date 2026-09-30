import { initializeApp, type FirebaseApp } from "firebase/app";
import {
  GoogleAuthProvider,
  getAuth,
  onAuthStateChanged,
  signInWithPopup,
  signOut,
  type Auth,
  type User,
} from "firebase/auth";
import type { AppConfig } from "./types";

let app: FirebaseApp | null = null;
let auth: Auth | null = null;

export function firebaseAuth(config: NonNullable<AppConfig["firebase"]>): Auth {
  if (!auth) {
    app = initializeApp(config);
    auth = getAuth(app);
  }
  return auth;
}

export const watchUser = (a: Auth, callback: (user: User | null) => void) => onAuthStateChanged(a, callback);

export const signInWithGoogle = (a: Auth) => signInWithPopup(a, new GoogleAuthProvider());

export const signOutUser = (a: Auth) => signOut(a);
