import { atom } from "jotai";
import { atomWithStorage } from "jotai/utils";

export interface User {
  id?: number;
  employeeNo?: string;
  displayName?: string;
  name?: string;
  role: "ADMIN" | "TEACHER";
}

export const tokenAtom = atomWithStorage<string | null>(
  "edu-flow-token",
  null
);

export const userAtom = atomWithStorage<User | null>("edu-flow-user", null);

export const isLoggedInAtom = atom((get) => get(tokenAtom) !== null);

export const isAdminAtom = atom((get) => get(userAtom)?.role === "ADMIN");

export const displayNameAtom = atom(
  (get) => get(userAtom)?.displayName || get(userAtom)?.name || ""
);
