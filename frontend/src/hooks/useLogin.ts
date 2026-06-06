import { useState } from "react";
import { useNavigate } from "@tanstack/react-router";
import { useSetAtom } from "jotai";
import request from "../api/request";
import { tokenAtom, userAtom } from "../atoms/auth";
import type { LoginResponse } from "../types/LoginResponse";

export function useLogin() {
  const navigate = useNavigate();
  const setToken = useSetAtom(tokenAtom);
  const setUser = useSetAtom(userAtom);

  const [employeeNo, setEmployeeNo] = useState("");
  const [password, setPassword] = useState("");
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(false);
  const [showPassword, setShowPassword] = useState(false);

  function validate() {
    const next: Record<string, string> = {};
    if (!employeeNo.trim()) next.employeeNo = "请输入工号";
    if (!password) next.password = "请输入密码";
    setErrors(next);
    return Object.keys(next).length === 0;
  }

  async function handleLogin() {
    if (!validate()) return;
    setLoading(true);
    try {
      const data = await request.post<LoginResponse>("/api/auth/login", {
        employeeNo: employeeNo.trim(),
        password,
      });
      setToken(data.employeeNo || String(data.id));
      setUser(data);
      if (data.role === "ADMIN") {
        navigate({ to: "/admin" });
      } else {
        navigate({ to: "/teacher" });
      }
    } catch {
      // toast 已在拦截器处理
    } finally {
      setLoading(false);
    }
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === "Enter") handleLogin();
  }

  return {
    employeeNo,
    setEmployeeNo,
    password,
    setPassword,
    errors,
    setErrors,
    loading,
    showPassword,
    setShowPassword,
    handleLogin,
    handleKeyDown,
  };
}
