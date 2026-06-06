export interface LoginResponse {
  id?: number;
  employeeNo?: string;
  displayName?: string;
  name?: string;
  role: "ADMIN" | "TEACHER";
}
