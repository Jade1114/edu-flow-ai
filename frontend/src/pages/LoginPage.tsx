import LoginForm from "../components/LoginForm";

export default function LoginPage() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-linear-to-br from-white to-slate-50 p-4">
      <div className="card bg-base-100 shadow-2xl w-full max-w-sm">
        <div className="card-body p-8">
          <div className="text-center mb-2">
            <h1 className="text-2xl font-bold text-base-content">
              Edu Flow AI
            </h1>
            <p className="text-sm text-base-content/60 mt-1">
              智能教务管理系统
            </p>
          </div>

          <LoginForm />

          <div>
            <div className="divider text-xs text-base-content/40 my-1">
              测试账号
            </div>
            <div className="text-xs text-base-content/50 space-y-0.5">
              <p>教务管理员：ADMIN001 / 123456</p>
              <p>教师：T1001 / 123456</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
