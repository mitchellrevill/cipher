/**
 * Login page with MSAL integration
 */

import { useEffect, useState } from "react";
import { useMsal } from "@azure/msal-react";
import { AlertCircle, Info } from "lucide-react";
import { useNavigate } from "@tanstack/react-router";
import { accountToUser, isMsalConfigured, loginRequest } from "@/auth/msal";
import { Card, CardContent, CardDescription, CardHeader, CardTitle, Button, Input, Label } from "@/components/ui";
import { useAuthStore } from "@/store";
import { toast } from "sonner";

const AUTH_REASON_MESSAGES: Record<string, { tone: "info" | "error"; message: string }> = {
  "auth-required": { tone: "info", message: "Sign in to continue to the requested page." },
  "session-expired": { tone: "error", message: "Your session expired or was rejected. Sign in again to continue." },
  "signed-out": { tone: "info", message: "You have been signed out." },
  "auth-error": { tone: "error", message: "Authentication is not fully configured yet. Check your MSAL environment settings." },
};

export default function LoginRoute() {
  const { instance } = useMsal();
  const navigate = useNavigate();
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
  const authError = useAuthStore((state) => state.error);
  const setToken = useAuthStore((state) => state.setToken);
  const setUser = useAuthStore((state) => state.setUser);
  const setMsalAccount = useAuthStore((state) => state.setMsalAccount);
  const setError = useAuthStore((state) => state.setError);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const searchParams = new URLSearchParams(window.location.search);
  const redirectTarget = searchParams.get("redirect") || "/jobs";
  const authReason = searchParams.get("reason") || "";
  const reasonDetails = AUTH_REASON_MESSAGES[authReason];
  const activeMessage = authError || reasonDetails?.message || null;

  useEffect(() => {
    if (isAuthenticated) {
      const nextTarget = redirectTarget.startsWith("/") ? redirectTarget : "/jobs";
      if (nextTarget.startsWith("/")) {
        void navigate({ to: nextTarget, replace: true });
      } else {
        window.location.assign(redirectTarget);
      }
    }
  }, [isAuthenticated, navigate, redirectTarget]);

  useEffect(() => {
    if (!authReason || authReason === "signed-out") {
      return;
    }

    if (reasonDetails?.tone === "error") {
      setError(reasonDetails.message);
      return;
    }

    setError(null);
  }, [authReason, reasonDetails, setError]);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setError(null);
    try {
      if (import.meta.env.DEV) {
        setUser({
          id: "dev-user-123",
          email: email || "dev@example.com",
          name: "Developer",
          roles: ["admin"],
        });
        setMsalAccount(null);
        setToken("dev-token-bypass");
        await navigate({ to: redirectTarget.startsWith("/") ? redirectTarget : "/jobs", replace: true });
        return;
      }

      if (!isMsalConfigured) {
        throw new Error("MSAL is not configured. Set the VITE_MSAL_* environment variables.");
      }

      const result = await instance.loginPopup(loginRequest);
      const account = result.account;
      if (!account) {
        throw new Error("Microsoft sign-in did not return an account.");
      }

      instance.setActiveAccount(account);
      setMsalAccount(account);
      setUser(accountToUser(account));
      setToken(null);

      if (redirectTarget.startsWith("/")) {
        await navigate({ to: redirectTarget, replace: true });
      } else {
        window.location.assign(redirectTarget);
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : "Sign-in failed. Please try again.";
      setError(message);
      toast.error(message);
      console.error("Login failed", error);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex-1 flex items-center justify-center p-4">
      <Card className="w-full max-w-md">
        <CardHeader>
          <CardTitle>Sign In</CardTitle>
          <CardDescription>
            {import.meta.env.DEV
              ? "Use any local credentials to enter development mode."
              : "Sign in with your Microsoft account to access Cipher."}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleLogin} className="space-y-4">
            {activeMessage ? (
              <div
                className={
                  reasonDetails?.tone === "error" || authError
                    ? "flex items-start gap-3 rounded-lg border border-destructive/40 bg-destructive/10 px-4 py-3 text-sm text-destructive"
                    : "flex items-start gap-3 rounded-lg border border-sky-500/30 bg-sky-500/10 px-4 py-3 text-sm text-sky-700 dark:text-sky-300"
                }
              >
                {reasonDetails?.tone === "error" || authError ? (
                  <AlertCircle className="mt-0.5 h-4 w-4 flex-shrink-0" />
                ) : (
                  <Info className="mt-0.5 h-4 w-4 flex-shrink-0" />
                )}
                <p>{activeMessage}</p>
              </div>
            ) : null}
            {import.meta.env.DEV ? (
              <>
                <div className="space-y-2">
                  <Label htmlFor="email">Email</Label>
                  <Input
                    id="email"
                    type="email"
                    placeholder="you@example.com"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="password">Password</Label>
                  <Input
                    id="password"
                    type="password"
                    placeholder="••••••••"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                  />
                </div>
              </>
            ) : null}
            <Button type="submit" className="w-full" disabled={isLoading}>
              {isLoading ? "Signing in..." : import.meta.env.DEV ? "Sign In" : "Continue with Microsoft"}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
