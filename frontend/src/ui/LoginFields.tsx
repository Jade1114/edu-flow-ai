interface LoginFieldsProps {
  employeeNo: string;
  setEmployeeNo: (v: string) => void;
  password: string;
  setPassword: (v: string) => void;
  errors: Record<string, string>;
  setErrors: React.Dispatch<React.SetStateAction<Record<string, string>>>;
  loading: boolean;
  showPassword: boolean;
  setShowPassword: (v: boolean) => void;
  handleLogin: () => void;
  handleKeyDown: (e: React.KeyboardEvent) => void;
}

export default function LoginFields({
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
}: LoginFieldsProps) {
  return (
    <div className="space-y-4">
      {/* Employee No */}
      <div>
        <label className="label pb-1">
          <span className="label-text font-medium">工号</span>
        </label>
        <div className="relative">
          <span className="absolute left-3 top-1/2 -translate-y-1/2 text-base-content/40 text-sm">
            👤
          </span>
          <input
            type="text"
            placeholder="请输入工号"
            className={`input input-bordered w-full pl-9 ${
              errors.employeeNo ? "input-error" : ""
            }`}
            value={employeeNo}
            onChange={(e) => {
              setEmployeeNo(e.target.value);
              if (errors.employeeNo)
                setErrors((prev) => ({ ...prev, employeeNo: "" }));
            }}
            onKeyDown={handleKeyDown}
            disabled={loading}
          />
        </div>
        {errors.employeeNo && (
          <span className="label-text-alt text-error mt-1 block">
            {errors.employeeNo}
          </span>
        )}
      </div>

      {/* Password */}
      <div>
        <label className="label pb-1">
          <span className="label-text font-medium">密码</span>
        </label>
        <div className="relative">
          <span className="absolute left-3 top-1/2 -translate-y-1/2 text-base-content/40 text-sm">
            🔒
          </span>
          <input
            type={showPassword ? "text" : "password"}
            placeholder="请输入密码"
            className={`input input-bordered w-full pl-9 pr-10 ${
              errors.password ? "input-error" : ""
            }`}
            value={password}
            onChange={(e) => {
              setPassword(e.target.value);
              if (errors.password)
                setErrors((prev) => ({ ...prev, password: "" }));
            }}
            onKeyDown={handleKeyDown}
            disabled={loading}
          />
          <button
            type="button"
            className="absolute right-3 top-1/2 -translate-y-1/2 text-base-content/40 hover:text-base-content/60 text-sm"
            onClick={() => setShowPassword(!showPassword)}
            tabIndex={-1}
          >
            {showPassword ? "🙈" : "👁"}
          </button>
        </div>
        {errors.password && (
          <span className="label-text-alt text-error mt-1 block">
            {errors.password}
          </span>
        )}
      </div>

      {/* Submit */}
      <button
        className="btn btn-primary w-full mt-2"
        onClick={handleLogin}
        disabled={loading}
      >
        {loading ? (
          <span className="loading loading-spinner loading-sm" />
        ) : (
          "登录"
        )}
      </button>
    </div>
  );
}
