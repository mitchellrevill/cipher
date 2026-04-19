import { useEffect, useMemo, useState } from "react";
import { AlertCircle, Info, Loader2, LogIn } from "lucide-react";
import { isMsalConfigured, startLoginRedirect } from "@/auth/msal";
import { Button, Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui";
import { useAuthStore } from "@/store";
import { toast } from "sonner";

const AUTH_REASON_MESSAGES: Record<string, { tone: "info" | "error"; message: string }> = {
  "auth-required": { tone: "info", message: "Sign in to continue to the requested page." },
  "session-expired": { tone: "error", message: "Your session expired or was rejected. Sign in again to continue." },
  "signed-out": { tone: "info", message: "You have been signed out." },
  "auth-error": { tone: "error", message: "Authentication is not fully configured yet. Check your MSAL environment settings." },
};

function normalizeRedirectTarget(rawTarget: string | null): string {
  if (!rawTarget) {
    return "/jobs";
  }

  try {
    const resolved = new URL(rawTarget, window.location.origin);
    if (resolved.origin !== window.location.origin) {
      return "/jobs";
    }

    return `${resolved.pathname}${resolved.search}${resolved.hash}` || "/jobs";
  } catch {
    return rawTarget.startsWith("/") ? rawTarget : "/jobs";
  }
}

export default function LoginRoute() {
  const authError = useAuthStore((state) => state.error);
  const setError = useAuthStore((state) => state.setError);
  const setLoading = useAuthStore((state) => state.setLoading);
  const [isLoading, setIsLoading] = useState(false);
  const searchParams = useMemo(() => new URLSearchParams(window.location.search), []);
  const redirectTarget = normalizeRedirectTarget(searchParams.get("redirect"));
  const authReason = searchParams.get("reason") || "";
  const reasonDetails = AUTH_REASON_MESSAGES[authReason];
  const activeMessage = authError || reasonDetails?.message || null;

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
    setLoading(true);
    setError(null);
    try {
      await startLoginRedirect(redirectTarget);
    } catch (error) {
      const message = error instanceof Error ? error.message : "Sign-in failed. Please try again.";
      setError(message);
      toast.error(message);
      console.error("Login failed", error);
    } finally {
      setIsLoading(false);
      setLoading(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4 py-8 text-foreground">
      <Card className="w-full max-w-md border-border/70 shadow-lg">
        <CardHeader className="space-y-2 text-center">
          <div className="mx-auto flex h-11 w-11 items-center justify-center rounded-2xl border border-border bg-muted text-sm font-semibold">
            C
          </div>
          <CardTitle className="text-2xl">Sign in</CardTitle>
          <CardDescription>Use your Microsoft account to continue to Cipher.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {activeMessage ? (
            <div className={reasonDetails?.tone === "error" || authError ? "flex items-start gap-3 rounded-lg border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive" : "flex items-start gap-3 rounded-lg border border-border bg-muted/50 px-4 py-3 text-sm text-muted-foreground"}>
              {reasonDetails?.tone === "error" || authError ? <AlertCircle className="mt-0.5 h-4 w-4 flex-shrink-0" /> : <Info className="mt-0.5 h-4 w-4 flex-shrink-0" />}
              <p>{activeMessage}</p>
            </div>
          ) : null}

          <form onSubmit={handleLogin}>
            <Button type="submit" className="h-11 w-full" disabled={isLoading || !isMsalConfigured}>
              {isLoading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <LogIn className="mr-2 h-4 w-4" />}
              {isLoading ? "Signing in..." : isMsalConfigured ? "Continue with Microsoft" : "Configure Microsoft sign-in"}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
