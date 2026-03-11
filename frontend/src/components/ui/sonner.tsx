import { useTheme } from "next-themes";
import { useEffect, useState } from "react";
import { Toaster as Sonner } from "sonner";
import type { CSSProperties } from "react";
import type { ToasterProps } from "sonner";

const Toaster = ({ ...props }: ToasterProps) => {
  const { theme = "system" } = useTheme();
  const [isMobile, setIsMobile] = useState(false);

  useEffect(() => {
    const checkMobile = () => {
      setIsMobile(window.innerWidth < 768);
    };

    checkMobile();
    window.addEventListener("resize", checkMobile);

    return () => window.removeEventListener("resize", checkMobile);
  }, []);

  return (
    <Sonner
      theme={theme as ToasterProps["theme"]}
      className="toaster group"
      position={isMobile ? "top-center" : "bottom-right"}
      expand={!isMobile}
      richColors
      closeButton
      visibleToasts={isMobile ? 2 : 5}
      toastOptions={{
        style: {
          background: "var(--popover)",
          color: "var(--popover-foreground)",
          borderColor: "var(--border)",
          opacity: 1,
          backdropFilter: "blur(12px)",
        },
        classNames: {
          toast: isMobile
            ? "group toast group-[.toaster]:!bg-popover/95 group-[.toaster]:!text-popover-foreground group-[.toaster]:!border-border group-[.toaster]:shadow-lg group-[.toaster]:!opacity-100 max-w-xs mx-2"
            : "group toast group-[.toaster]:!bg-popover/95 group-[.toaster]:!text-popover-foreground group-[.toaster]:!border-border group-[.toaster]:shadow-lg group-[.toaster]:!opacity-100",
          description: "group-[.toast]:text-muted-foreground",
          actionButton: "group-[.toast]:bg-primary group-[.toast]:text-primary-foreground",
          cancelButton: "group-[.toast]:bg-muted group-[.toast]:text-muted-foreground",
          error: "group-[.toaster]:border-destructive group-[.toaster]:text-destructive",
          success: "group-[.toaster]:border-emerald-500 group-[.toaster]:text-emerald-600",
          warning: "group-[.toaster]:border-amber-500 group-[.toaster]:text-amber-600",
          info: "group-[.toaster]:border-sky-500 group-[.toaster]:text-sky-600",
        },
      }}
      style={
        {
          "--normal-bg": "var(--popover)",
          "--normal-text": "var(--popover-foreground)",
          "--normal-border": "var(--border)",
        } as CSSProperties
      }
      {...props}
    />
  );
};

export { Toaster };
