import { useLogin } from "../hooks/useLogin";
import LoginFields from "../ui/LoginFields";

export default function LoginForm() {
  const login = useLogin();
  return <LoginFields {...login} />;
}
