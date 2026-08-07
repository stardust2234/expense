import type { AuthUser } from "../types/api";
import { request } from "./request";

export const authApi = {
  me: () => request<AuthUser>("/auth/me"),
};

